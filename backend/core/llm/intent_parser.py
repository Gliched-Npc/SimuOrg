# backend/core/llm/intent_parser.py

import json
import os
import time

from openai import OpenAI

from backend.config import logger
from backend.core.llm.bounds import clamp, get_param_bounds
from backend.core.llm.prompt_templates import SYSTEM_PROMPT
from backend.core.llm.scenario_retriever import ScenarioRetriever
from backend.core.simulation.policies import SimulationConfig

_retriever = ScenarioRetriever()


def translate_policy(user_text: str, calib_context: dict) -> dict:
    """
    Translates user text to a dictionary of multipliers via LLM API.
    Builds a fallback mechanism to Local Ollama if Groq fails or is rate limited.
    """
    attrition = calib_context.get("annual_attrition_rate", 0)
    dynamic_examples = _retriever.get_top_k_scenarios(user_text, k=2)
    system_instructions = (
        SYSTEM_PROMPT
        + f"\n{dynamic_examples}\n\nCompany Profile Context:\nAnnual Attrition: {attrition*100:.1f}%\n"
    )

    messages = [
        {"role": "system", "content": system_instructions},
        {"role": "user", "content": user_text},
    ]

    groq_api_key = os.getenv("GROQ_API_KEY")

    # 1. Try Groq Remote API
    try:
        if not groq_api_key:
            raise ValueError("No GROQ_API_KEY found, falling back to local.")

        client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=groq_api_key)
        start_time = time.time()
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        latency = time.time() - start_time
        usage = response.usage
        if usage:
            logger.info(
                f"LLM (Groq) | Latency: {latency:.2f}s | Tokens: {usage.prompt_tokens} prompt, {usage.completion_tokens} completion"
            )
        else:
            logger.info(f"LLM (Groq) | Latency: {latency:.2f}s")

        content = response.choices[0].message.content
        return json.loads(content)

    except Exception as e:
        logger.warning(f"Groq API skipped or failed: {e}. Falling back to Local Ollama.")
        # 2. Try Local Ollama Fallback
        try:
            local_client = OpenAI(
                base_url="http://localhost:11434/v1",
                api_key="ollama",  # required but ignored by Ollama
            )
            start_time = time.time()
            response = local_client.chat.completions.create(
                model="llama3.1:8b",  # Make sure this matches your `ollama run`
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.1,
            )
            latency = time.time() - start_time
            logger.info(f"LLM (Ollama) | Latency: {latency:.2f}s")
            content = response.choices[0].message.content
            return json.loads(content)
        except Exception as fallback_e:
            logger.error(f"Both Remote Groq and Local Ollama failed. Local Error: {fallback_e}")
            raise RuntimeError(
                f"Both Remote Groq and Local Ollama failed. Local Error: {fallback_e}"
            )


def build_config_from_llm_output(
    llm_json: dict,
    calib: dict,
    user_text: str = "",
) -> tuple[SimulationConfig, dict]:
    bounds = get_param_bounds(calib)
    sgr = calib.get("behavior_stress_gain_rate", 0.01)
    mdr = calib.get("motivation_recovery_rate", 0.005)

    # ── Whitelist guards ───────────────────────────────────────────────────────
    if not llm_json.get("intent_mentions_layoff", False):
        if float(llm_json.get("layoff_ratio", 0.0)) > 0.0:
            logger.info(
                f"[intent_parser] GUARD: layoff_ratio={llm_json['layoff_ratio']} "
                f"rejected — not mentioned in intent. Forcing 0.0."
            )
            llm_json["layoff_ratio"] = 0.0

    # Layoffs automatically imply hiring freeze — you don't hire while firing
    if (
        llm_json.get("intent_mentions_layoff", False)
        and float(llm_json.get("layoff_ratio", 0.0)) > 0.0
    ):
        llm_json["hiring_active"] = False
        logger.info("[intent_parser] AUTO: layoff detected → hiring_active forced to False.")
    elif not llm_json.get("intent_mentions_hiring_freeze", False):
        if llm_json.get("hiring_active", True) is False:
            logger.info(
                "[intent_parser] GUARD: hiring_active=false "
                "rejected — not mentioned in intent. Forcing true."
            )
            llm_json["hiring_active"] = True

    if not llm_json.get("intent_mentions_wlb_penalty", False):
        if float(llm_json.get("wlb_boost", 0.0)) < -0.05:
            logger.info(
                f"[intent_parser] GUARD: wlb_boost={llm_json['wlb_boost']} "
                f"rejected — not mentioned in intent. Forcing 0.0."
            )
            llm_json["wlb_boost"] = 0.0

    stress_gain = float(llm_json.get("stress_gain_rate_multiplier", 1.0)) * sgr
    motivation_decay = float(llm_json.get("motivation_decay_rate_multiplier", 1.0)) * mdr

    # ── Precise percentage extraction (bypasses LLM bucket-rounding) ──────────
    # When the user states "12% raise" and "15% overtime reduction", the LLM
    # returns exact floats in salary_increase_pct / overtime_reduction_pct.
    # We use these to compute bonus and workload_multiplier precisely so that
    # 10% vs 12% raise produces different simulation outcomes.
    salary_pct = float(llm_json.get("salary_increase_pct", 0.0))
    overtime_cut = float(llm_json.get("overtime_reduction_pct", 0.0))

    # Bonus: linear scale — 1% raise = 0.1 bonus units (so 10%→1.0, 12%→1.2, 25%→2.5)
    # Falls back to LLM's bucketed `bonus` if no explicit salary_pct was returned.
    if salary_pct > 0.0:
        precise_bonus = round(salary_pct / 10.0, 3)
        logger.info(
            f"[intent_parser] PRECISE salary: {salary_pct:.1f}% → bonus={precise_bonus:.3f} "
            f"(LLM bucket was {llm_json.get('bonus', 'N/A')})"
        )
    else:
        precise_bonus = float(llm_json.get("bonus", 0.0))

    # Workload: overtime reduction directly shrinks workload_multiplier.
    # 15% cut → 1.0 - 0.15 = 0.85 | 20% cut → 1.0 - 0.20 = 0.80
    # Falls back to LLM's workload_multiplier if no explicit overtime_cut was returned.
    base_workload = float(llm_json.get("workload_multiplier", 1.0))

    if overtime_cut > 0.0:
        # Clamp: max 60% overtime reduction → min workload multiplier of 0.4
        overtime_multiplier = max(0.4, 1.0 - overtime_cut / 100.0)
        base_workload *= overtime_multiplier
        # Propagate consistent stress / motivation relief from the reduced workload
        _workload_stress_scale = max(0.25, 1.0 - overtime_cut / 100.0)
        stress_gain = min(stress_gain, sgr * _workload_stress_scale)
        logger.info(
            f"[intent_parser] PRECISE overtime_cut: {overtime_cut:.1f}% "
            f"→ base_workload={base_workload:.3f} "
            f"(LLM value was {llm_json.get('workload_multiplier', 'N/A')})"
        )

    precise_workload = round(base_workload, 3)

    # ── Precise Layoff Math (bypasses LLM calculation entirely) ──────────────
    layoff = float(llm_json.get("layoff_ratio", 0.0))
    if layoff > 0.0 and layoff < 1.0:
        layoff_workload_multiplier = 1.0 / (1.0 - layoff)
        precise_workload = round(base_workload * layoff_workload_multiplier, 3)
        stress_gain = round((precise_workload**2) * sgr * 1.5, 3)
        motivation_decay = round((1.0 + (layoff * 15.0)) * mdr, 3)
        llm_json["shock_factor"] = round(layoff * 2.5, 3)
        logger.info(
            f"[intent_parser] PRECISE layoff: {layoff*100:.1f}% → compounded precise_workload={precise_workload:.3f}, stress={stress_gain:.2f}"
        )

    config = SimulationConfig(
        workload_multiplier=clamp(precise_workload, *bounds.get("workload_multiplier", (0.4, 1.6))),
        motivation_decay_rate=clamp(
            motivation_decay, *bounds.get("motivation_decay_rate", (0.3 * mdr, 10.0 * mdr))
        ),
        shock_factor=clamp(
            float(llm_json.get("shock_factor", 0.0)), *bounds.get("shock_factor", (0.0, 0.7))
        ),
        hiring_active=bool(llm_json.get("hiring_active", True)),
        layoff_ratio=clamp(
            float(llm_json.get("layoff_ratio", 0.0)), *bounds.get("layoff_ratio", (0.0, 0.5))
        ),
        stress_gain_rate=clamp(
            stress_gain, *bounds.get("stress_gain_rate", (0.4 * sgr, 9.0 * sgr))
        ),
        # Minimum 3 months — "immediately" shouldn't cut the sim to 1 month,
        # but explicit short durations like "3 months" are still respected.
        duration_months=clamp(
            max(3, int(llm_json.get("duration_months", 12))),
            *bounds.get("duration_months", (1, 36)),
        ),
        bonus=clamp(precise_bonus, *bounds.get("bonus", (0.0, 5.0))),
        wlb_boost=clamp(
            float(llm_json.get("wlb_boost", 0.0)), *bounds.get("wlb_boost", (0.0, 1.0))
        ),
        # Store raw percentages so time_engine can inject them directly into agent features
        salary_increase_pct=max(0.0, salary_pct),
        overtime_reduction_pct=max(0.0, overtime_cut),
    )
    justification = llm_json.get("_justification", {})
    return config, justification

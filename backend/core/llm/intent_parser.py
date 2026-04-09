# backend/core/llm/intent_parser.py

import json
import os
from openai import OpenAI
from backend.core.llm.prompt_templates import SYSTEM_PROMPT
from backend.core.llm.bounds import get_param_bounds, clamp
from backend.core.simulation.policies import SimulationConfig

def _mentions_layoff(text: str) -> bool:
    keywords = [
        "layoff", "lay off", "laid off", "redundan", "headcount reduction",
        "headcount cut", "terminate", "termination", "let go", "job cut",
        "retrench", "downsize", "staff reduction", "workforce reduction"
    ]
    return any(k in text.lower() for k in keywords)


def _mentions_hiring_freeze(text: str) -> bool:
    keywords = [
        "hiring freeze", "no hiring", "pause hiring", "stop hiring",
        "halt hiring", "freeze hiring", "no backfill", "no recruitment"
    ]
    return any(k in text.lower() for k in keywords)


def _mentions_wlb_penalty(text: str) -> bool:
    keywords = [
        "return to office", "rto", "mandatory office", "relocation",
        "relocate", "mandatory overtime", "longer hours", "extended hours"
    ]
    return any(k in text.lower() for k in keywords)


def translate_policy(user_text: str, calib_context: dict) -> dict:
    """
    Translates user text to a dictionary of multipliers via LLM API.
    Builds a fallback mechanism to Local Ollama if Groq fails or is rate limited.
    """
    attrition = calib_context.get("annual_attrition_rate", 0)
    system_instructions = SYSTEM_PROMPT + f"\n\nCompany Profile Context:\nAnnual Attrition: {attrition*100:.1f}%\n"
    
    messages = [
        {"role": "system", "content": system_instructions},
        {"role": "user", "content": user_text}
    ]

    groq_api_key = os.getenv("GROQ_API_KEY")
    
    # 1. Try Groq Remote API
    try:
        if not groq_api_key:
            raise ValueError("No GROQ_API_KEY found, falling back to local.")
        
        client = OpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=groq_api_key
        )
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.1
        )
        content = response.choices[0].message.content
        return json.loads(content)
        
    except Exception as e:
        print(f"Groq API skipped or failed: {e}. Falling back to Local Ollama.")
        # 2. Try Local Ollama Fallback
        try:
            local_client = OpenAI(
                base_url="http://localhost:11434/v1",
                api_key="ollama" # required but ignored by Ollama
            )
            response = local_client.chat.completions.create(
                model="llama3.1:8b", # Make sure this matches your `ollama run`
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.1
            )
            content = response.choices[0].message.content
            return json.loads(content)
        except Exception as fallback_e:
            raise RuntimeError(f"Both Remote Groq and Local Ollama failed. Local Error: {fallback_e}")

def build_config_from_llm_output(
    llm_json: dict,
    calib: dict,
    user_text: str = "",
) -> tuple[SimulationConfig, dict]:
    bounds = get_param_bounds(calib)
    sgr = calib.get("behavior_stress_gain_rate", 0.01)
    mdr = calib.get("motivation_recovery_rate", 0.005)

    # ── Whitelist guards ───────────────────────────────────────────────────────
    if not _mentions_layoff(user_text):
        if float(llm_json.get("layoff_ratio", 0.0)) > 0.0:
            print(f"[intent_parser] GUARD: layoff_ratio={llm_json['layoff_ratio']} "
                  f"rejected — not mentioned by user. Forcing 0.0.")
            llm_json["layoff_ratio"] = 0.0

    if not _mentions_hiring_freeze(user_text):
        if llm_json.get("hiring_active", True) is False:
            print(f"[intent_parser] GUARD: hiring_active=false "
                  f"rejected — not mentioned by user. Forcing true.")
            llm_json["hiring_active"] = True

    if not _mentions_wlb_penalty(user_text):
        if float(llm_json.get("wlb_boost", 0.0)) < -0.05:
            print(f"[intent_parser] GUARD: wlb_boost={llm_json['wlb_boost']} "
                  f"rejected — not mentioned by user. Forcing 0.0.")
            llm_json["wlb_boost"] = 0.0

    stress_gain = float(llm_json.get("stress_gain_rate_multiplier", 1.0))
    motivation_decay = float(llm_json.get("motivation_decay_rate_multiplier", 1.0)) * mdr

    config = SimulationConfig(
        workload_multiplier   = clamp(float(llm_json.get("workload_multiplier", 1.0)),
                                      *bounds.get("workload_multiplier", (0.5, 1.6))),
        motivation_decay_rate = clamp(motivation_decay,
                                      *bounds.get("motivation_decay_rate", (0.3*mdr, 10.0*mdr))),
        shock_factor          = clamp(float(llm_json.get("shock_factor", 0.0)),
                                      *bounds.get("shock_factor", (0.0, 0.7))),
        hiring_active         = bool(llm_json.get("hiring_active", True)),
        layoff_ratio          = clamp(float(llm_json.get("layoff_ratio", 0.0)),
                                      *bounds.get("layoff_ratio", (0.0, 0.3))),
        stress_gain_rate      = clamp(stress_gain,
                                      *bounds.get("stress_gain_rate", (0.4, 9.0))),
        duration_months       = clamp(int(llm_json.get("duration_months", 12)),
                                      *bounds.get("duration_months", (1, 36))),
        overtime_bonus        = clamp(float(llm_json.get("overtime_bonus", 0.0)),
                                      *bounds.get("overtime_bonus", (0.0, 5.0))),
        wlb_boost             = clamp(float(llm_json.get("wlb_boost", 0.0)),
                                      *bounds.get("wlb_boost", (0.0, 1.0))),
    )
    justification = llm_json.get("_justification", {})
    return config, justification

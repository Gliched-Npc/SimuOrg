# backend/core/llm/reasoning_chain.py
#
# Chain-of-Thought CEO Reasoning Engine
# ──────────────────────────────────────
# Takes a completed simulation result and runs a structured 4-step reasoning
# chain to produce a structured executive briefing for the CEO.
#
# Steps (all in a single LLM call with structured JSON output):
#   Step 1 — Interpret  : What happened and why?
#   Step 2 — Compare    : Better or worse than historical baseline?
#   Step 3 — Risks      : Top 3 risks over the simulation period
#   Step 4 — Recommend  : What should the CEO do next?

import json
import os
from datetime import datetime
from openai import OpenAI


# ── Prompt ────────────────────────────────────────────────────────────────────

REASONING_SYSTEM_PROMPT = """You are a senior HR analytics advisor and organizational psychologist presenting simulation results to a company's CEO.

You will be given structured data from an agent-based Monte Carlo simulation of organizational dynamics. Your job is to reason through this data in 4 clear steps and return a structured JSON executive briefing.

Your tone must be: professional, direct, data-driven, and actionable. Avoid jargon. Write as if briefing a CEO who has 5 minutes to read this.

You MUST return ONLY a valid JSON object. No markdown, no text outside the JSON.

Required JSON structure:
{
  "situation": "2-3 sentence summary of what happened in the simulation — key numbers only",
  "performance": {
    "attrition_verdict": "improving | stable | deteriorating",
    "stress_verdict":    "improving | stable | deteriorating",
    "morale_verdict":    "improving | stable | deteriorating",
    "productivity_verdict": "improving | stable | deteriorating",
    "one_line":          "Single sentence verdict e.g. 'A high-risk scenario with unsustainable attrition.'"
  },
  "comparison": "2 sentences comparing this scenario to the company's historical baseline attrition. Be specific with numbers.",
  "risks": [
    {
      "title":    "Short risk title",
      "severity": "high | medium | low",
      "detail":   "1-2 sentences explaining the risk and what drives it"
    },
    { ... },
    { ... }
  ],
  "recommendation": "3-4 sentences of concrete, specific CEO actions. Always end with a time horizon (e.g. 'within 60 days').",
  "confidence": "high | medium | low",
  "confidence_reason": "One sentence explaining confidence level based on data quality or simulation parameters."
}

SEVERITY GUIDE:
- high: attrition > 25% annually OR stress increase > 0.15 OR headcount loss > 15%
- medium: attrition 15-25% OR stress increase 0.08-0.15 OR headcount loss 8-15%
- low: attrition < 15% OR stress improving OR headcount stable
"""


def _build_reasoning_prompt(sim_result: dict, policy_config: dict | None) -> str:
    """
    Compress the Monte Carlo result into a focused prompt.
    Only sends the data the LLM actually needs — not the full monthly time series.
    """
    summary = sim_result.get("summary", {})
    results = sim_result.get("results", [])
    config  = policy_config or sim_result.get("config", {})

    # Key month snapshots: start, mid, end
    start = results[0]  if results else {}
    mid   = results[len(results) // 2] if len(results) > 1 else {}
    end   = results[-1] if results else {}

    def fmt(month_data: dict, key: str) -> str:
        if not month_data or key not in month_data:
            return "N/A"
        v = month_data[key]
        return f"mean={v['mean']:.3f}, range=[{v['min']:.3f}–{v['max']:.3f}]"

    prompt = f"""
SIMULATION BRIEF FOR CEO REVIEW
=================================

POLICY SCENARIO: {summary.get('policy_name', 'Unknown')}
DURATION: {summary.get('duration_months', '?')} months
MONTE CARLO RUNS: {sim_result.get('runs', '?')} simulations

POLICY PARAMETERS USED:
{json.dumps(config, indent=2)}

KEY OUTCOMES:
  Initial headcount  : {summary.get('initial_headcount', '?'):.0f} employees
  Final headcount    : {summary.get('final_headcount', '?'):.0f} employees
  Period attrition   : {summary.get('period_attrition_pct', '?'):.1f}% over the period
  Annual attrition   : {summary.get('annual_attrition_pct', '?'):.1f}% annualised
  Historical baseline: {summary.get('baseline_annual_attrition_pct', 'unknown')}% (company's actual attrition)
  Realism check      : {summary.get('realism_flag', 'unknown')}

MONTHLY TRAJECTORY (mean across all runs):
  Month 1  (start) — headcount: {fmt(start, 'headcount')} | stress: {fmt(start, 'avg_stress')} | productivity: {fmt(start, 'avg_productivity')} | motivation: {fmt(start, 'avg_motivation')} | satisfaction: {fmt(start, 'avg_job_satisfaction')} | WLB: {fmt(start, 'avg_work_life_balance')}
  Month {mid.get('month', '?')} (mid)   — headcount: {fmt(mid,   'headcount')} | stress: {fmt(mid,   'avg_stress')} | productivity: {fmt(mid,   'avg_productivity')} | motivation: {fmt(mid, 'avg_motivation')} | satisfaction: {fmt(mid, 'avg_job_satisfaction')} | WLB: {fmt(mid, 'avg_work_life_balance')}
  Month {end.get('month', '?')} (end)   — headcount: {fmt(end,   'headcount')} | stress: {fmt(end,   'avg_stress')} | productivity: {fmt(end,   'avg_productivity')} | motivation: {fmt(end, 'avg_motivation')} | satisfaction: {fmt(end, 'avg_job_satisfaction')} | WLB: {fmt(end, 'avg_work_life_balance')}

PEAK STRESS MONTH: {max((r['avg_stress']['mean'] for r in results), default=0):.3f}
BURNOUT EVENTS (end of period): {fmt(end, 'burnout_count')}

Now produce the CEO executive briefing JSON as instructed.
"""
    return prompt.strip()


# ── Main function ──────────────────────────────────────────────────────────────

def run_reasoning_chain(sim_result: dict, policy_config: dict | None = None) -> dict:
    """
    Run the 4-step chain-of-thought reasoning over a simulation result.

    Parameters
    ----------
    sim_result    : full dict returned by run_monte_carlo()
    policy_config : the SimulationConfig.__dict__ used for the run (optional)

    Returns
    -------
    Structured dict with keys: situation, performance, comparison, risks,
    recommendation, confidence, confidence_reason, generated_at
    """
    prompt = _build_reasoning_prompt(sim_result, policy_config)

    messages = [
        {"role": "system", "content": REASONING_SYSTEM_PROMPT},
        {"role": "user",   "content": prompt},
    ]

    groq_api_key = os.getenv("GROQ_API_KEY")
    raw_json = None

    # 1. Try Groq (fast, cheap)
    try:
        if not groq_api_key:
            raise ValueError("No GROQ_API_KEY — falling back to local Ollama.")
        client = OpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=groq_api_key,
        )
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.2,   # slightly higher than policy gen — reasoning benefits from fluency
        )
        raw_json = json.loads(response.choices[0].message.content)

    except Exception as e:
        print(f"[reasoning] Groq failed: {e}. Falling back to local Ollama.")
        # 2. Local Ollama fallback
        try:
            local_client = OpenAI(
                base_url="http://localhost:11434/v1",
                api_key="ollama",
            )
            response = local_client.chat.completions.create(
                model="llama3.1:8b",
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.2,
            )
            raw_json = json.loads(response.choices[0].message.content)
        except Exception as fallback_e:
            raise RuntimeError(
                f"Both Groq and local Ollama failed for reasoning chain. "
                f"Local error: {fallback_e}"
            )

    # Stamp with generation time and return
    raw_json["generated_at"] = datetime.utcnow().isoformat() + "Z"
    return raw_json

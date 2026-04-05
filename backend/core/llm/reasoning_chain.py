# backend/core/llm/reasoning_chain.py
#
# Chain-of-Thought CEO Reasoning Engine
# ──────────────────────────────────────
# Takes a completed simulation result and runs a structured reasoning
# chain to produce a structured executive briefing for the CEO.
#
# Improvements over v1:
#   - Full monthly burnout + stress trajectory passed (not just 3 snapshots)
#   - Inflection point detection: month where deterioration breaks
#   - 5 named risk categories with explicit detection guidance
#   - Recommendation requires: proceed/reject verdict + counter-measure + cost impact
#   - Cost framing: replacement cost estimated from attrition counts
#   - Loyalty floor warning when loyalty < 0.50

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
  "situation": "3-4 sentence summary. MUST include: (1) what the policy was, (2) the final attrition % vs baseline, (3) the specific month where deterioration broke (the inflection point), (4) final headcount loss in absolute employee count.",
  "inflection_point": {
    "month": <integer — the month where burnout or attrition accelerated sharply>,
    "trigger": "One sentence: what specifically spiked at this month (e.g. burnout crossed X, stress exceeded quit threshold, attrition doubled)"
  },
  "performance": {
    "attrition_verdict":    "improving | stable | deteriorating",
    "stress_verdict":       "improving | stable | deteriorating",
    "morale_verdict":       "improving | stable | deteriorating",
    "productivity_verdict": "improving | stable | deteriorating",
    "one_line":             "Single sentence verdict that references the inflection point month"
  },
  "comparison": "2 sentences comparing actual vs baseline. Use exact numbers: attrition %, headcount delta, stress delta.",
  "risks": [
    {
      "title":    "Unsustainable Attrition",
      "severity": "high | medium | low",
      "detail":   "Cite the specific attrition % and how many months before it becomes irreversible."
    },
    {
      "title":    "Burnout Cascade",
      "severity": "high | medium | low",
      "detail":   "Cite the burnout count trajectory: start, mid, end. Identify when the cascade became self-sustaining."
    },
    {
      "title":    "Loyalty Collapse",
      "severity": "high | medium | low",
      "detail":   "Cite loyalty start and end values. If loyalty dropped below 0.50, flag this as a 'point of no return' — recovery requires active intervention, not just removing the bad policy."
    },
    {
      "title":    "Productivity Erosion",
      "severity": "high | medium | low",
      "detail":   "Cite productivity start and end. Translate the % drop into business impact: 'a workforce of X employees at Y% productivity is equivalent to Z fewer full-time employees'."
    },
    {
      "title":    "Contagion and Peer Stress Spread",
      "severity": "high | medium | low",
      "detail":   "Cite the shock_factor used. Explain how departures visible to peers trigger additional voluntary exits beyond the direct cause."
    }
  ],
  "recommendation": "4-5 sentences. MUST include: (1) explicit verdict: 'Do NOT proceed' or 'Proceed with modifications' — never vague, (2) a specific counter-measure (e.g. 'Instead, cap workload at X% and pair with WLB support'), (3) a cost framing: 'Replacing N employees costs approximately $X assuming 50% annual salary replacement cost per hire', (4) the time window before damage becomes hard to reverse, (5) a monitoring trigger: 'If stress exceeds X by month Y, escalate immediately.'",
  "confidence": "high | medium | low",
  "confidence_reason": "One sentence: cite the number of Monte Carlo runs and the calibration std to justify the confidence level."
}

SEVERITY GUIDE:
- high: attrition > 25% annually OR stress increase > 0.15 OR headcount loss > 15% OR burnout > 100 at end
- medium: attrition 15–25% OR stress increase 0.08–0.15 OR headcount loss 8–15% OR burnout 30–100
- low: attrition < 15% OR stress improving OR headcount stable OR burnout < 30

INFLECTION POINT GUIDE:
- Look for the month where burnout_count shows the largest jump (> 2x previous month)
- OR the month where attrition_count increases by > 50% vs previous month
- OR the month where avg_stress crosses 0.12 (typical quit threshold)
- Report the EARLIEST of these triggers as the inflection month

LOYALTY FLOOR WARNING:
- If loyalty end value < 0.50, the recommendation MUST include: "Loyalty has fallen below the recovery threshold (0.50). Simply reversing the policy will not restore employee trust — active recovery measures are required."

COST FRAMING RULE:
- Total quits over the period = (initial_headcount - final_headcount) + any hiring
- Replacement cost estimate = total_quits × 0.5 × avg_annual_salary
- If avg_annual_salary is unknown, assume $60,000 as a conservative floor
- Always present this as a range: "Replacing these N employees costs $X–$Y depending on role seniority."
"""


def _detect_inflection_point(results: list[dict]) -> dict:
    """
    Identify the month where the simulation deterioration breaks sharply.
    Returns {"month": int, "trigger": str}.
    """
    best_month = 1
    best_trigger = "No sharp inflection detected — deterioration was gradual."
    max_score = 0.0

    for i in range(1, len(results)):
        prev = results[i - 1]
        curr = results[i]
        month = curr.get("month", i + 1)

        scores = []
        trigger_parts = []

        # Burnout jump
        prev_burnout = prev.get("burnout_count", {}).get("mean", 0) or 0
        curr_burnout = curr.get("burnout_count", {}).get("mean", 0) or 0
        if prev_burnout > 0 and curr_burnout > prev_burnout * 1.8:
            ratio = curr_burnout / max(prev_burnout, 1)
            scores.append(ratio)
            trigger_parts.append(f"burnout jumped from {prev_burnout:.0f} to {curr_burnout:.0f} ({ratio:.1f}x)")

        # Attrition spike
        prev_attr = prev.get("attrition_count", {}).get("mean", 0) or 0
        curr_attr = curr.get("attrition_count", {}).get("mean", 0) or 0
        if prev_attr > 0 and curr_attr > prev_attr * 1.5:
            ratio = curr_attr / max(prev_attr, 1)
            scores.append(ratio * 0.5)
            trigger_parts.append(f"monthly quits spiked from {prev_attr:.0f} to {curr_attr:.0f}")

        # Stress crossing quit threshold ~0.12
        prev_stress = prev.get("avg_stress", {}).get("mean", 0) or 0
        curr_stress = curr.get("avg_stress", {}).get("mean", 0) or 0
        if prev_stress < 0.12 <= curr_stress:
            scores.append(1.5)
            trigger_parts.append(f"avg stress crossed the quit threshold (0.12) reaching {curr_stress:.3f}")

        total_score = sum(scores)
        if total_score > max_score:
            max_score = total_score
            best_month = month
            best_trigger = "; ".join(trigger_parts) if trigger_parts else f"deterioration accelerated at month {month}"

    return {"month": best_month, "trigger": best_trigger}


def _build_reasoning_prompt(sim_result: dict, policy_config: dict | None) -> str:
    """
    Compress the Monte Carlo result into a focused prompt.
    Sends: summary, full burnout/stress trajectory, inflection point, and cost framing context.
    """
    summary = sim_result.get("summary", {})
    results = sim_result.get("results", [])
    config  = policy_config or sim_result.get("config", {})

    # Key month snapshots
    start = results[0]  if results else {}
    end   = results[-1] if results else {}

    def val(month_data: dict, key: str) -> str:
        if not month_data or key not in month_data:
            return "N/A"
        v = month_data[key]
        return f"{v['mean']:.3f} (range {v['min']:.3f}–{v['max']:.3f})"

    # Build full burnout + stress trajectory for inflection awareness
    trajectory_lines = []
    for r in results:
        m = r.get("month", "?")
        stress   = r.get("avg_stress",    {}).get("mean", 0)
        burnout  = r.get("burnout_count", {}).get("mean", 0)
        quits    = r.get("attrition_count",{}).get("mean", 0)
        loyalty  = r.get("avg_loyalty",   {}).get("mean", 0)
        prod     = r.get("avg_productivity",{}).get("mean", 0)
        trajectory_lines.append(
            f"  Month {m:>2}: stress={stress:.3f}  burnout={burnout:>6.1f}  quits={quits:>5.1f}  loyalty={loyalty:.3f}  productivity={prod:.3f}"
        )

    # Detect inflection point in Python to hint the LLM
    inflection = _detect_inflection_point(results)

    # Cost framing context
    initial_hc   = summary.get("initial_headcount", 0) or 0
    final_hc     = summary.get("final_headcount",   0) or 0
    total_loss   = round(initial_hc - final_hc)
    est_cost_low  = total_loss * 30_000   # 50% of $60k low floor
    est_cost_high = total_loss * 75_000   # 50% of $150k upper

    prompt = f"""
SIMULATION BRIEF FOR CEO REVIEW
=================================

POLICY SCENARIO : {summary.get('policy_name', 'Unknown')}
DURATION        : {summary.get('duration_months', '?')} months
MONTE CARLO RUNS: {sim_result.get('runs', '?')} simulations

POLICY PARAMETERS APPLIED:
{json.dumps(config, indent=2)}

HEADLINE OUTCOMES:
  Initial headcount  : {initial_hc:.0f} employees
  Final headcount    : {final_hc:.0f} employees  (lost {total_loss} employees)
  Period attrition   : {summary.get('period_attrition_pct', 0):.1f}% over the period
  Annual attrition   : {summary.get('annual_attrition_pct', 0):.1f}% annualised
  Historical baseline: {summary.get('baseline_annual_attrition_pct', 'unknown')}% (company's actual historical attrition)
  Attrition delta    : +{(summary.get('annual_attrition_pct', 0) - summary.get('baseline_annual_attrition_pct', 0)):.1f} percentage points vs baseline
  Realism check      : {summary.get('realism_flag', 'unknown')}

BASELINE COMPARISON:
  Start → End stress      : {val(start, 'avg_stress')} → {val(end, 'avg_stress')}
  Start → End productivity: {val(start, 'avg_productivity')} → {val(end, 'avg_productivity')}
  Start → End motivation  : {val(start, 'avg_motivation')} → {val(end, 'avg_motivation')}
  Start → End loyalty     : {val(start, 'avg_loyalty')} → {val(end, 'avg_loyalty')}
  Start → End job sat.    : {val(start, 'avg_job_satisfaction')} → {val(end, 'avg_job_satisfaction')}
  Start → End WLB         : {val(start, 'avg_work_life_balance')} → {val(end, 'avg_work_life_balance')}

FULL MONTHLY TRAJECTORY:
{chr(10).join(trajectory_lines)}

PRE-COMPUTED INFLECTION POINT (where deterioration broke sharply):
  Month   : {inflection['month']}
  Trigger : {inflection['trigger']}

LOYALTY FLOOR NOTE:
  End loyalty {val(end, 'avg_loyalty')} — {'BELOW 0.50: recovery requires active intervention' if (end.get('avg_loyalty', {}) or {}).get('mean', 1) < 0.50 else 'Above 0.50: reversible if policy removed'}

COST FRAMING CONTEXT:
  Net headcount loss  : {total_loss} employees
  Estimated replacement cost (50% of salary per hire):
    Conservative floor: ~${est_cost_low:,} (assuming $60k avg salary)
    Upper estimate    : ~${est_cost_high:,} (assuming $150k avg salary)
  Use this range in your recommendation. Do not invent other numbers.

NARRATIVE (from simulation engine):
{summary.get('narrative', 'No narrative available.')}

Now produce the CEO executive briefing JSON as instructed.
""".strip()
    return prompt


# ── Main function ──────────────────────────────────────────────────────────────

def run_reasoning_chain(sim_result: dict, policy_config: dict | None = None) -> dict:
    """
    Run the chain-of-thought reasoning over a simulation result.

    Parameters
    ----------
    sim_result    : full dict returned by run_monte_carlo()
    policy_config : the SimulationConfig.__dict__ used for the run (optional)

    Returns
    -------
    Structured dict with keys: situation, inflection_point, performance, comparison,
    risks, recommendation, confidence, confidence_reason, generated_at
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
            model="llama-3.3-70b-versatile",   # upgraded: 70B for richer CEO-level reasoning
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.25,
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
                temperature=0.25,
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

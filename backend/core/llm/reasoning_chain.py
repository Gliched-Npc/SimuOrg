# backend/core/llm/reasoning_chain.py
#
# Chain-of-Thought CEO Reasoning Engine
# ──────────────────────────────────────
# Takes a completed simulation result and produces a structured executive
# briefing for the CEO.
#
# Design principle:
#   Python does ALL the math and direction analysis.
#   The LLM only writes narrative and recommendations.
#   This prevents the LLM from misreading numbers or inverting trends.
#
# Steps:
#   1. _compute_analytics()  — pure Python: deltas, verdicts, flags, shape
#   2. _build_prompt()       — injects pre-computed analytics into the prompt
#   3. run_reasoning_chain() — calls LLM, validates output, stamps result

import json
import os
from datetime import datetime, timezone
from openai import OpenAI


# ── Analytics Engine (pure Python, no LLM) ────────────────────────────────────

def _safe_mean(month: dict, key: str) -> float | None:
    """Extract mean from a metric dict safely."""
    v = month.get(key)
    if v is None:
        return None
    return v.get("mean")


def _trend_verdict(pct_change: float, lower_is_better: bool = False) -> str:
    """
    Convert a % change into a human verdict.
    Thresholds are intentionally asymmetric — small improvements matter less
    than small deteriorations for executive risk framing.
    """
    if lower_is_better:
        if pct_change < -8:   return "improving"
        if pct_change < -3:   return "slightly improving"
        if pct_change <=  3:  return "stable"
        if pct_change <=  10: return "slightly deteriorating"
        return "deteriorating"
    else:
        if pct_change > 3:    return "improving"
        if pct_change > 1:    return "slightly improving"
        if pct_change >= -1:  return "stable"
        if pct_change >= -5:  return "slightly deteriorating"
        return "deteriorating"


def _severity_label(value: float, thresholds: dict) -> str:
    """Generic severity bucketer using a thresholds dict with 'high' and 'medium' keys."""
    if value >= thresholds["high"]:
        return "high"
    if value >= thresholds["medium"]:
        return "medium"
    return "low"


def _pct_change(start: float, end: float) -> float:
    if start == 0:
        return 0.0
    return ((end - start) / abs(start)) * 100


def _classify_scenario(config: dict, results: list) -> dict:
    """
    Step 0: Classify the scenario type from config and data.
    This runs BEFORE any metric interpretation.
    Every downstream analysis is conditioned on these flags.

    Why this matters:
      - In a layoff scenario, lower voluntary attrition is NOT good news.
        Fear suppresses quit rates. People aren't staying because they're happy.
      - In a workload-reduction scenario, stress dropping is expected and positive.
        Do NOT treat it as suspicious or note it as a coincidence.
      - In a growth scenario, workload increase is acceptable if motivation holds.
      - These flags prevent the LLM from applying the wrong mental model
        to a scenario it hasn't fully understood.
    """
    layoff_ratio    = config.get("layoff_ratio", 0) or 0
    workload        = config.get("workload_multiplier", 1.0) or 1.0
    hiring          = config.get("hiring_active", True)
    shock           = config.get("shock_factor", 0) or 0
    wlb             = config.get("wlb_boost", 0) or 0
    overtime        = config.get("bonus", 0) or 0

    # Compute total layoffs from data (more reliable than config alone)
    total_layoffs = sum((_safe_mean(r, "layoff_count") or 0) for r in results)
    peak_monthly_layoffs = max(
        (_safe_mean(r, "layoff_count") or 0) for r in results
    ) if results else 0

    # ── Scenario type flags ────────────────────────────────────────────────────
    is_layoff_scenario      = layoff_ratio > 0 or total_layoffs > 0
    is_hiring_freeze        = not hiring and layoff_ratio == 0
    is_workload_reduction   = workload < 0.95
    is_workload_increase    = workload > 1.1
    is_extreme_crunch       = workload >= 1.4
    is_positive_policy      = workload <= 1.0 and wlb > 0 and layoff_ratio == 0
    is_compensation_focused = overtime > 0 and workload <= 1.1
    is_restructure          = shock > 0.3 and layoff_ratio == 0
    is_growth_phase         = hiring and workload >= 1.1 and layoff_ratio == 0

    # ── Layoff suppression warning ─────────────────────────────────────────────
    # When layoffs happen, voluntary attrition drops artificially.
    # People don't quit when they're scared of losing their job.
    # Lower voluntary attrition in a layoff scenario is NOT a positive signal.
    layoff_suppression_active = is_layoff_scenario and total_layoffs > 0

    # ── Human-readable policy translation ─────────────────────────────────────
    # Convert config floats to plain English for the LLM
    workload_meaning = (
        f"workload REDUCED by {round((1 - workload) * 100)}% — employees have less work"
        if workload < 0.95 else
        f"workload INCREASED by {round((workload - 1) * 100)}% — employees have more work"
        if workload > 1.05 else
        "workload unchanged (baseline)"
    )

    scenario_type = (
        "LAYOFF"           if is_layoff_scenario else
        "HIRING_FREEZE"    if is_hiring_freeze else
        "WORKLOAD_REDUCTION" if is_workload_reduction else
        "EXTREME_CRUNCH"   if is_extreme_crunch else
        "WORKLOAD_INCREASE" if is_workload_increase else
        "POSITIVE_POLICY"  if is_positive_policy else
        "COMPENSATION"     if is_compensation_focused else
        "RESTRUCTURE"      if is_restructure else
        "GROWTH"           if is_growth_phase else
        "GENERAL"
    )

    return {
        "scenario_type":             scenario_type,
        "is_layoff_scenario":        is_layoff_scenario,
        "is_hiring_freeze":          is_hiring_freeze,
        "is_workload_reduction":     is_workload_reduction,
        "is_workload_increase":      is_workload_increase,
        "is_extreme_crunch":         is_extreme_crunch,
        "is_positive_policy":        is_positive_policy,
        "is_compensation_focused":   is_compensation_focused,
        "is_restructure":            is_restructure,
        "is_growth_phase":           is_growth_phase,
        "layoff_suppression_active": layoff_suppression_active,
        "total_layoffs":             round(total_layoffs, 1),
        "peak_monthly_layoffs":      round(peak_monthly_layoffs, 1),
        "workload_meaning":          workload_meaning,
    }


def _compute_analytics(sim_result: dict, policy_config: dict | None) -> dict:
    """
    Pre-compute every analytical signal the LLM will need.
    Returns a rich analytics dict. No LLM involved.

    Computed signals:
      - Scenario classification (runs first — conditions everything else)
      - Per-metric: start, end, delta, pct_change, verdict, trajectory shape
      - Attrition: voluntary vs forced split, layoff-adjusted true loss rate
      - Stress: shape (monotone drop vs bounce), peak location
      - Burnout: total events, end-period burnout rate
      - Headcount: net change, velocity
      - Overall: composite health score, dominant risk driver
      - Baseline comparison: vs historical attrition
    """
    results  = sim_result.get("results", [])
    summary  = sim_result.get("summary", {})
    config   = policy_config or sim_result.get("config", {})

    if not results:
        return {"error": "No monthly results available"}

    start = results[0]
    end   = results[-1]
    n     = len(results)
    mid   = results[n // 2]

    # ── Step 0: Classify scenario FIRST — conditions all downstream logic ──────
    scenario = _classify_scenario(config, results)

    def metric_block(key: str, label: str, lower_is_better: bool = False) -> dict:
        s = _safe_mean(start, key)
        e = _safe_mean(end,   key)
        m = _safe_mean(mid,   key)
        if s is None or e is None:
            return {"label": label, "available": False}
        pct = _pct_change(s, e)

        # Shape: monotone, bounce, or plateau
        mid_val = m or ((s + e) / 2)
        if lower_is_better:
            if mid_val > max(s, e):
                shape = "peaked then recovered"
            elif s > mid_val > e:
                shape = "steadily improving"
            elif abs(pct) < 3:
                shape = "flat"
            else:
                shape = "improving" if pct < 0 else "worsening"
        else:
            if mid_val < min(s, e):
                shape = "dipped then recovered"
            elif s < mid_val < e:
                shape = "steadily improving"
            elif abs(pct) < 3:
                shape = "flat"
            else:
                shape = "improving" if pct > 0 else "worsening"

        return {
            "label":         label,
            "available":     True,
            "start":         round(s, 4),
            "mid":           round(mid_val, 4),
            "end":           round(e, 4),
            "abs_delta":     round(e - s, 4),
            "pct_change":    round(pct, 1),
            "verdict":       _trend_verdict(pct, lower_is_better),
            "shape":         shape,
            "lower_is_better": lower_is_better,
        }

    # ── Per-metric trajectory ──────────────────────────────────────────────────

    metrics = {
        "stress":       metric_block("avg_stress",           "Stress",            lower_is_better=True),
        "productivity": metric_block("avg_productivity",     "Productivity",      lower_is_better=False),
        "motivation":   metric_block("avg_motivation",       "Motivation",        lower_is_better=False),
        "satisfaction": metric_block("avg_job_satisfaction", "Job Satisfaction",  lower_is_better=False),
        "wlb":          metric_block("avg_work_life_balance","Work-Life Balance", lower_is_better=False),
        # NOTE: loyalty is computed by the simulation engine but excluded from
        # executive-facing analytics. The model's loyalty decay does not
        # accurately reflect real-world dynamics for flexibility/WLB policies.
    }

    # ── Attrition analysis ─────────────────────────────────────────────────────

    monthly_attr_rates = []
    for r in results:
        hc  = _safe_mean(r, "headcount")
        att = _safe_mean(r, "attrition_count")
        if hc and att and hc > 0:
            monthly_attr_rates.append({
                "month": r["month"],
                "rate_pct": round((att / hc) * 100, 3),
                "count": round(att, 1),
            })

    peak_attr = max(monthly_attr_rates, key=lambda x: x["rate_pct"]) if monthly_attr_rates else {}
    avg_monthly_attr = (
        sum(x["rate_pct"] for x in monthly_attr_rates) / len(monthly_attr_rates)
        if monthly_attr_rates else 0
    )

    # Acceleration: is attrition getting worse over time?
    if len(monthly_attr_rates) >= 4:
        first_half  = monthly_attr_rates[:n // 2]
        second_half = monthly_attr_rates[n // 2:]
        avg_first   = sum(x["rate_pct"] for x in first_half)  / len(first_half)
        avg_second  = sum(x["rate_pct"] for x in second_half) / len(second_half)
        attr_acceleration = round(avg_second - avg_first, 3)
        attr_trend = (
            "accelerating"   if attr_acceleration >  0.1 else
            "decelerating"   if attr_acceleration < -0.1 else
            "stable"
        )
    else:
        attr_acceleration = 0.0
        attr_trend = "unknown"

    # ── Stress shape analysis ──────────────────────────────────────────────────

    stress_vals  = [(_safe_mean(r, "avg_stress") or 0) for r in results]
    peak_stress  = max(stress_vals)
    peak_stress_month = results[stress_vals.index(peak_stress)]["month"]
    final_stress = stress_vals[-1]
    stress_pct_drop = round(_pct_change(stress_vals[0], final_stress), 1)

    # Did stress peak early and fall? Or did it build up over time?
    if peak_stress_month <= 2:
        stress_shape = "peaked at month 1 then steadily declined — policy had immediate calming effect"
    elif peak_stress_month >= n - 2:
        stress_shape = "built up throughout the period — policy increased chronic stress over time"
    else:
        stress_shape = f"peaked at month {peak_stress_month} then recovered — mid-period stress spike"

    # ── Healthy Worker Effect detection ────────────────────────────────────────
    # When workload INCREASES but avg stress DROPS, the most likely cause is NOT
    # genuine de-stressing — it's that the highest-stress employees quit first,
    # and new hires (starting at low stress) are diluting the population average.
    # This is the "healthy worker survival bias" and must be flagged so the LLM
    # does not present it as a positive policy outcome.
    total_voluntary_for_hwe = sum((_safe_mean(r, "attrition_count") or 0) for r in results)
    hwe_attrition_rate = (total_voluntary_for_hwe / max(hc_start, 1)) * 100 if 'hc_start' in dir() else 0
    healthy_worker_effect_warning = None
    if (
        scenario["is_workload_increase"]
        and stress_pct_drop < -1.0          # stress measurably dropped
        and total_voluntary_for_hwe > 20    # meaningful attrition occurred
    ):
        workload_pct = round((config.get("workload_multiplier", 1.0) - 1) * 100) if isinstance(config, dict) else 25
        healthy_worker_effect_warning = (
            f"HEALTHY WORKER EFFECT DETECTED: Workload INCREASED by {workload_pct}% "
            f"yet average stress DROPPED by {abs(stress_pct_drop):.1f}%. "
            f"This is NOT genuine de-stressing. "
            f"The most likely cause: {round(total_voluntary_for_hwe)} high-stress employees quit over the period "
            f"and were replaced by new hires who start with near-zero stress, "
            f"pulling the population AVERAGE down. "
            f"The REMAINING employees may be under increasing pressure. "
            f"Do NOT present this stress drop as a positive policy outcome. "
            f"Flag it as a population composition artifact."
        )

    # ── Burnout analysis ───────────────────────────────────────────────────────

    total_burnout = sum((_safe_mean(r, "burnout_count") or 0) for r in results)
    end_burnout   = _safe_mean(end, "burnout_count") or 0
    end_hc        = _safe_mean(end, "headcount") or 1
    burnout_rate_pct = round((end_burnout / end_hc) * 100, 2)

    # ── Headcount analysis ─────────────────────────────────────────────────────

    hc_start = _safe_mean(start, "headcount") or 0
    hc_end   = _safe_mean(end,   "headcount") or 0
    hc_net   = round(hc_end - hc_start, 1)
    hc_pct   = round(_pct_change(hc_start, hc_end), 2)

    # ── Layoff-adjusted true workforce loss ────────────────────────────────────
    # This is the fix for the "attrition illusion" bug:
    # When layoffs happen, voluntary quits drop (fear suppression).
    # annual_attrition_pct only counts voluntary exits.
    # True workforce loss = voluntary exits + forced layoffs.
    # We must compute this and flag it explicitly so the LLM cannot
    # praise improved voluntary attrition while ignoring forced exits.

    total_layoffs      = scenario["total_layoffs"]
    total_voluntary    = sum((_safe_mean(r, "attrition_count") or 0) for r in results)
    total_workforce_loss = total_voluntary + total_layoffs
    true_loss_rate_pct = round((total_workforce_loss / hc_start) * 100, 2) if hc_start > 0 else 0

    # Layoff as % of starting headcount
    layoff_pct_of_headcount = round((total_layoffs / hc_start) * 100, 2) if hc_start > 0 else 0

    # ── Layoff-adjusted voluntary rate (Fix 2) ────────────────────────────────
    # This is the voluntary attrition rate computed on the SURVIVOR pool only
    # (i.e., excluding the people who were already removed via layoff).
    # It surfaces the true voluntary quit pressure on remaining employees.
    # Why this matters for comparison correctness:
    #   A 24% cut leaves only 76% of workforce. Even if the SAME NUMBER of
    #   voluntary quits happens as in an 8% cut, the RATE per survivor is higher.
    #   This metric corrects for the denominator shrinkage so scenarios are
    #   comparable on a like-for-like basis.
    survivor_pool = max(hc_start - total_layoffs, 1)
    voluntary_rate_on_survivors = round((total_voluntary / survivor_pool) * 100, 2)

    # Fear suppression: did voluntary attrition drop in months WITH layoffs?
    # If yes, the lower quit rate is fear-driven, not satisfaction-driven.
    if scenario["is_layoff_scenario"] and total_layoffs > 0:
        layoff_ratio_actual = round(total_layoffs / max(hc_start, 1) * 100, 1)
        layoff_suppression_warning = (
            f"LAYOFF SUPPRESSION DETECTED: {total_layoffs:.0f} employees were forcibly laid off "
            f"({layoff_ratio_actual}% of starting headcount). "
            f"Voluntary attrition appears to be {summary.get('annual_attrition_pct', '?')}% annualised, "
            f"but this suppressed rate is fear-driven — remaining staff are afraid to quit. "
            f"This is NOT a retention improvement. "
            f"True workforce loss rate (voluntary + forced) is {true_loss_rate_pct}%. "
            f"Voluntary quit rate on SURVIVOR pool (excl. layoffs) is {voluntary_rate_on_survivors}%. "
            f"Do NOT praise the lower voluntary attrition rate in a layoff scenario. "
            f"IMPORTANT: A SMALLER layoff (e.g. 8%) may show a HIGHER voluntary attrition rate than "
            f"a LARGER layoff (e.g. 24%) because fewer people were removed from the at-risk pool "
            f"and survivors have less fear paralysis. This is the attrition INVERSION effect — "
            f"it does NOT mean the smaller layoff policy is worse. The true comparable metric is "
            f"true_loss_rate_pct (voluntary + forced combined), not voluntary rate alone."
        )
        # Build a human-readable fear suppression note for the prompt
        fear_suppression_note = (
            f"  ATTRITION INVERSION EXPLANATION:\n"
            f"  ⚠ Layoff size SUPPRESSES voluntary attrition — the BIGGER the layoff, the LOWER \n"
            f"    the voluntary quit rate appears. This is NOT an improvement.\n"
            f"  ⚠ A 24% cut removes {total_layoffs:.0f} at-risk employees from the quit pool AND\n"
            f"    creates fear paralysis in survivors. Both effects reduce voluntary exits.\n"
            f"  ⚠ An 8% cut keeps more at-risk employees in the pool AND has less fear paralysis,\n"
            f"    so it shows HIGHER voluntary attrition — but LOWER true workforce loss.\n"
            f"  ⚠ Do NOT interpret a lower voluntary rate as 'better retention' in any layoff scenario.\n"
            f"  ⚠ The CORRECT comparison metric is TRUE WORKFORCE LOSS RATE (voluntary + forced).\n"
            f"  ✓ Voluntary rate on survivor pool: {voluntary_rate_on_survivors}% (removes denominator bias)"
        )
        # Override attrition verdict — it cannot be "improving" if layoffs happened
        attrition_verdict_override = "deteriorating"
    else:
        layoff_suppression_warning = None
        fear_suppression_note = None
        attrition_verdict_override = None

    annual_attr      = summary.get("annual_attrition_pct", 0)
    baseline_attr    = summary.get("baseline_annual_attrition_pct", None)
    attr_vs_baseline = None
    attr_vs_verdict  = "unknown"
    if baseline_attr:
        attr_vs_baseline = round(annual_attr - baseline_attr, 2)
        if attr_vs_baseline < -2:
            attr_vs_verdict = "better than baseline"
        elif attr_vs_baseline > 2:
            attr_vs_verdict = "worse than baseline"
        else:
            attr_vs_verdict = "on par with baseline"

    # Override: layoff scenario always = deteriorating attrition, regardless of voluntary rate
    if attrition_verdict_override:
        attr_vs_verdict = "worse than baseline (layoff-adjusted)"

    # ── Dominant risk driver ───────────────────────────────────────────────────
    # Which metric is in the worst shape? Used to anchor the recommendation.

    risk_scores = {}
    for key, m in metrics.items():
        if not m.get("available"):
            continue
        v = m["verdict"]
        score = {
            "deteriorating":          3,
            "slightly deteriorating": 2,
            "stable":                 1,
            "slightly improving":     0,
            "improving":              0,
        }.get(v, 0)
        risk_scores[key] = score

    # If every metric is stable or improving (all scores == 0 or 1),
    # don't arbitrarily pick one as the "dominant risk" — it misleads the LLM.
    # Use a forward-looking risk label instead.
    max_risk_score = max(risk_scores.values()) if risk_scores else 0
    if max_risk_score <= 1:
        # All metrics are stable or better — anchor recommendation to attrition sustainability
        dominant_risk = "none"
        dominant_risk_label = "Attrition Sustainability"
    else:
        # At least one metric is deteriorating — pick the worst
        worst_keys = [k for k, v in risk_scores.items() if v == max_risk_score]
        dominant_risk = worst_keys[0]
        dominant_risk_label = metrics.get(dominant_risk, {}).get("label", "unknown")

    # ── Composite health score (0–100, higher = healthier org) ────────────────
    # Weighted average of metric verdicts

    weights = {
        "stress":       0.25,
        "attrition":    0.25,
        "motivation":   0.25,  # +0.05 from removed loyalty weight
        "productivity": 0.15,
        "wlb":          0.10,  # +0.05 from removed loyalty weight
    }
    verdict_score = {
        "improving":             100,
        "slightly improving":     75,
        "stable":                 50,
        "slightly deteriorating": 25,
        "deteriorating":           0,
    }

    # Attrition health: invert (lower attrition = better health)
    if baseline_attr:
        attr_health = max(0, min(100, 50 + (baseline_attr - annual_attr) * 5))
    else:
        attr_health = 50

    health_score = (
        weights["stress"]       * verdict_score.get(metrics["stress"]["verdict"], 50) +
        weights["attrition"]    * attr_health +
        weights["motivation"]   * verdict_score.get(metrics["motivation"]["verdict"], 50) +
        weights["productivity"] * verdict_score.get(metrics["productivity"]["verdict"], 50) +
        weights["wlb"]          * verdict_score.get(metrics["wlb"]["verdict"], 50)
    )
    health_label = (
        "healthy"     if health_score >= 70 else
        "mixed"       if health_score >= 45 else
        "at risk"     if health_score >= 25 else
        "critical"
    )

    # ── Assemble ───────────────────────────────────────────────────────────────

    return {
        "scenario":             scenario,
        "metrics":              metrics,
        "attrition": {
            "annual_pct":              annual_attr,
            "baseline_pct":            baseline_attr,
            "vs_baseline_pts":         attr_vs_baseline,
            "vs_baseline_verdict":     attr_vs_verdict,
            "avg_monthly_rate":        round(avg_monthly_attr, 3),
            "peak_month":              peak_attr.get("month"),
            "peak_rate_pct":           peak_attr.get("rate_pct"),
            "acceleration":            attr_acceleration,
            "trend":                   attr_trend,
            "total_voluntary_exits":   round(total_voluntary, 1),
            "total_layoffs":           round(total_layoffs, 1),
            "total_workforce_loss":    round(total_workforce_loss, 1),
            "true_loss_rate_pct":      true_loss_rate_pct,
            "layoff_pct_of_headcount": layoff_pct_of_headcount,
            # Voluntary rate recalculated on the survivor pool (excludes layoffs from denominator)
            # This is the like-for-like metric for comparing across different layoff sizes.
            "voluntary_rate_on_survivors": voluntary_rate_on_survivors,
            "layoff_suppression_warning": layoff_suppression_warning,
            "fear_suppression_note":   fear_suppression_note,
            "attrition_verdict_override": attrition_verdict_override,
        },
        "stress_shape":         stress_shape,
        "stress_peak":          round(peak_stress, 4),
        "stress_peak_month":    peak_stress_month,
        "stress_pct_change":    stress_pct_drop,
        "healthy_worker_effect_warning": healthy_worker_effect_warning,
        "burnout": {
            "total_events":      round(total_burnout, 1),
            "end_period_count":  round(end_burnout, 1),
            "end_period_rate_pct": burnout_rate_pct,
        },
        "headcount": {
            "start":  round(hc_start),
            "end":    round(hc_end),
            "net":    round(hc_net),
            "pct_change": hc_pct,
        },
        "dominant_risk":        dominant_risk_label,
        "health_score":         round(health_score, 1),
        "health_label":         health_label,
        "realism_flag":         summary.get("realism_flag", "unknown"),
        "policy_name":          summary.get("policy_name", "unknown"),
        "duration_months":      summary.get("duration_months", 12),
        "runs":                 sim_result.get("runs", "?"),
        "config":               config,
    }


# ── Prompt Builder ─────────────────────────────────────────────────────────────

def _build_prompt(analytics: dict, user_intent: str | None) -> str:
    """
    Build the LLM prompt using pre-computed analytics.
    The LLM receives verdicts, directions, scenario context, and explicit
    warnings — not raw numbers to interpret.
    Its job is to write narrative, not do math or classify scenarios.
    """
    m    = analytics["metrics"]
    att  = analytics["attrition"]
    hc   = analytics["headcount"]
    bur  = analytics["burnout"]
    sc   = analytics["scenario"]

    def fmt_metric(key: str) -> str:
        mm = m.get(key, {})
        if not mm.get("available"):
            return f"  {key}: data unavailable"
        arrow = "✓" if mm["verdict"] in ("improving", "slightly improving") else (
                "✗" if mm["verdict"] in ("deteriorating", "slightly deteriorating") else "~"
        )
        return (
            f"  {arrow} {mm['label']:20s}: {mm['start']:.4f} → {mm['end']:.4f}  "
            f"({mm['pct_change']:+.1f}%)  [{mm['verdict'].upper()}]  shape: {mm['shape']}"
        )

    lines = [
        "SIMULATION ANALYTICS BRIEF",
        "=" * 60,
        "",
        f"ORIGINAL USER REQUEST  : {user_intent or 'Not specified'}",
        f"POLICY NAME            : {analytics['policy_name']}",
        f"DURATION               : {analytics['duration_months']} months",
        f"MONTE CARLO RUNS       : {analytics['runs']}",
        f"REALISM CHECK          : {analytics['realism_flag']}",
        f"ORG HEALTH SCORE       : {analytics['health_score']:.1f}/100 ({analytics['health_label'].upper()})",
        "",

        # ── SCENARIO CONTEXT (most important block — sets the mental model) ──
        "── SCENARIO CLASSIFICATION ──────────────────────────────────",
        f"  Type                 : {sc['scenario_type']}",
        f"  Workload meaning     : {sc['workload_meaning']}",
        f"  Layoff scenario      : {'YES' if sc['is_layoff_scenario'] else 'NO'}",
        f"  Workload reduction   : {'YES' if sc['is_workload_reduction'] else 'NO'}",
        f"  Workload increase    : {'YES' if sc['is_workload_increase'] else 'NO'}",
        f"  Positive policy      : {'YES' if sc['is_positive_policy'] else 'NO'}",
        f"  Growth phase         : {'YES' if sc['is_growth_phase'] else 'NO'}",
        "",
        "  SCENARIO READING RULES — follow these for this specific scenario:",
    ]

    # Conditional interpretation rules per scenario type
    if sc["is_layoff_scenario"]:
        lines += [
            "  ⚠ LAYOFF SCENARIO: Lower voluntary attrition is NOT good news.",
            "    People are not quitting because they are AFRAID of losing their job.",
            "    This is fear-driven suppression, not satisfaction-driven retention.",
            "    You MUST report the TRUE workforce loss (voluntary + layoffs combined).",
            "    NEVER praise improved voluntary attrition in a layoff scenario.",
            "    The attrition verdict is OVERRIDDEN to DETERIORATING.",
        ]
    elif sc["is_workload_reduction"]:
        lines += [
            "  ✓ WORKLOAD REDUCTION SCENARIO: Stress dropping is EXPECTED and POSITIVE.",
            "    Do not treat stress decline as surprising or coincidental.",
            "    The policy directly caused the stress reduction — acknowledge this.",
            "    If attrition also improved, credit the workload reduction directly.",
        ]
    elif sc["is_extreme_crunch"]:
        lines += [
            "  ✗ EXTREME CRUNCH SCENARIO: Workload is at crisis level.",
            "    Any stress increase is directly caused by the workload policy.",
            "    Do NOT suggest generic wellness programs — fix the workload first.",
            "    Burnout and attrition acceleration are the primary risks to flag.",
        ]
    elif sc["is_workload_increase"]:
        lines += [
            "  ⚠ WORKLOAD INCREASE SCENARIO: Elevated stress is expected.",
            "    Assess whether compensation or WLB improvements offset the load.",
            "    If stress is high AND morale is low — policy is backfiring.",
        ]
    elif sc["is_positive_policy"]:
        lines += [
            "  ✓ POSITIVE POLICY SCENARIO: Expect improvements across most metrics.",
            "    If any metric is still deteriorating, that is the key risk to flag.",
            "    Do NOT recommend reversing a policy that is delivering improvements.",
        ]
    elif sc["is_hiring_freeze"]:
        lines += [
            "  ⚠ HIRING FREEZE SCENARIO: Workload creep is the primary risk.",
            "    Remaining employees absorb the work of unfilled roles.",
            "    Monitor productivity and stress for early burnout signals.",
        ]

    lines += [""]

    # ── LAYOFF SUPPRESSION WARNING (injected as a hard alert if present) ──────
    if att.get("layoff_suppression_warning"):
        lines += [
            "── ⚠ CRITICAL LAYOFF SUPPRESSION WARNING ──────────────────────",
            f"  {att['layoff_suppression_warning']}",
            f"  Total voluntary exits          : {att['total_voluntary_exits']:.0f}",
            f"  Total forced layoffs           : {att['total_layoffs']:.0f}",
            f"  TRUE total workforce loss      : {att['total_workforce_loss']:.0f} people ({att['true_loss_rate_pct']}% of headcount)",
            f"  Layoffs as % of headcount      : {att['layoff_pct_of_headcount']}%",
            f"  Voluntary rate on SURVIVOR pool: {att.get('voluntary_rate_on_survivors', 'N/A')}%  ← use this for cross-scenario comparisons",
            "  The briefing MUST lead with the true workforce loss, not the voluntary rate.",
        ]
        if att.get("fear_suppression_note"):
            lines += [
                "",
                att["fear_suppression_note"],
            ]
        lines.append("")

    # ── POLICY PARAMETERS (translated to plain English) ─────────────────────────────────────────
    config = analytics["config"]
    lines += [
        "── POLICY PARAMETERS (plain English translation) ────────────",
        f"  {sc['workload_meaning']}",
    ]
    if config.get("layoff_ratio", 0):
        lines.append(f"  Layoffs          : {config['layoff_ratio']*100:.0f}% of workforce laid off")
    if config.get("wlb_boost", 0):
        lines.append(f"  WLB boost        : +{config['wlb_boost']} points — schedule/flexibility improvement")
    if config.get("bonus", 0):
        # Map the internal bonus float to an overtime premium description
        bonus_val = config['bonus']
        if bonus_val >= 2.0:
            pay_approx = "~1.5x–2x overtime rate (intensive mandatory overtime compensation)"
        elif bonus_val >= 1.0:
            pay_approx = "~10–15% overtime premium (moderate extra pay for extra work)"
        else:
            pay_approx = "~5–10% overtime supplement (partial compensation for extra load)"
        lines.append(f"  Overtime pay     : {bonus_val} [{pay_approx}] — employees compensated for extra workload")
        lines.append(f"  NOTE: This is OVERTIME PAY tied to the workload increase, not a general salary raise.")
        lines.append(f"  It partially offsets the stress of more work, but is transactional — not a retention signal like a permanent raise.")
    if not config.get("hiring_active", True):
        lines.append("  Hiring           : FROZEN — no backfill for exits")
    if config.get("shock_factor", 0) > 0.3:
        lines.append(f"  Peer contagion   : HIGH ({config['shock_factor']}) — departures trigger further exits")
    lines.append("")

    # ── HEADCOUNT ───────────────────────────────────────────────────────────────────
    lines += [
        "── HEADCOUNT ──────────────────────────────────────────────────",
        f"  Start : {hc['start']} employees",
        f"  End   : {hc['end']} employees",
        f"  Net   : {hc['net']:+.0f} employees ({hc['pct_change']:+.1f}%)",
    ]
    if att.get("total_layoffs", 0) > 0:
        lines.append(f"  Of which {att['total_layoffs']:.0f} were FORCED LAYOFFS — not voluntary exits")
    lines.append("")

    # ── ATTRITION ───────────────────────────────────────────────────────────────────
    lines += [
        "── ATTRITION ──────────────────────────────────────────────────",
        f"  Voluntary attrition (this scenario) : {att['annual_pct']:.2f}% annualised",
        f"  Historical baseline (actual)         : {att['baseline_pct']}%",
        f"  Difference vs baseline               : {att['vs_baseline_pts']:+.2f} pts  [{att['vs_baseline_verdict'].upper()}]",
    ]
    if att.get("true_loss_rate_pct", 0) != att.get("annual_pct", 0):
        lines += [
            f"  TRUE workforce loss rate (incl. layoffs)  : {att['true_loss_rate_pct']}%",
            f"  Voluntary rate on SURVIVOR pool (bias-free): {att.get('voluntary_rate_on_survivors', 'N/A')}%",
            f"  ← USE TRUE LOSS RATE in your situation summary, NOT the voluntary rate.",
            f"  ← Survivor-pool rate removes denominator bias — use it for cross-scenario comparisons.",
        ]
        if att.get("fear_suppression_note"):
            lines += [
                "",
                att["fear_suppression_note"],
                "",
            ]
    lines += [
        f"  Average monthly attrition rate       : {att['avg_monthly_rate']:.3f}%/month",
        f"  Peak attrition month                 : Month {att['peak_month']} ({att['peak_rate_pct']:.2f}%)",
        f"  Attrition trend over period          : {att['trend'].upper()}",
        "",
    ]

    # ── METRIC TRAJECTORIES ───────────────────────────────────────────────────
    lines += [
        "── METRIC TRAJECTORIES (Python-computed — trust these) ──────",
        "  Verdicts are pre-computed from start→end delta. Do NOT override them.",
        "",
    ]
    for key in ["stress", "productivity", "motivation", "satisfaction", "wlb"]:
        lines.append(fmt_metric(key))

    # ── STRESS DEEP DIVE ──────────────────────────────────────────────────────
    stress_end = m["stress"]["end"]
    lines += [
        "",
        "── STRESS DEEP DIVE ─────────────────────────────────────────",
        f"  Peak stress value    : {analytics['stress_peak']:.4f}  at month {analytics['stress_peak_month']}",
        f"  Final stress value   : {stress_end:.4f}",
        f"  Total stress change  : {analytics['stress_pct_change']:+.1f}%",
        f"  Stress shape         : {analytics['stress_shape']}",
        "  SCALE                : Stress > 0.15 = high risk | 0.05–0.15 = elevated | < 0.05 = healthy",
        f"  VERDICT              : Final stress {stress_end:.4f} is "
        f"{'HEALTHY' if stress_end < 0.05 else 'ELEVATED' if stress_end < 0.15 else 'HIGH RISK'}",
    ]

    # Inject healthy worker effect warning right after the stress verdict
    hwe = analytics.get("healthy_worker_effect_warning")
    if hwe:
        lines += [
            "",
            "  ⚠ HEALTHY WORKER EFFECT WARNING:",
            f"  {hwe}",
            "  ─────────────────────────────────────────────────────────────",
            "  INSTRUCTION: In your briefing, do NOT say 'stress improved' or 'stress dropped'.",
            "  Instead say something like: 'Average stress appears lower, but this reflects",
            "  workforce composition change — high-stress employees left and new hires",
            "  diluted the average. The underlying workload pressure remains unresolved.'",
        ]
    lines.append("")

    # ── BURNOUT ───────────────────────────────────────────────────────────────
    lines += [
        "── BURNOUT ──────────────────────────────────────────────────",
        f"  Total burnout events over period : {bur['total_events']:.0f}",
        f"  End-period burnout count         : {bur['end_period_count']:.0f}",
        f"  End-period burnout rate          : {bur['end_period_rate_pct']:.2f}% of workforce",
        f"  VERDICT : {'CRITICAL (>10%)' if bur['end_period_rate_pct'] > 10 else 'ELEVATED (5-10%)' if bur['end_period_rate_pct'] > 5 else 'NONE DETECTED'}",
        "",
    ]

    # ── INTERPRETATION GUIDE ──────────────────────────────────────────────────
    lines += [
        "── INTERPRETATION GUIDE ─────────────────────────────────────",
        "  Stress        : 0.0–0.05 healthy | 0.05–0.15 elevated | 0.15+ high risk",
        "  Productivity  : 0.9–1.0 normal | below 0.85 = productivity crisis",
        "  Motivation    : 0.5–0.7 normal | below 0.4 = disengagement risk",
        "  Satisfaction  : scale 1–5 | below 2.5 = dissatisfied | above 3.5 = satisfied",
        "  WLB           : scale 1–5 | below 2.5 = poor | above 3.5 = good",
        "  Attrition     : <10% healthy | 10–20% moderate | 20–30% concerning | 30%+ crisis",
        "",
    ]

    # ── DOMINANT RISK AND TASK ────────────────────────────────────────────────
    dominant_risk_label = analytics['dominant_risk']
    is_all_healthy = dominant_risk_label == "Attrition Sustainability"

    lines += [
        "── DOMINANT RISK DRIVER ─────────────────────────────────────",
    ]
    if is_all_healthy:
        lines += [
            "  ✓ No metric is in a deteriorating state.",
            "  All key indicators are STABLE or IMPROVING.",
            "  The forward-looking risk is: Attrition Sustainability.",
            "  Focus the recommendation on sustaining the current positive trajectory.",
            "  Do NOT invent risks or suggest the policy is problematic — the data says it is working.",
        ]
    else:
        lines += [
            f"  {dominant_risk_label} is the metric in worst shape.",
            "  Anchor risks and recommendation to this first.",
        ]
    lines.append("")

    lines += [
        "── YOUR TASK ────────────────────────────────────────────────",
        "  Write a CEO executive briefing using ONLY the analytics above.",
        "  Follow the SCENARIO READING RULES at the top of this brief.",
        "  The verdicts are pre-computed — do NOT contradict them.",
        f"  Stress verdict: {m['stress']['verdict'].upper()} "
        f"({'dropped' if analytics['stress_pct_change'] < 0 else 'rose'} "
        f"{abs(analytics['stress_pct_change']):.1f}% — "
        f"{'POSITIVE' if analytics['stress_pct_change'] < 0 else 'NEGATIVE'}).",
    ]

    if att.get("layoff_suppression_warning"):
        lines += [
            "  ⚠ LAYOFF SCENARIO: Report TRUE workforce loss in situation summary.",
            "  ⚠ Do NOT praise voluntary attrition improvement. It is fear suppression.",
            "  ⚠ Attrition verdict is OVERRIDDEN to DETERIORATING.",
        ]
    elif sc["is_workload_reduction"]:
        lines.append("  ✓ Stress drop is expected and positive — credit the workload reduction.")
    elif is_all_healthy and config.get("bonus", 0) > 0:
        lines.append("  ✓ Pay increase is actively buffering workload stress — acknowledge this explicitly in the briefing.")

    lines.append("  Recommendation must address the DOMINANT RISK DRIVER.")

    return "\n".join(lines)


# ── System Prompt ──────────────────────────────────────────────────────────────

REASONING_SYSTEM_PROMPT = """You are a senior HR analytics advisor presenting simulation results to a CEO.

You will receive pre-computed analytics from an agent-based Monte Carlo simulation.
The verdicts (improving / stable / deteriorating) are mathematically computed — do NOT override them.
Your job is to write the narrative, identify risks, and give concrete recommendations.

STRICT RULES:
1. Never contradict a pre-computed verdict. If stress verdict is IMPROVING, do not call it deteriorating.
2. Never recommend reversing a policy that improved the key outcomes.
3. Always anchor recommendations to the DOMINANT RISK DRIVER field.
4. Be specific with meaningful numbers (Headcount, Attrition %). However, DO NOT output raw internal decimals for abstract engine physics like Stress or Motivation (e.g., never say 'dropped to 0.0053'). Translate those abstract decimals into English using the Interpretation Guide (e.g., 'dropped to a healthy baseline' or 'escalated to high risk').
5. Tone: direct, professional, no jargon, no hedging. 5-minute read.

Return ONLY a valid JSON object. No markdown. No text outside JSON.

Required structure:
{
  "situation": "2-3 sentences: what happened, what drove it, is it good or bad overall.",
  "performance": {
    "attrition_verdict":    "improving | stable | deteriorating",
    "stress_verdict":       "improving | stable | deteriorating",
    "morale_verdict":       "improving | stable | deteriorating",
    "productivity_verdict": "improving | stable | deteriorating",
    "one_line": "Single verdict sentence e.g. 'Strong overall improvement with one area of concern.'"
  },
  "comparison": "2 sentences comparing annualised attrition to the historical baseline. Use exact numbers.",
  "risks": [
    {"title": "Short title", "severity": "high | medium | low", "detail": "1-2 sentences on what drives this risk and its consequence."},
    {"title": "...", "severity": "...", "detail": "..."},
    {"title": "...", "severity": "...", "detail": "..."}
  ],
  "recommendation": "3-4 sentences. Concrete actions. Must address dominant risk. End with a time horizon.",
  "confidence": "high | medium | low",
  "confidence_reason": "One sentence: why this confidence level given data quality and simulation parameters."
}

SEVERITY GUIDE:
  high   : attrition > 25% OR stress > 0.15 OR burnout > 10%
  medium : attrition 15-25% OR stress 0.08-0.15 OR motivation deteriorating
  low    : attrition < 15% AND stress < 0.08 AND no burnout

MORALE VERDICT:
  Derive from motivation + satisfaction + work-life balance combined.
  If 2 of 3 are improving or stable → stable or improving.
  If 2 of 3 are deteriorating → deteriorating.

Always produce exactly 3 risks. If the scenario is mostly positive, the third risk can be forward-looking (e.g. 'risk of complacency' or 'dependency on this policy continuing').
"""


# ── Output Validator ───────────────────────────────────────────────────────────

def _validate_briefing(briefing: dict, analytics: dict) -> dict:
    """
    Post-process the LLM output.
    Correct any verdict that directly contradicts Python-computed analytics.
    Enforce scenario-specific overrides.
    Ensure required fields exist and risk count is exactly 3.
    """
    VALID_VERDICTS = {"improving", "stable", "deteriorating"}

    perf = briefing.get("performance", {})
    att  = analytics["attrition"]
    sc   = analytics["scenario"]

    # ── Enforce stress verdict ─────────────────────────────────────────────────
    computed_stress = analytics["metrics"]["stress"]["verdict"]
    simplified_stress = (
        "improving"     if "improving" in computed_stress else
        "deteriorating" if "deteriorating" in computed_stress else
        "stable"
    )
    if perf.get("stress_verdict") != simplified_stress:
        perf["stress_verdict"] = simplified_stress
        perf["_stress_corrected"] = True

    # ── Enforce attrition verdict ──────────────────────────────────────────────
    # LAYOFF GUARD: if layoffs happened, attrition is ALWAYS deteriorating.
    # The LLM must not praise lower voluntary attrition when forced exits happened.
    if att.get("attrition_verdict_override"):
        if perf.get("attrition_verdict") != "deteriorating":
            perf["attrition_verdict"] = "deteriorating"
            perf["_attrition_override_reason"] = (
                f"Layoff suppression: {att['total_layoffs']:.0f} forced exits detected. "
                f"True workforce loss is {att['true_loss_rate_pct']}%. "
                f"Voluntary attrition improvement is fear-driven, not retention-driven."
            )
    else:
        # Normal case: derive from baseline comparison
        computed_attr = (
            "improving"     if att["vs_baseline_verdict"] == "better than baseline" else
            "deteriorating" if "worse" in att["vs_baseline_verdict"] else
            "stable"
        )
        if perf.get("attrition_verdict") not in VALID_VERDICTS:
            perf["attrition_verdict"] = computed_attr

    # ── Enforce productivity verdict ───────────────────────────────────────────
    computed_prod = analytics["metrics"]["productivity"]["verdict"]
    simplified_prod = (
        "improving"     if "improving" in computed_prod else
        "deteriorating" if "deteriorating" in computed_prod else
        "stable"
    )
    if perf.get("productivity_verdict") not in VALID_VERDICTS:
        perf["productivity_verdict"] = simplified_prod

    # ── Workload crunch guard ──────────────────────────────────────────────────
    # If this is an extreme crunch scenario, recommendations must not be generic wellness tips.
    # Flag it so the caller can check.
    if sc.get("is_extreme_crunch"):
        perf["_crunch_scenario"] = True

    briefing["performance"] = perf

    # ── Ensure exactly 3 risks ─────────────────────────────────────────────────
    risks = briefing.get("risks", [])
    while len(risks) < 3:
        risks.append({
            "title":    "Continued monitoring required",
            "severity": "low",
            "detail":   (
                "Validate simulation outcomes against real workforce data after 60 days. "
                "Confidence increases with more Monte Carlo runs and longer observation periods."
            )
        })
    briefing["risks"] = risks[:3]

    # ── Ensure required top-level fields ──────────────────────────────────────
    for field in ["situation", "comparison", "recommendation", "confidence", "confidence_reason"]:
        if field not in briefing:
            briefing[field] = "Data unavailable — rerun simulation."

    return briefing


# ── Main Entry Point ───────────────────────────────────────────────────────────

def run_reasoning_chain(
    sim_result:    dict,
    policy_config: dict | None = None,
    user_intent:   str  | None = None,
) -> dict:
    """
    Run the CEO reasoning chain over a completed simulation result.

    Parameters
    ----------
    sim_result    : full dict returned by run_monte_carlo()
    policy_config : the SimulationConfig.__dict__ used for the run (optional)
    user_intent   : original plain-English policy text the user entered

    Returns
    -------
    Structured dict with CEO briefing + analytics + metadata
    """

    # Step 1: Python computes everything
    analytics = _compute_analytics(sim_result, policy_config)
    if "error" in analytics:
        return {"error": analytics["error"], "generated_at": datetime.now(timezone.utc).isoformat()}

    # Step 2: Build enriched prompt
    prompt = _build_prompt(analytics, user_intent)

    messages = [
        {"role": "system", "content": REASONING_SYSTEM_PROMPT},
        {"role": "user",   "content": prompt},
    ]

    groq_api_key = os.getenv("GROQ_API_KEY")
    raw_json = None

    # Step 3: Call LLM — Groq first, Ollama fallback
    # NOTE: Use llama-3.3-70b-versatile or llama3-70b-8192 on Groq.
    # The 8b model is too small for reliable structured reasoning.
    # Check your Groq console at console.groq.com for available models.

    try:
        if not groq_api_key:
            raise ValueError("No GROQ_API_KEY — falling back to local Ollama.")

        client = OpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=groq_api_key,
        )
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",   # ← upgrade from 8b-instant
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.15,   # low temp = consistent structured output
            max_tokens=1200,
        )
        raw_json = json.loads(response.choices[0].message.content)

    except Exception as e:
        print(f"[reasoning] Groq failed: {e}. Falling back to local Ollama.")
        try:
            local_client = OpenAI(
                base_url="http://localhost:11434/v1",
                api_key="ollama",
            )
            response = local_client.chat.completions.create(
                model="llama3.1:8b",
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.15,
                max_tokens=1200,
            )
            raw_json = json.loads(response.choices[0].message.content)
        except Exception as fallback_e:
            raise RuntimeError(
                f"Both Groq and Ollama failed. Ollama error: {fallback_e}"
            )

    # Step 4: Validate and correct LLM output
    briefing = _validate_briefing(raw_json, analytics)

    # Step 5: Return with full metadata
    return {
        "briefing":   briefing,
        "analytics":  analytics,    # expose pre-computed analytics for frontend use
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
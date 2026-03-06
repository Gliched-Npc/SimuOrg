# backend/simulation/monte_carlo.py

import copy
import json
import os
import numpy as np
from backend.simulation.time_engine import run_simulation, load_agents_from_db
from backend.simulation.org_graph import build_org_graph
from backend.simulation.policies import SimulationConfig


def run_monte_carlo(config: SimulationConfig, runs: int = 50, policy_name: str = "custom") -> dict:
    """
    Run simulation multiple times and aggregate results.
    Returns mean, min, max, std for each metric across all runs.
    """
    print(f"=== Running Monte Carlo: {runs} simulations - Policy: {policy_name.upper()}")

    # Load once, deepcopy per run for speed and consistency
    base_agents = load_agents_from_db()
    

    all_logs = []
    all_summaries = []

    for i in range(runs):
        print(f"   Run {i+1}/{runs}...", end="\r")
        agents_copy = copy.deepcopy(base_agents)
        G_copy = build_org_graph(agents_copy)
        result      = run_simulation(config, agents=agents_copy, G=G_copy, policy_name=policy_name)
        all_logs.append(result["logs"])
        all_summaries.append(result.get("summary", {}))

    print(f"\n[done] Monte Carlo complete.")

    # Aggregate across runs for each month
    duration   = len(all_logs[0]) if all_logs else 0
    aggregated = []

    for month_idx in range(duration):
        month_data = [run[month_idx] for run in all_logs]

        def stat(key):
            values = [m[key] for m in month_data]
            return {
                "mean": round(float(np.mean(values)), 4),
                "min":  round(float(np.min(values)),  4),
                "max":  round(float(np.max(values)),  4),
                "std":  round(float(np.std(values)),  4),
            }

        aggregated.append({
            "month"                : month_idx + 1,
            "headcount"            : stat("headcount"),
            "attrition_count"      : stat("attrition_count"),
            "layoff_count"         : stat("layoff_count"),
            "avg_stress"           : stat("avg_stress"),
            "avg_productivity"     : stat("avg_productivity"),
            "avg_motivation"       : stat("avg_motivation"),
            "burnout_count"        : stat("burnout_count"),
            "avg_job_satisfaction" : stat("avg_job_satisfaction"),
            "avg_work_life_balance": stat("avg_work_life_balance"),
            "avg_loyalty"          : stat("avg_loyalty"),
        })

    # --- Executive / domain-level summary ---
    if aggregated:
        initial_headcount = aggregated[0]["headcount"]["mean"]
        final_headcount   = aggregated[-1]["headcount"]["mean"]
        # Estimate period quits as the sum of mean monthly quits across runs.
        total_quits_est   = sum(m["attrition_count"]["mean"] for m in aggregated)
        period_months     = config.duration_months
        if initial_headcount > 0:
            period_attrition_pct = total_quits_est / initial_headcount * 100.0
            annual_attrition_pct = period_attrition_pct * (12.0 / period_months) if period_months > 0 else period_attrition_pct
        else:
            period_attrition_pct = 0.0
            annual_attrition_pct = 0.0

        # Load calibration, if available, to anchor realism check.
        calibration_path = "backend/ml/exports/calibration.json"
        baseline_annual_attrition = None
        if os.path.exists(calibration_path):
            try:
                with open(calibration_path) as f:
                    cal = json.load(f)
                baseline_annual_attrition = float(cal.get("annual_attrition_rate", 0.0)) * 100.0
            except Exception:
                baseline_annual_attrition = None

        # Simple realism flag for leadership: is this within a plausible HR range?
        realism_flag = "plausible"
        if annual_attrition_pct < 3.0 or annual_attrition_pct > 40.0:
            realism_flag = "implausible"

        # Short narrative for CEOs/Directors
        start = aggregated[0]
        end   = aggregated[-1]
        delta_stress = end["avg_stress"]["mean"] - start["avg_stress"]["mean"]
        delta_wlb    = end["avg_work_life_balance"]["mean"] - start["avg_work_life_balance"]["mean"]
        delta_jobsat = end["avg_job_satisfaction"]["mean"] - start["avg_job_satisfaction"]["mean"]

        narrative = (
            f"Over {period_months} months under the '{policy_name}' scenario, "
            f"average headcount moves from {initial_headcount:.0f} to {final_headcount:.0f}, "
            f"with an implied annual attrition of ~{annual_attrition_pct:.1f}%. "
            f"Average stress changes by {delta_stress:+.2f}, job satisfaction by {delta_jobsat:+.2f}, "
            f"and work-life balance by {delta_wlb:+.2f} points."
        )
        if baseline_annual_attrition is not None:
            diff = annual_attrition_pct - baseline_annual_attrition
            narrative += f" This is {diff:+.1f} pts versus the observed historical attrition (~{baseline_annual_attrition:.1f}%)."

        executive_summary = {
            "policy_name": policy_name,
            "duration_months": period_months,
            "initial_headcount": round(float(initial_headcount), 2),
            "final_headcount": round(float(final_headcount), 2),
            "period_attrition_pct": round(float(period_attrition_pct), 2),
            "annual_attrition_pct": round(float(annual_attrition_pct), 2),
            "realism_flag": realism_flag,
            "baseline_annual_attrition_pct": round(float(baseline_annual_attrition), 2) if baseline_annual_attrition is not None else None,
            "narrative": narrative,
        }
    else:
        executive_summary = {
            "policy_name": policy_name,
            "duration_months": config.duration_months,
            "initial_headcount": 0,
            "final_headcount": 0,
            "period_attrition_pct": 0.0,
            "annual_attrition_pct": 0.0,
            "realism_flag": "unknown",
            "baseline_annual_attrition_pct": None,
            "narrative": "No simulation data available.",
        }

    return {
        "config" : config.__dict__,
        "runs"   : runs,
        "results": aggregated,
        "summary": executive_summary,
    }


if __name__ == "__main__":
    from backend.simulation.policies import get_policy

    config  = get_policy("baseline")
    results = run_monte_carlo(config, runs=10)

    print("\n=== Month 12 Summary (across 10 runs):")
    m12 = results["results"][11]
    for key, val in m12.items():
        if key != "month":
            print(f"   {key}: mean={val['mean']} | min={val['min']} | max={val['max']}")
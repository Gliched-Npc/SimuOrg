# backend/simulation/monte_carlo.py

import copy
import numpy as np
from backend.simulation.time_engine import run_simulation, load_agents_from_db
from backend.simulation.org_graph import build_org_graph
from backend.simulation.policies import SimulationConfig


def run_monte_carlo(config: SimulationConfig, runs: int = 50, policy_name: str = "custom") -> dict:
    """
    Run simulation multiple times and aggregate results.
    Returns mean, min, max, std for each metric across all runs.
    """
    print(f"🎲 Running Monte Carlo: {runs} simulations — Policy: {policy_name.upper()}")

    # Load once, deepcopy per run for speed and consistency
    base_agents = load_agents_from_db()
    base_G      = build_org_graph(base_agents)

    all_logs = []

    for i in range(runs):
        print(f"   Run {i+1}/{runs}...", end="\r")
        agents_copy = copy.deepcopy(base_agents)
        G_copy      = copy.deepcopy(base_G)
        result      = run_simulation(config, agents=agents_copy, G=G_copy, policy_name=policy_name)
        all_logs.append(result["logs"])

    print(f"\n✅ Monte Carlo complete.")

    # Aggregate across runs for each month
    duration   = len(all_logs[0])
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

    return {
        "config" : config.__dict__,
        "runs"   : runs,
        "results": aggregated,
    }


if __name__ == "__main__":
    from backend.simulation.policies import get_policy

    config  = get_policy("baseline")
    results = run_monte_carlo(config, runs=10)

    print("\n📊 Month 12 Summary (across 10 runs):")
    m12 = results["results"][11]
    for key, val in m12.items():
        if key != "month":
            print(f"   {key}: mean={val['mean']} | min={val['min']} | max={val['max']}")
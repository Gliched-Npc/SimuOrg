# backend/simulation/monte_carlo.py

import copy

import numpy as np

from backend.core.simulation.org_graph import build_org_graph
from backend.core.simulation.policies import SimulationConfig
from backend.core.simulation.time_engine import load_agents_from_db, run_simulation


def run_monte_carlo(
    config: SimulationConfig,
    runs: int = 50,
    policy_name: str = "custom",
    seed: int = 42,
    session_id: str = "global",
) -> dict:
    """
    Run simulation multiple times and aggregate results.
    Returns mean, min, max, std for each metric across all runs.
    """
    print(f"=== Running Monte Carlo: {runs} simulations - Policy: {policy_name.upper()}")

    # Load once — used as the immutable base for ALL runs
    base_agents = load_agents_from_db(session_id=session_id)

    # Build org graph ONCE from base agents, then deepcopy it per run.
    # Previously deepcopy(base_agents) produced new object ids, breaking the
    # _cached_template_graph key, so build_org_graph rebuilt 69k edges on
    # every single run. Building once and copying the graph object is ~50x faster.
    base_G = build_org_graph(base_agents)

    all_logs = []
    all_summaries = []

    for i in range(runs):
        print(f"   Run {i+1}/{runs}...", end="\r")
        agents_copy = copy.deepcopy(base_agents)
        G_copy = copy.deepcopy(base_G)

        # Re-wire graph node agent references to the copied agents so the
        # behavior engine reads the copied state, not the base state.
        id_to_copy = {a.employee_id: a for a in agents_copy}
        for node_id in G_copy.nodes():
            if node_id in id_to_copy:
                G_copy.nodes[node_id]["agent"] = id_to_copy[node_id]

        result = run_simulation(
            config,
            agents=agents_copy,
            G=G_copy,
            policy_name=policy_name,
            seed=seed + i,
            session_id=session_id,
        )
        all_logs.append(result["logs"])
        all_summaries.append(result.get("summary", {}))

    print("\n[done] Monte Carlo complete.")

    # Aggregate across runs for each month
    duration = len(all_logs[0]) if all_logs else 0
    aggregated = []

    for month_idx in range(duration):
        month_data = [run[month_idx] for run in all_logs]

        def stat(key):
            values = [m[key] for m in month_data]
            return {
                "mean": round(float(np.mean(values)), 4),
                "min": round(float(np.min(values)), 4),
                "max": round(float(np.max(values)), 4),
                "std": round(float(np.std(values)), 4),
            }

        aggregated.append(
            {
                "month": month_idx + 1,
                "headcount": stat("headcount"),
                "attrition_count": stat("attrition_count"),
                "layoff_count": stat("layoff_count"),
                "avg_stress": stat("avg_stress"),
                "avg_productivity": stat("avg_productivity"),
                "avg_motivation": stat("avg_motivation"),
                "burnout_count": stat("burnout_count"),
                "avg_job_satisfaction": stat("avg_job_satisfaction"),
                "avg_work_life_balance": stat("avg_work_life_balance"),
                "avg_loyalty": stat("avg_loyalty"),
            }
        )

    # --- Executive / domain-level summary ---
    if aggregated:
        valid_summaries = [s for s in all_summaries if "initial_headcount" in s]
        initial_headcount = (
            float(np.mean([s["initial_headcount"] for s in valid_summaries]))
            if valid_summaries
            else aggregated[0]["headcount"]["mean"]
        )
        final_headcount = aggregated[-1]["headcount"]["mean"]

        # Correct attrition formula:
        # Each run's summary["total_quits"] is the ground truth — it's the raw
        # cumulative count returned by time_engine, not a mean of monthly slices.
        # Averaging those per-run totals removes the double-counting bias from
        # summing monthly mean attrition_counts (which compounds rounding error).
        valid_summaries = [s for s in all_summaries if "total_quits" in s]
        if valid_summaries:
            total_quits_est = float(np.mean([s["total_quits"] for s in valid_summaries]))
            avg_headcount_est = (
                float(
                    np.mean(
                        [
                            (s["initial_headcount"] + s["final_headcount"]) / 2.0
                            for s in valid_summaries
                            if "initial_headcount" in s and "final_headcount" in s
                        ]
                    )
                )
                if all("initial_headcount" in s for s in valid_summaries)
                else initial_headcount
            )
        else:
            # Fallback: sum of monthly means (old method — less accurate)
            total_quits_est = sum(m["attrition_count"]["mean"] for m in aggregated)
            avg_headcount_est = initial_headcount

        period_months = config.duration_months
        denom = avg_headcount_est if avg_headcount_est > 0 else initial_headcount
        if denom > 0:
            period_attrition_pct = total_quits_est / denom * 100.0
            annual_attrition_pct = (
                period_attrition_pct * (12.0 / period_months)
                if period_months > 0
                else period_attrition_pct
            )
        else:
            period_attrition_pct = 0.0
            annual_attrition_pct = 0.0

        # Load calibration, if available, to anchor realism check.
        from backend.storage.storage import load_artifact

        baseline_annual_attrition = None
        cal = load_artifact("calibration", session_id=session_id)
        if cal:
            try:
                baseline_annual_attrition = float(cal.get("annual_attrition_rate", 0.0)) * 100.0
            except Exception:
                baseline_annual_attrition = None

        # Simple realism flag for leadership: is this within a plausible HR range?
        realism_flag = "plausible"
        if annual_attrition_pct < 3.0 or annual_attrition_pct > 40.0:
            realism_flag = "implausible"

        # Short narrative for CEOs/Directors
        start = aggregated[0]
        end = aggregated[-1]
        delta_stress = end["avg_stress"]["mean"] - start["avg_stress"]["mean"]
        delta_wlb = end["avg_work_life_balance"]["mean"] - start["avg_work_life_balance"]["mean"]
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
            "baseline_annual_attrition_pct": round(float(baseline_annual_attrition), 2)
            if baseline_annual_attrition is not None
            else None,
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
        "config": config.__dict__,
        "runs": runs,
        "results": aggregated,
        "summary": executive_summary,
    }


if __name__ == "__main__":
    from backend.core.simulation.policies import get_policy

    config = get_policy("baseline")
    results = run_monte_carlo(config, runs=10)

    print("\n=== Month 12 Summary (across 10 runs):")
    m12 = results["results"][11]
    for key, val in m12.items():
        if key != "month":
            print(f"   {key}: mean={val['mean']} | min={val['min']} | max={val['max']}")

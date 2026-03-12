# backend/simulation/time_engine.py

import json
import numpy as np
from sqlmodel import Session, select
from backend.database import engine
from backend.models import Employee
from backend.simulation.agent import EmployeeAgent, _quit_model, _quit_threshold
from backend.simulation.org_graph import build_org_graph, OrgGraph
from backend.simulation.behavior_engine import update_agent_state, apply_attrition_shockwave
from backend.simulation.policies import SimulationConfig, get_policy
from backend.ml.burnout_estimator import burnout_threshold as burnout_fn

# Lazy-loaded calibration cache — same pattern as behavior_engine.py.
# This guarantees that after a retrain + recalibrate, the very next simulation
# picks up fresh values without a server restart.
_engine_calibration_cache = None


def clear_engine_calibration_cache():
    """Call after calibrate() so the next run_simulation reads fresh values."""
    global _engine_calibration_cache
    _engine_calibration_cache = None


def _get_calibration():
    """Lazy-load calibration.json. Re-reads after clear_engine_calibration_cache()."""
    global _engine_calibration_cache
    if _engine_calibration_cache is None:
        try:
            with open("backend/ml/exports/calibration.json") as f:
                _engine_calibration_cache = json.load(f)
        except FileNotFoundError:
            _engine_calibration_cache = {
                "prob_scale": 1.0,
                "stress_amplification": 2.0,
                "monthly_natural_rate": 0.0145,
                "stress_threshold": 0.5,
                "new_hire_monthly_prob": 0.029,
            }
    return _engine_calibration_cache



def load_agents_from_db() -> list[EmployeeAgent]:
    with Session(engine) as session:
        all_employees = session.exec(select(Employee)).all()

    # Load all employees regardless of Attrition label.
    # Attrition="Yes" is past information used to train the ML model.
    # The simulation asks: who will quit in the future?
    # The model answers that from features alone, not the historical label.
    # Hiring replacements happens during the simulation when someone actually quits.
    agents = [EmployeeAgent(emp) for emp in all_employees]
    print(f"  >> Loaded {len(agents)} employees (Attrition label ignored)")
    return agents


def run_simulation(config: SimulationConfig = None, agents=None, G: OrgGraph=None, policy_name: str = "custom", seed: int = 42, prob_scale_override: float = None) -> dict:
    if config is None:
        config = SimulationConfig()

    rng = np.random.default_rng(seed)

    # Read fresh calibration on every call (lazy-loaded, invalidated after retrain)
    cal                = _get_calibration()
    STRESS_THRESHOLD   = cal.get("stress_threshold", 0.5)
    NATURAL_MONTHLY_RATE = cal.get("monthly_natural_rate", 0.0145)
    STRESS_AMPLIFICATION = cal.get("stress_amplification", 2.0)
    # prob_scale_override lets the calibration loop test different scales without
    # rewriting calibration.json between runs.
    _prob_scale = prob_scale_override if prob_scale_override is not None else cal.get("prob_scale", 1.0)
    _new_hire_cap = cal.get("new_hire_monthly_prob", NATURAL_MONTHLY_RATE * 2.0)

    print(f"=== Starting simulation - Policy: {policy_name.upper()}")
    if agents is None:
        agents = load_agents_from_db()
    if G is None:
        G = build_org_graph(agents)

    if not agents:
        print("No agents available for simulation. Returning empty results.")
        return {
            "config": config.__dict__,
            "logs": [],
            "summary": {
                "policy_name": policy_name,
                "duration_months": config.duration_months,
                "initial_headcount": 0,
                "final_headcount": 0,
                "total_quits": 0,
                "total_layoffs": 0,
                "annual_attrition_pct": 0.0,
            },
        }

    max_id = max(a.employee_id for a in agents)
    initial_headcount = len([a for a in agents if a.is_active])
    initial_avg_stress = float(np.mean([a.stress for a in agents if a.is_active]))
    logs   =  []
    for month in range(1, config.duration_months + 1):
        print(f"--- Month {month}...")

        #   Update all agent states
        for agent in agents:
            if agent.is_active:
                update_agent_state(
                    agent, G,
                    workload_multiplier   = config.workload_multiplier,
                    motivation_decay_rate = config.motivation_decay_rate,
                    stress_gain_rate      = config.stress_gain_rate,
                    overtime_bonus        = config.overtime_bonus,
                    wlb_boost             = config.wlb_boost,
                )

        # Layoffs
        layoff_agents = []
        if config.layoff_ratio > 0:
            active     = [a for a in agents if a.is_active]
            n_layoffs  = int(len(active) * config.layoff_ratio)
            layoff_targets = sorted(active, key=lambda a: a.performance_rating)[:n_layoffs]
            for agent in layoff_targets:
                layoff_agents.append(agent)

        # Voluntary attrition
        quitting_agents = []
        for agent in agents:
            if not agent.is_active or agent in layoff_agents:
                continue

            yearly_prob  = _quit_model().predict_proba(agent.get_quit_features())[0][1]
            monthly_prob = 1 - (1 - yearly_prob) ** (1 / 12)

            # Mid-simulation new hires (years_at_company=0) have zero-valued engineered
            # features so the model over-scores them. Cap at new_hire_monthly_prob —
            # derived from real short-tenure employees in calibration, same cap used
            # in mini-sim so prob_scale stays consistent.
            if agent.years_at_company == 0:
                monthly_prob = min(monthly_prob, _new_hire_cap)

            excess_stress  = max(0.0, agent.stress - STRESS_THRESHOLD)
            stress_scale   = 1.0 + STRESS_AMPLIFICATION * excess_stress
            effective_prob = min(1.0, monthly_prob * _prob_scale * stress_scale)

            if rng.random() < effective_prob:
                quitting_agents.append(agent)

        # Process departures
        for agent in layoff_agents + quitting_agents:
            apply_attrition_shockwave(agent, G, config.shock_factor)
            agent.is_active = False
            # G.remove_node() intentionally omitted: removing nodes permanently
            # breaks contagion paths. Inactive agents are skipped by behavior_engine.

        # Hiring — employer attractiveness model.
        # Companies under stress struggle to attract candidates. Calm workplaces
        # fill roles quickly. Stressful ones lose the hiring race.
        #
        # fill_prob  = 0.95 at zero stress (calm, nearly all quits replaced)
        #            = 0.50 at max stress  (toxic culture, candidates avoid it)
        # Uses previous month's avg_stress so the effect is one month delayed
        # (real companies feel reputation lag when stress spikes).
        if config.hiring_active:
            prev_avg_stress = logs[-1]["avg_stress"] if logs else initial_avg_stress
            fill_prob       = max(0.50, 0.95 - prev_avg_stress * 0.50)

            filled_this_month = 0
            for quitter in list(quitting_agents):
                if rng.random() < fill_prob:
                    max_id += 1
                    # Spawn via from_template — goes through __init__, no attribute misses
                    new_agent = EmployeeAgent.from_template(quitter, max_id, rng)

                    agents.append(new_agent)
                    G.add_node(new_agent.employee_id, agent=new_agent)
                    if new_agent.manager_id and G.has_node(new_agent.manager_id):
                        G.add_edge(
                            new_agent.employee_id,
                            new_agent.manager_id,
                            weight=0.9,
                            edge_type="manager"
                        )

        #  Metrics
        active_agents = [a for a in agents if a.is_active]
        if active_agents:
            avg_stress       = np.mean([a.stress            for a in active_agents])
            avg_productivity = np.mean([a.productivity      for a in active_agents])
            avg_motivation   = np.mean([a.motivation        for a in active_agents])
            avg_job_sat      = np.mean([a.job_satisfaction  for a in active_agents])
            avg_wlb          = np.mean([a.work_life_balance for a in active_agents])
            avg_loyalty      = np.mean([a.loyalty           for a in active_agents])
            burnout_count    = sum(1 for a in active_agents if a.stress > a.burnout_limit)
        else:
            avg_stress       = 0.0
            avg_productivity = 0.0
            avg_motivation   = 0.0
            avg_job_sat      = 0.0
            avg_wlb          = 0.0
            avg_loyalty      = 0.0
            burnout_count    = 0

        logs.append({
            "month"                : month,
            "headcount"            : len(active_agents),
            "attrition_count"      : len(quitting_agents),
            "layoff_count"         : len(layoff_agents),
            "avg_stress"           : round(float(avg_stress), 4),
            "avg_productivity"     : round(float(avg_productivity), 4),
            "avg_motivation"       : round(float(avg_motivation), 4),
            "avg_job_satisfaction" : round(float(avg_job_sat), 4),
            "avg_work_life_balance": round(float(avg_wlb), 4),
            "avg_loyalty"          : round(float(avg_loyalty), 4),
            "burnout_count"        : burnout_count,
        })

        print(f"   HC: {len(active_agents)} |"
              f" Quit: {len(quitting_agents)} |"
              f" Layoff: {len(layoff_agents)} |"
              f" Stress: {avg_stress:.3f} |"
              f" Productivity: {avg_productivity:.3f} |"
              f" JobSat: {avg_job_sat:.2f} |"
              f" WLB: {avg_wlb:.2f} |"
              f" Loyalty: {avg_loyalty:.2f} |"
              f" Burnout: {burnout_count}")


    # Summary
    total_quits       = sum(l["attrition_count"] for l in logs)
    total_layoffs     = sum(l["layoff_count"] for l in logs)
    final_headcount   = logs[-1]["headcount"] if logs else initial_headcount
    period_months     = config.duration_months

    # Use average headcount as denominator for voluntary attrition rate.
    # Initial headcount is wrong for shrinking workforces (layoff scenarios) —
    # 432 quits / 4410 initial = 9.8%, but the company was down to 494 by month 12.
    # Average headcount across the period correctly reflects the population at risk.
    avg_headcount        = sum(l["headcount"] for l in logs) / len(logs) if logs else initial_headcount
    period_attrition_pct = (total_quits / avg_headcount * 100) if avg_headcount > 0 else 0.0
    annual_attrition_pct = period_attrition_pct * (12.0 / period_months) if period_months > 0 else period_attrition_pct

    total_workforce_loss      = total_quits + total_layoffs
    total_workforce_loss_pct  = (total_workforce_loss / initial_headcount * 100) if initial_headcount > 0 else 0.0

    print(f"\n{'='*50}")
    print(f"=== Simulation Summary - {policy_name.upper()}")
    print(f"{'='*50}")
    print(f"   Duration          : {config.duration_months} months")
    print(f"   Initial Headcount : {initial_headcount}")
    print(f"   Final Headcount   : {final_headcount}")
    print(f"   Total Quits       : {total_quits}")
    print(f"   Total Layoffs     : {total_layoffs}")
    print(f"   Attrition Rate    : {period_attrition_pct:.1f}% "
          f"(~{annual_attrition_pct:.1f}% annualised, voluntary only)")
    print(f"   Workforce Loss    : {total_workforce_loss_pct:.1f}% "
          f"(voluntary + involuntary)")
    print(f"   Final Avg Stress  : {logs[-1]['avg_stress']:.3f}")
    print(f"   Final Productivity: {logs[-1]['avg_productivity']:.3f}")
    print(f"   Final Burnout     : {logs[-1]['burnout_count']}")
    print(f"{'='*50}")
    print("+++ Simulation complete.")

    summary = {
        "policy_name": policy_name,
        "duration_months": config.duration_months,
        "initial_headcount": initial_headcount,
        "final_headcount": final_headcount,
        "total_quits": total_quits,
        "total_layoffs": total_layoffs,
        "period_attrition_pct": round(period_attrition_pct, 2),
        "annual_attrition_pct": round(annual_attrition_pct, 2),
        "total_workforce_loss_pct": round(total_workforce_loss_pct, 2),
        "final_avg_stress": round(float(logs[-1]["avg_stress"]), 4) if logs else 0.0,
        "final_avg_productivity": round(float(logs[-1]["avg_productivity"]), 4) if logs else 0.0,
        "final_burnout_count": logs[-1]["burnout_count"] if logs else 0,
    }

    return {"config": config.__dict__, "logs": logs, "summary": summary}


if __name__ == "__main__":
    policy  = "flexible_work"
    config  = get_policy(policy)
    results = run_simulation(config, policy_name=policy)  
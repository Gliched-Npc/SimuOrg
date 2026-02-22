# backend/simulation/time_engine.py

import random
import json
import numpy as np
from sqlmodel import Session, select
from backend.database import engine
from backend.models import Employee
from backend.simulation.agent import EmployeeAgent, quit_model
from backend.simulation.org_graph import build_org_graph
from backend.simulation.behavior_engine import update_agent_state, apply_attrition_shockwave
from backend.simulation.policies import SimulationConfig, get_policy

# Load calibration with fallback defaults
try:
    with open("backend/ml/exports/calibration.json") as f:
        calibration = json.load(f)
except FileNotFoundError:
    calibration = {
        "quit_threshold":       0.37,
        "stress_threshold":     0.5,
        "monthly_natural_rate": 0.0145,
        "natural_scale":        1.0,
    }

QUIT_THRESHOLD       = calibration["quit_threshold"]
STRESS_THRESHOLD     = calibration["stress_threshold"]
NATURAL_MONTHLY_RATE = calibration["monthly_natural_rate"]


def load_agents_from_db() -> list[EmployeeAgent]:
    with Session(engine) as session:
        employees = session.exec(select(Employee)).all()
    return [EmployeeAgent(emp) for emp in employees]


def run_simulation(config: SimulationConfig = None, agents=None, G=None) -> dict:
    if config is None:
        config = SimulationConfig()

    print("🚀 Starting simulation...")
    if agents is None:
        agents = load_agents_from_db()
    if G is None:
        G = build_org_graph(agents)

    # Track max ID to avoid new hire collisions
    max_id = max(a.employee_id for a in agents)

    logs = []

    for month in range(1, config.duration_months + 1):
        print(f"📅 Month {month}...")

        # Step 1 — Update all agent states
        for agent in agents:
            if agent.is_active:
                update_agent_state(
                    agent, G,
                    workload_multiplier   = config.workload_multiplier,
                    motivation_decay_rate = config.motivation_decay_rate,
                    stress_gain_rate      = config.stress_gain_rate,  # now passed correctly
                )

        # Step 2 — Layoffs (before voluntary attrition)
        layoff_agents = []
        if config.layoff_ratio > 0:
            active = [a for a in agents if a.is_active]
            n_layoffs = int(len(active) * config.layoff_ratio)
            # Lay off lowest performers first
            layoff_targets = sorted(active, key=lambda a: a.performance_rating)[:n_layoffs]
            for agent in layoff_targets:
                layoff_agents.append(agent)

        # Step 3 — Voluntary attrition
        quitting_agents = []
        for agent in agents:
            if not agent.is_active:
                continue
            if agent in layoff_agents:
                continue  # already being laid off

            yearly_prob  = quit_model.predict_proba(agent.get_quit_features())[0][1]
            monthly_prob = 1 - (1 - yearly_prob) ** (1 / 12)

            # Natural attrition
            if random.random() < NATURAL_MONTHLY_RATE:
                quitting_agents.append(agent)
                continue

            # Stress-driven attrition
            if agent.stress > STRESS_THRESHOLD and yearly_prob > QUIT_THRESHOLD:
                if random.random() < monthly_prob:
                    quitting_agents.append(agent)

        # Step 4 — Process all departures (layoffs + voluntary)
        all_departures = layoff_agents + quitting_agents
        for agent in all_departures:
            apply_attrition_shockwave(agent, G, config.shock_factor)
            agent.is_active = False
            if G.has_node(agent.employee_id):
                G.remove_node(agent.employee_id)

        # Step 5 — Hiring (only replaces voluntary quits, not layoffs)
        if config.hiring_active:
            for quitter in quitting_agents:
                max_id += 1  # safe unique ID
                new_agent = EmployeeAgent.__new__(EmployeeAgent)
                new_agent.employee_id           = max_id
                new_agent.department            = quitter.department
                new_agent.job_role              = quitter.job_role
                new_agent.job_level             = quitter.job_level
                new_agent.manager_id            = quitter.manager_id
                new_agent.years_at_company      = 0
                new_agent.total_working_years   = 0
                new_agent.num_companies_worked  = 1.0
                new_agent.monthly_income        = quitter.monthly_income
                new_agent.job_satisfaction      = 3.0
                new_agent.work_life_balance     = 3.0
                new_agent.performance_rating    = 3
                new_agent.stress                = 0.1
                new_agent.fatigue               = 0.0
                new_agent.motivation            = 0.75
                new_agent.loyalty               = 0.1
                new_agent.productivity          = 1.0
                new_agent.is_active             = True
                new_agent.burnout_limit         = 0.4
                agents.append(new_agent)
                G.add_node(new_agent.employee_id, agent=new_agent)
                if new_agent.manager_id and G.has_node(new_agent.manager_id):
                    G.add_edge(
                        new_agent.employee_id,
                        new_agent.manager_id,
                        weight=0.9,
                        edge_type="manager"
                    )

        # Step 6 — Compute metrics
        active_agents    = [a for a in agents if a.is_active]
        avg_stress       = np.mean([a.stress       for a in active_agents])
        avg_productivity = np.mean([a.productivity for a in active_agents])
        avg_motivation   = np.mean([a.motivation   for a in active_agents])
        avg_job_sat      = np.mean([a.job_satisfaction   for a in active_agents])
        avg_wlb          = np.mean([a.work_life_balance  for a in active_agents])
        avg_loyalty      = np.mean([a.loyalty      for a in active_agents])
        burnout_count    = sum(1 for a in active_agents if a.stress > a.burnout_limit)

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

        print(f"   👥 {len(active_agents)} | "
              f"Quit: {len(quitting_agents)} | "
              f"Layoff: {len(layoff_agents)} | "
              f"Stress: {avg_stress:.3f} | "
              f"Productivity: {avg_productivity:.3f} | "
              f"JobSat: {avg_job_sat:.2f} | "
              f"WLB: {avg_wlb:.2f} | "
              f"Loyalty: {avg_loyalty:.2f} | "
              f"Burnout: {burnout_count}")

    print("✅ Simulation complete.")
    return {"config": config.__dict__, "logs": logs}


if __name__ == "__main__":
    config  = get_policy("baseline")
    results = run_simulation(config)
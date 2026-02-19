# backend/simulation/time_engine.py

import random
import numpy as np
from sqlmodel import Session, select
from backend.database import engine
from backend.models import Employee
from backend.simulation.agent import EmployeeAgent, quit_model
from backend.simulation.org_graph import build_org_graph
from backend.simulation.behavior_engine import update_agent_state, apply_attrition_shockwave
from backend.simulation.policies import SimulationConfig, get_policy


def load_agents_from_db() -> list[EmployeeAgent]:
    with Session(engine) as session:
        employees = session.exec(select(Employee)).all()
    return [EmployeeAgent(emp) for emp in employees]


def run_simulation(config: SimulationConfig = None) -> dict:
    if config is None:
        config = SimulationConfig()

    print("🚀 Starting simulation...")
    agents = load_agents_from_db()
    G = build_org_graph(agents)
    logs = []

    for month in range(1, config.duration_months + 1):
        print(f"📅 Month {month}...")

        for agent in agents:
            if agent.is_active:
                update_agent_state(
                    agent, G,
                    config.workload_multiplier,
                    config.motivation_decay_rate
                )

        quitting_agents = []
        for agent in agents:
            if not agent.is_active:
                continue
            yearly_prob  = quit_model.predict_proba(agent.get_quit_features())[0][1]
            monthly_prob = 1 - (1 - yearly_prob) ** (1 / 12)
            if agent.stress > 0.15 and yearly_prob > 0.25:
                if random.random() < monthly_prob:
                    quitting_agents.append(agent)

        for agent in quitting_agents:
            apply_attrition_shockwave(agent, G, config.shock_factor)
            agent.is_active = False
            if G.has_node(agent.employee_id):
                G.remove_node(agent.employee_id)

        if config.hiring_active:
            for quitter in quitting_agents:
                new_agent = EmployeeAgent.__new__(EmployeeAgent)
                new_agent.employee_id        = quitter.employee_id + 100000
                new_agent.department         = quitter.department
                new_agent.job_role           = quitter.job_role
                new_agent.job_level          = quitter.job_level
                new_agent.manager_id         = quitter.manager_id
                new_agent.years_at_company   = 0
                new_agent.total_working_years= 0
                new_agent.monthly_income     = quitter.monthly_income
                new_agent.job_satisfaction   = 3.0
                new_agent.work_life_balance  = 3.0
                new_agent.performance_rating = 3
                new_agent.stress             = 0.0
                new_agent.fatigue            = 0.0
                new_agent.motivation         = 0.75
                new_agent.loyalty            = 0.1
                new_agent.productivity       = 1.0
                new_agent.is_active          = True
                new_agent.burnout_limit      = 0.4
                agents.append(new_agent)
                G.add_node(new_agent.employee_id, agent=new_agent)
                if new_agent.manager_id and G.has_node(new_agent.manager_id):
                    G.add_edge(new_agent.employee_id, new_agent.manager_id,
                               weight=0.9, edge_type="manager")

        active_agents    = [a for a in agents if a.is_active]
        avg_stress       = np.mean([a.stress for a in active_agents])
        avg_productivity = np.mean([a.productivity for a in active_agents])
        avg_motivation   = np.mean([a.motivation for a in active_agents])
        burnout_count    = sum(1 for a in active_agents if a.stress > a.burnout_limit)

        logs.append({
            "month"           : month,
            "headcount"       : len(active_agents),
            "attrition_count" : len(quitting_agents),
            "avg_stress"      : round(float(avg_stress), 4),
            "avg_productivity": round(float(avg_productivity), 4),
            "avg_motivation"  : round(float(avg_motivation), 4),
            "burnout_count"   : burnout_count,
        })

        print(f"   👥 Headcount: {len(active_agents)} | "
              f"Quit: {len(quitting_agents)} | "
              f"Stress: {avg_stress:.3f} | "
              f"Productivity: {avg_productivity:.3f}")

    print("✅ Simulation complete.")
    return {"config": config.__dict__, "logs": logs}


if __name__ == "__main__":
    config = get_policy("baseline")
    results = run_simulation(config)
# ```

# Save it and run:
# ```
# python -m backend.simulation.time_engine
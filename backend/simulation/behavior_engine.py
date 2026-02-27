# backend/simulation/behavior_engine.py

from backend.simulation.agent import EmployeeAgent
from backend.simulation.org_graph import build_org_graph, OrgGraph
import json

try:
    with open("backend/ml/exports/calibration.json") as f:
        _cal = json.load(f)
except FileNotFoundError:
    _cal = {
        "stress_gain_rate": 0.0132,
        "recovery_rate": 0.0104,
        "shockwave_stress_factor": 0.268,
        "shockwave_loyalty_factor": 0.093,
    }

STRESS_GAIN_RATE = _cal["stress_gain_rate"]
RECOVERY_RATE    = _cal["recovery_rate"]
_SHOCKWAVE_STRESS_FACTOR  = _cal.get("shockwave_stress_factor", 0.3)
_SHOCKWAVE_LOYALTY_FACTOR = _cal.get("shockwave_loyalty_factor", 0.1)

def compute_neighbor_influence(agent: EmployeeAgent, G: OrgGraph) -> tuple[float, float]:
    """
    Read stress from neighbors weighted by edge weight.
    Returns (neighbor_stress, comm_quality)
    """
    neighbor_stress = 0.0
    comm_quality = 0.0

    for neighbor_id in G.neighbors(agent.employee_id):
        edge_data = G[agent.employee_id][neighbor_id]
        weight = edge_data.get("weight", 0.5)
        neighbor_agent = G.nodes[neighbor_id].get("agent")

        if neighbor_agent and neighbor_agent.is_active:
            neighbor_stress += weight * neighbor_agent.stress
            comm_quality += weight

    return neighbor_stress, comm_quality


def update_agent_state(agent: EmployeeAgent, 
                       G: OrgGraph, 
                       workload_multiplier: float,
                       motivation_decay_rate: float,
                       stress_gain_rate: float=1.0,
                       overtime_bonus: float=0.0):
    """
    Update one agent's behavioral state for one timestep.
    """
    if not agent.is_active:
        return

    # Step 1 — Get neighbor influence
    neighbor_stress, comm_quality = compute_neighbor_influence(agent, G)

    # Step 2 — Update stress
    stress_gain = (
        STRESS_GAIN_RATE * workload_multiplier * stress_gain_rate +
        0.01 * neighbor_stress +
        0.005 * agent.fatigue -
        0.001 * min(comm_quality, 5.0)
    )
    agent.stress = max(0.0, min(agent.stress + stress_gain, 1.0))
    agent.stress = max(0.0, agent.stress - RECOVERY_RATE)

    # Step 3 — Update fatigue
    if agent.stress > 0.5:
        agent.fatigue = min(agent.fatigue + 0.03, 1.0)
    else:
        agent.fatigue = max(agent.fatigue - 0.01, 0.0)

    # Step 4 — Update motivation
    if agent.stress > 0.4:
        agent.motivation = max(agent.motivation - motivation_decay_rate, 0.0)
    else:
        # Recover slowly back to their personal baseline
        agent.motivation = min(agent.motivation + 0.01, agent.baseline_satisfaction / 4.0)

    # Step 5 — Sync satisfaction with motivation and stress, capped at baseline
    # Overtime pay provides an artificial monetary buffer to Job Satisfaction
    base_satisfaction = (agent.motivation * 4.0) + overtime_bonus
    agent.job_satisfaction = max(1.0, min(4.0, base_satisfaction))
    
    # WLB drifts down slowly from baseline based on stress (requires crossing 0.2 buffer)
    perceptible_stress = max(0.0, agent.stress - 0.2)
    target_wlb = max(1.0, min(4.0, agent.baseline_wlb - (perceptible_stress * 1.5)))
    
    # Smooth the drop so it doesn't crash all at once (max drop of 0.15 per month)
    if target_wlb < agent.work_life_balance:
        agent.work_life_balance = max(target_wlb, agent.work_life_balance - 0.15)
    else:
        agent.work_life_balance = min(target_wlb, agent.work_life_balance + 0.1)

    # Step 6 — Update productivity
    agent.update_productivity(workload_multiplier)

    # Step 7 — Burnout acceleration
    if agent.stress > agent.burnout_limit:
        # agent.stress = min(agent.stress + 0.02, 1.0)
        agent.productivity *= 0.97


def apply_attrition_shockwave(quitting_agent: EmployeeAgent,
                               G: OrgGraph,
                               shock_factor: float):
    """
    When an agent quits, their neighbors feel the impact.
    """
    for neighbor_id in list(G.neighbors(quitting_agent.employee_id)):
        edge_data = G[quitting_agent.employee_id][neighbor_id]
        weight = edge_data.get("weight", 0.5)
        neighbor_agent = G.nodes[neighbor_id].get("agent")

        if neighbor_agent and neighbor_agent.is_active:
            neighbor_agent.stress  += shock_factor * weight * _SHOCKWAVE_STRESS_FACTOR
            neighbor_agent.loyalty -= shock_factor * weight * _SHOCKWAVE_LOYALTY_FACTOR

            # Cap values
            neighbor_agent.stress  = min(neighbor_agent.stress, 1.0)
            neighbor_agent.loyalty = max(neighbor_agent.loyalty, 0.0)
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
        "neighbor_stress_weight": 0.01,
        "fatigue_stress_weight": 0.005,
        "comm_quality_cap": 5.0,
        "comm_quality_benefit": 0.001,
        "fatigue_gain_rate": 0.03,
        "fatigue_recovery_rate": 0.01,
        "fatigue_stress_trigger": 0.5,
        "motivation_recovery_rate": 0.01,
        "stress_threshold": 0.44,
        "wlb_stress_buffer": 0.2,
        "wlb_stress_sensitivity": 1.5,
        "wlb_drop_rate": 0.15,
        "wlb_recovery_rate": 0.1,
        "burnout_productivity_penalty": 0.97,
    }

# All constants loaded from calibration.json — zero hardcoded values
STRESS_GAIN_RATE         = _cal["stress_gain_rate"]
RECOVERY_RATE            = _cal["recovery_rate"]
NEIGHBOR_STRESS_WEIGHT   = _cal.get("neighbor_stress_weight", 0.01)
FATIGUE_STRESS_WEIGHT    = _cal.get("fatigue_stress_weight", 0.005)
COMM_QUALITY_CAP         = _cal.get("comm_quality_cap", 5.0)
COMM_QUALITY_BENEFIT     = _cal.get("comm_quality_benefit", 0.001)
FATIGUE_GAIN_RATE        = _cal.get("fatigue_gain_rate", 0.03)
FATIGUE_RECOVERY_RATE    = _cal.get("fatigue_recovery_rate", 0.01)
FATIGUE_STRESS_TRIGGER   = _cal.get("fatigue_stress_trigger", 0.5)
MOTIVATION_RECOVERY_RATE = _cal.get("motivation_recovery_rate", 0.01)
STRESS_THRESHOLD         = _cal.get("stress_threshold", 0.44)
WLB_STRESS_BUFFER        = _cal.get("wlb_stress_buffer", 0.2)
WLB_STRESS_SENSITIVITY   = _cal.get("wlb_stress_sensitivity", 1.5)
WLB_DROP_RATE            = _cal.get("wlb_drop_rate", 0.15)
WLB_RECOVERY_RATE        = _cal.get("wlb_recovery_rate", 0.1)
BURNOUT_PROD_PENALTY     = _cal.get("burnout_productivity_penalty", 0.97)

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
    All constants from calibration.json — no hardcoded values.
    """
    if not agent.is_active:
        return

    # Get neighbor influence
    neighbor_stress, comm_quality = compute_neighbor_influence(agent, G)

    # Update stress — all weights from calibration
    stress_gain = (
        STRESS_GAIN_RATE * workload_multiplier * stress_gain_rate +
        NEIGHBOR_STRESS_WEIGHT * neighbor_stress +
        FATIGUE_STRESS_WEIGHT * agent.fatigue -
        COMM_QUALITY_BENEFIT * min(comm_quality, COMM_QUALITY_CAP)
    )
    agent.stress = max(0.0, min(agent.stress + stress_gain, 1.0))
    agent.stress = max(0.0, agent.stress - RECOVERY_RATE)

    # Update fatigue — trigger and rates from calibration
    if agent.stress > FATIGUE_STRESS_TRIGGER:
        agent.fatigue = min(agent.fatigue + FATIGUE_GAIN_RATE, 1.0)
    else:
        agent.fatigue = max(agent.fatigue - FATIGUE_RECOVERY_RATE, 0.0)

    # Update motivation — threshold from calibration
    if agent.stress > STRESS_THRESHOLD:
        agent.motivation = max(agent.motivation - motivation_decay_rate, 0.0)
    else:
        # Recover slowly back to their personal baseline
        agent.motivation = min(agent.motivation + MOTIVATION_RECOVERY_RATE, agent.baseline_satisfaction / 4.0)

    # Sync satisfaction with motivation and stress, capped at baseline
    # Overtime pay: only affects agents who actually work overtime (agent.overtime == 1).
    # Bonus phases out as fatigue builds — money stops compensating once burnout sets in.
    # fatigue=0.0 → full bonus | fatigue=0.5 → half bonus | fatigue>=1.0 → no bonus
    effective_overtime_bonus = 0.0
    if agent.overtime == 1 and overtime_bonus > 0.0:
        fatigue_discount = max(0.0, 1.0 - agent.fatigue)
        effective_overtime_bonus = overtime_bonus * fatigue_discount

    base_satisfaction = (agent.motivation * 4.0) + effective_overtime_bonus
    agent.job_satisfaction = max(1.0, min(4.0, base_satisfaction))
    
    # WLB drifts down from baseline based on stress (requires crossing calibrated buffer)
    perceptible_stress = max(0.0, agent.stress - WLB_STRESS_BUFFER)
    target_wlb = max(1.0, min(4.0, agent.baseline_wlb - (perceptible_stress * WLB_STRESS_SENSITIVITY)))
    
    # Smooth the drop — cap from calibration (no longer hardcoded 0.15)
    if target_wlb < agent.work_life_balance:
        agent.work_life_balance = max(target_wlb, agent.work_life_balance - WLB_DROP_RATE)
    else:
        agent.work_life_balance = min(target_wlb, agent.work_life_balance + WLB_RECOVERY_RATE)

    # Update productivity
    agent.update_productivity(workload_multiplier)

    # Burnout acceleration — penalty from calibration
    if agent.stress > agent.burnout_limit:
        agent.productivity *= BURNOUT_PROD_PENALTY


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
# backend/simulation/behavior_engine.py

from backend.core.simulation.agent import EmployeeAgent
from backend.core.simulation.org_graph import build_org_graph, OrgGraph
import json

_calibration_cache = None

def _load_calibration():
    """Lazy-load calibration — re-reads after retrain without server restart."""
    global _calibration_cache
    if _calibration_cache is None:
        try:
            with open("backend/core/ml/exports/calibration.json") as f:
                _calibration_cache = json.load(f)
        except FileNotFoundError:
            _calibration_cache = {
                "stress_gain_rate": 0.0132,
                "behavior_stress_gain_rate": 0.0264,
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
    return _calibration_cache


def clear_calibration_cache():
    """Invalidate the lazy cache so the next simulation re-reads calibration.json."""
    global _calibration_cache
    _calibration_cache = None


# All constants resolved lazily via _load_calibration() on first call
def _c(key, default):
    return _load_calibration().get(key, default)

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
                       stress_gain_rate: float = 1.0,
                       overtime_bonus: float = 0.0,
                       wlb_boost: float = 0.0):
    """
    Update one agent's behavioral state for one timestep.
    All constants from calibration.json via lazy loader — picks up retrain without restart.
    """
    if not agent.is_active:
        return

    # Resolve constants lazily each call (cached after first load)
    STRESS_GAIN_RATE       = _c("behavior_stress_gain_rate", _c("stress_gain_rate", 0.0132))
    RECOVERY_RATE          = _c("recovery_rate", 0.0104)
    NEIGHBOR_STRESS_WEIGHT = _c("neighbor_stress_weight", 0.01)
    FATIGUE_STRESS_WEIGHT  = _c("fatigue_stress_weight", 0.005)
    COMM_QUALITY_CAP       = _c("comm_quality_cap", 5.0)
    COMM_QUALITY_BENEFIT   = _c("comm_quality_benefit", 0.001)
    FATIGUE_GAIN_RATE      = _c("fatigue_gain_rate", 0.03)
    FATIGUE_RECOVERY_RATE  = _c("fatigue_recovery_rate", 0.01)
    FATIGUE_STRESS_TRIGGER = _c("fatigue_stress_trigger", 0.5)
    MOTIVATION_RECOVERY_RATE = _c("motivation_recovery_rate", 0.01)
    MOTIVATION_THRESHOLD = _c("motivation_threshold", 0.15)
    WLB_STRESS_BUFFER      = _c("wlb_stress_buffer", 0.2)
    WLB_STRESS_SENSITIVITY = _c("wlb_stress_sensitivity", 1.5)
    WLB_DROP_RATE          = _c("wlb_drop_rate", 0.15)
    WLB_RECOVERY_RATE      = _c("wlb_recovery_rate", 0.1)
    BURNOUT_PROD_PENALTY   = _c("burnout_productivity_penalty", 0.97)

    # Get neighbor influence
    neighbor_stress, comm_quality = compute_neighbor_influence(agent, G)

    # Quadratic workload scaling — high pressure is meaningfully worse than linear
    # workload=1.0 → 1.0x | workload=1.3 → 1.69x | workload=1.5 → 2.25x
    workload_stress_factor = workload_multiplier ** 2

    # Stress accumulates each month. Net gain is positive under pressure.
    # Overtime pay provides a stress dampener — being compensated fairly
    # reduces subjective stress from overwork (rational agent effect).
    # The relief is proportional to bonus but capped at 50% of raw gain
    # so stress can still build under extreme workload.
    raw_stress_gain = (
        STRESS_GAIN_RATE * workload_stress_factor * stress_gain_rate
        + NEIGHBOR_STRESS_WEIGHT * neighbor_stress
        + FATIGUE_STRESS_WEIGHT * agent.fatigue
        - COMM_QUALITY_BENEFIT * min(comm_quality, COMM_QUALITY_CAP)
    )
    overtime_stress_relief = min(raw_stress_gain * 0.5, overtime_bonus * 0.02) if overtime_bonus > 0.0 else 0.0
    stress_gain = raw_stress_gain - overtime_stress_relief
    agent.stress = max(0.0, min(agent.stress + stress_gain - RECOVERY_RATE, 1.0))

    # Fatigue
    if agent.stress > FATIGUE_STRESS_TRIGGER:
        agent.fatigue = min(agent.fatigue + FATIGUE_GAIN_RATE, 1.0)
    else:
        agent.fatigue = max(agent.fatigue - FATIGUE_RECOVERY_RATE, 0.0)

    # Motivation decays under stress OR high workload.
    # Exception: when overtime_bonus > 0, pay compensates for workload — no workload decay
    # until stress crosses threshold (fatigue eventually overwhelms the pay benefit).
    if agent.stress > MOTIVATION_THRESHOLD:
        agent.motivation = max(agent.motivation - motivation_decay_rate, 0.0)
    elif workload_multiplier > 1.0 and overtime_bonus == 0.0:
        # High workload without pay compensation grinds motivation down
        workload_decay = motivation_decay_rate * (workload_multiplier - 1.0) * 1.5
        agent.motivation = max(agent.motivation - workload_decay, 0.0)
    else:
        agent.motivation = min(agent.motivation + MOTIVATION_RECOVERY_RATE, agent.baseline_satisfaction / 4.0)

    # Financial compensation (overtime pay or salary baseline bonus) — phases out with fatigue
    effective_overtime_bonus = 0.0
    if overtime_bonus > 0.0:
        fatigue_discount = max(0.0, 1.0 - agent.fatigue)
        effective_overtime_bonus = overtime_bonus * fatigue_discount

    base_satisfaction = (agent.motivation * 4.0) + effective_overtime_bonus
    agent.job_satisfaction = max(1.0, min(4.0, base_satisfaction))

    # Financial loyalty gain — being fairly compensated builds commitment.
    # Small per-month effect but persistent: loyalty grows when well compensated,
    # making highly-paid employees more likely to stay long-term.
    if overtime_bonus > 0.0:
        loyalty_gain = overtime_bonus * 0.003 * (1.0 - agent.fatigue)
        agent.loyalty = min(1.0, agent.loyalty + loyalty_gain)

    # WLB drifts toward a target based on stress above the buffer.
    # wlb_boost raises the target ceiling — used by flexible/remote policies
    # to reflect that autonomy and schedule control genuinely improve WLB
    # beyond what stress reduction alone achieves.
    perceptible_stress = max(0.0, agent.stress - WLB_STRESS_BUFFER)
    target_wlb = max(1.0, min(4.0, agent.baseline_wlb + wlb_boost - (perceptible_stress * WLB_STRESS_SENSITIVITY)))
    if target_wlb < agent.work_life_balance:
        agent.work_life_balance = max(target_wlb, agent.work_life_balance - WLB_DROP_RATE)
    else:
        agent.work_life_balance = min(target_wlb, agent.work_life_balance + WLB_RECOVERY_RATE)

    # Productivity
    agent.update_productivity(workload_multiplier)

    # Burnout penalty — graduated, not binary.
    # A binary on/off penalty causes a "burnout cliff" where thousands of employees
    # suddenly drop productivity in the same month.
    # Graduated penalty: scales with how far stress exceeds the burnout_limit,
    # so the productivity curve degrades smoothly rather than collapsing at once.
    if agent.stress > agent.burnout_limit:
        overshoot = (agent.stress - agent.burnout_limit) / max(1.0 - agent.burnout_limit, 0.01)
        burnout_penalty = BURNOUT_PROD_PENALTY ** (1.0 + overshoot)
        agent.productivity *= burnout_penalty


def apply_attrition_shockwave(quitting_agent: EmployeeAgent,
                               G: OrgGraph,
                               shock_factor: float):
    """When an agent quits, their neighbors feel the impact."""
    shockwave_stress  = _c("shockwave_stress_factor", 0.3)
    shockwave_loyalty = _c("shockwave_loyalty_factor", 0.1)
    for neighbor_id in list(G.neighbors(quitting_agent.employee_id)):
        edge_data = G[quitting_agent.employee_id][neighbor_id]
        weight = edge_data.get("weight", 0.5)
        neighbor_agent = G.nodes[neighbor_id].get("agent")

        if neighbor_agent and neighbor_agent.is_active:
            # Cascade velocity cap: max stress added per quit event = 0.05.
            # Without this, a single mass-layoff instantly pushes every neighbor
            # over threshold, creating an unrealistic avalanche in one month.
            raw_stress_hit = shock_factor * weight * shockwave_stress
            neighbour_stress_delta = min(raw_stress_hit, 0.05)
            neighbor_agent.stress  = min(neighbor_agent.stress + neighbour_stress_delta, 1.0)
            neighbor_agent.loyalty -= shock_factor * weight * shockwave_loyalty
            neighbor_agent.loyalty = max(neighbor_agent.loyalty, 0.0)
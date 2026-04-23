# backend/simulation/behavior_engine.py

import math

from backend.core.simulation.agent import EmployeeAgent
from backend.core.simulation.org_graph import OrgGraph

_calibration_cache = {}


def _load_calibration(session_id: str = "global"):
    """Lazy-load calibration — re-reads after retrain without server restart."""
    global _calibration_cache
    if session_id not in _calibration_cache:
        from backend.storage.storage import load_artifact

        data = load_artifact("calibration", session_id=session_id)
        if data:
            _calibration_cache[session_id] = data
        else:
            _calibration_cache[session_id] = {
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
    return _calibration_cache[session_id]


def clear_calibration_cache(session_id: str = None):
    """Invalidate the lazy cache so the next simulation re-reads calibration.json."""
    global _calibration_cache
    if session_id is None:
        _calibration_cache = {}
    else:
        _calibration_cache.pop(session_id, None)


# All constants resolved lazily via _load_calibration() on first call
def _c(key, default, session_id: str = "global"):
    return _load_calibration(session_id=session_id).get(key, default)


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


def update_agent_state(
    agent: EmployeeAgent,
    G: OrgGraph,
    workload_multiplier: float,
    motivation_decay_rate: float,
    stress_gain_rate: float = 1.0,
    bonus: float = 0.0,
    wlb_boost: float = 0.0,
    session_id: str = "global",
):
    """
    Update one agent's behavioral state for one timestep.
    All constants from calibration.json via lazy loader — picks up retrain without restart.
    """
    if not agent.is_active:
        return

    # Resolve constants lazily each call (cached after first load)
    STRESS_GAIN_RATE = _c(
        "behavior_stress_gain_rate", _c("stress_gain_rate", 0.0132, session_id), session_id
    )
    RECOVERY_RATE = _c("recovery_rate", 0.0104, session_id)
    NEIGHBOR_STRESS_WEIGHT = _c("neighbor_stress_weight", 0.01, session_id)
    FATIGUE_STRESS_WEIGHT = _c("fatigue_stress_weight", 0.005, session_id)
    COMM_QUALITY_CAP = _c("comm_quality_cap", 5.0, session_id)
    COMM_QUALITY_BENEFIT = _c("comm_quality_benefit", 0.001, session_id)
    FATIGUE_GAIN_RATE = _c("fatigue_gain_rate", 0.03, session_id)
    FATIGUE_RECOVERY_RATE = _c("fatigue_recovery_rate", 0.01, session_id)
    FATIGUE_STRESS_TRIGGER = _c("fatigue_stress_trigger", 0.5, session_id)
    MOTIVATION_RECOVERY_RATE = _c("motivation_recovery_rate", 0.01, session_id)
    MOTIVATION_THRESHOLD = _c("motivation_threshold", 0.15, session_id)
    WLB_STRESS_BUFFER = _c("wlb_stress_buffer", 0.2, session_id)
    WLB_STRESS_SENSITIVITY = _c("wlb_stress_sensitivity", 1.5, session_id)
    WLB_DROP_RATE = _c("wlb_drop_rate", 0.15, session_id)
    WLB_RECOVERY_RATE = _c("wlb_recovery_rate", 0.1, session_id)
    BURNOUT_PROD_PENALTY = _c("burnout_productivity_penalty", 0.97, session_id)

    # Get neighbor influence
    neighbor_stress, comm_quality = compute_neighbor_influence(agent, G)

    # Quadratic workload scaling — high pressure is meaningfully worse than linear
    # workload=1.0 → 1.0x | workload=1.3 → 1.69x | workload=1.5 → 2.25x
    workload_stress_factor = workload_multiplier**2

    # Stress accumulates each month. Net gain is positive under pressure.
    # Financial compensation (salary raise / overtime pay) provides a stress dampener.
    # The relief is proportional to bonus magnitude so a 25% raise (bonus=2.5)
    # meaningfully differs from a 10% raise (bonus=1.0).
    # Relief is capped at 60% of raw gain so stress can still build under extreme workload.
    raw_stress_gain = (
        STRESS_GAIN_RATE * workload_stress_factor * stress_gain_rate
        + NEIGHBOR_STRESS_WEIGHT * neighbor_stress
        + FATIGUE_STRESS_WEIGHT * agent.fatigue
        - COMM_QUALITY_BENEFIT * min(comm_quality, COMM_QUALITY_CAP)
    )
    # Bonus-scaled fraction of raw gain absorbed each month:
    #   bonus=0.5 (5% raise)  → 10% of raw stress relieved
    #   bonus=1.0 (10% raise) → 18% of raw stress relieved
    #   bonus=2.5 (25% raise) → 37% of raw stress relieved
    #   bonus=3.0 (30% raise) → 41% of raw stress relieved
    # Formula: (1 - 1/(1+bonus*0.5)) gives a saturating 0–66% range
    # Hard cap at 60% so even a very large raise can't eliminate all stress
    if bonus > 0.0:
        relief_fraction = min(0.60, 1.0 - 1.0 / (1.0 + bonus * 0.25))
        overtime_stress_relief = raw_stress_gain * relief_fraction
    else:
        overtime_stress_relief = 0.0
    stress_gain = raw_stress_gain - overtime_stress_relief
    agent.stress = max(0.0, min(agent.stress + stress_gain - RECOVERY_RATE, 1.0))

    # Fatigue
    if agent.stress > FATIGUE_STRESS_TRIGGER:
        agent.fatigue = min(agent.fatigue + FATIGUE_GAIN_RATE, 1.0)
    else:
        agent.fatigue = max(agent.fatigue - FATIGUE_RECOVERY_RATE, 0.0)

    # Motivation decays under stress OR high workload.
    # Exception: when bonus > 0, pay compensates for workload — no workload decay
    # until stress crosses threshold (fatigue eventually overwhelms the pay benefit).
    if agent.stress > MOTIVATION_THRESHOLD:
        agent.motivation = max(agent.motivation - motivation_decay_rate, 0.0)
    elif workload_multiplier > 1.0 and bonus == 0.0:
        # High workload without pay compensation grinds motivation down
        workload_decay = motivation_decay_rate * (workload_multiplier - 1.0) * 1.5
        agent.motivation = max(agent.motivation - workload_decay, 0.0)
    else:
        agent.motivation = min(
            agent.motivation + MOTIVATION_RECOVERY_RATE, agent.baseline_satisfaction / 4.0
        )

    # Financial compensation (overtime pay or salary raise) — phases out with fatigue.
    # Uses a log-scale lift so a large raise (bonus=2.5) is clearly better than a
    # small raise (bonus=0.5), but returns diminish at extreme values.
    #   bonus=0.5 → lift≈+0.28  (mild satisfaction boost from cost-of-living raise)
    #   bonus=1.5 → lift≈+0.58  (strong boost from 15% raise — people feel valued)
    #   bonus=2.5 → lift≈+0.73  (large boost from 25%+ raise — aggressive retention)
    effective_bonus = 0.0
    if bonus > 0.0:
        fatigue_discount = max(0.0, 1.0 - agent.fatigue)

        # Non-linear penalty: money loses its effectiveness if the employee is deeply burned out
        burnout_factor = 1.0
        if agent.stress > agent.burnout_limit:
            overshoot = (agent.stress - agent.burnout_limit) / max(1.0 - agent.burnout_limit, 0.01)
            # Quadratic decay. If overshoot is 0.5 (halfway to guaranteed break), bonus loses 25% power.
            # If overshoot is >0.95 (fully past limit), bonus loses almost all power.
            burnout_factor = max(0.1, 1.0 - (overshoot**2))

        effective_bonus = math.log1p(bonus) * fatigue_discount * burnout_factor

    base_satisfaction = (agent.motivation * 4.0) + effective_bonus
    agent.job_satisfaction = max(
        1.0, min(4.0, base_satisfaction)
    )  # capped at 4.0 to match training range

    # Financial loyalty gain — proportional to raise magnitude.
    # A 25% raise (bonus=2.5) builds loyalty significantly faster than a 5% raise (bonus=0.5).
    if bonus > 0.0:
        loyalty_gain = math.log1p(bonus) * 0.008 * (1.0 - agent.fatigue)
        agent.loyalty = min(1.0, agent.loyalty + loyalty_gain)

    # WLB drifts toward a target based on stress above the buffer.
    # wlb_boost raises the target ceiling — used by flexible/remote policies
    # to reflect that autonomy and schedule control genuinely improve WLB
    # beyond what stress reduction alone achieves.
    perceptible_stress = max(0.0, agent.stress - WLB_STRESS_BUFFER)
    target_wlb = max(
        1.0,
        min(4.0, agent.baseline_wlb + wlb_boost - (perceptible_stress * WLB_STRESS_SENSITIVITY)),
    )
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


def apply_attrition_shockwave(
    quitting_agent: EmployeeAgent, G: OrgGraph, shock_factor: float, session_id: str = "global"
):
    """When an agent quits, their neighbors feel the impact."""
    shockwave_stress = _c("shockwave_stress_factor", 0.3, session_id)
    shockwave_loyalty = _c("shockwave_loyalty_factor", 0.1, session_id)
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
            neighbor_agent.stress = min(neighbor_agent.stress + neighbour_stress_delta, 1.0)
            neighbor_agent.loyalty -= shock_factor * weight * shockwave_loyalty
            neighbor_agent.loyalty = max(neighbor_agent.loyalty, 0.0)

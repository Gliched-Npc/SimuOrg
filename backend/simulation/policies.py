# backend/simulation/policies.py

import copy
from dataclasses import dataclass


@dataclass
class SimulationConfig:
    workload_multiplier:    float = 1.0
    motivation_decay_rate:  float = 0.005
    shock_factor:           float = 0.2
    hiring_active:          bool  = True
    layoff_ratio:           float = 0.0
    stress_gain_rate:       float = 1.0
    duration_months:        int   = 12
    overtime_bonus:         float = 0.0
    wlb_boost:              float = 0.0  # direct WLB lift (autonomy, flexibility, remote)


POLICIES = {
    "baseline": SimulationConfig(
        shock_factor=0.0,
        stress_gain_rate=0.75,
    ),

    "remote_work": SimulationConfig(
        workload_multiplier=0.9,
        motivation_decay_rate=0.004,
        shock_factor=0.15,
        stress_gain_rate=0.8,
        wlb_boost=0.3,   # remote cuts commute/office friction -> real WLB gain
    ),

    "flexible_work": SimulationConfig(
        workload_multiplier=0.85,
        motivation_decay_rate=0.002,
        shock_factor=0.1,
        stress_gain_rate=0.5,
        overtime_bonus=0.0,
        wlb_boost=0.5,   # schedule autonomy is the strongest WLB driver
    ),

    "kpi_pressure": SimulationConfig(
        workload_multiplier=1.3,
        motivation_decay_rate=0.012,
        shock_factor=0.25,
        stress_gain_rate=2.5,       # gradual burnout — crosses threshold by month 5-6
    ),

    "hiring_freeze": SimulationConfig(
        hiring_active=False,
        workload_multiplier=1.2,
        motivation_decay_rate=0.010,
        shock_factor=0.3,
        stress_gain_rate=2.5,
    ),

    "layoff": SimulationConfig(
        layoff_ratio=0.15,
        stress_gain_rate=5.0,       # panic level
        shock_factor=0.5,
        hiring_active=False,
        motivation_decay_rate=0.025,
    ),

    "promotion_freeze": SimulationConfig(
        motivation_decay_rate=0.025,
        workload_multiplier=1.1,
        shock_factor=0.2,
        stress_gain_rate=1.5,
    ),

    "overtime_pay": SimulationConfig(
        workload_multiplier=1.4,
        motivation_decay_rate=0.003,  # pay cushions motivation longer
        shock_factor=0.25,
        stress_gain_rate=2.0,         # lowered: fair pay means less subjective stress per hour
        overtime_bonus=2.0,           # dampens stress gain + raises job satisfaction
    ),
}


def get_policy(policy_name: str) -> SimulationConfig:
    if policy_name not in POLICIES:
        raise ValueError(f"Unknown policy: {policy_name}. "
                         f"Available: {list(POLICIES.keys())}")
    return copy.copy(POLICIES[policy_name])
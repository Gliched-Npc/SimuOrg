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
        stress_gain_rate=0.8,   # Standard operational friction
        motivation_decay_rate=0.005,
    ),

    "remote_work": SimulationConfig(
        workload_multiplier=0.9,
        motivation_decay_rate=0.012,  # ISOLATION: Higher decay due to lack of office touchpoints
        shock_factor=0.15,
        stress_gain_rate=0.6,         # COMMUTE RELIEF: Lowered stress gain
        wlb_boost=0.4,                
    ),

    "flexible_work": SimulationConfig(
        workload_multiplier=0.85,
        motivation_decay_rate=0.003,  # EMPOWERMENT: Lower decay due to high agency
        shock_factor=0.1,
        stress_gain_rate=1.2,         # DENSITY: Higher stress gain due to 'crunch' days
        wlb_boost=0.6,                # Schedule autonomy is the highest WLB driver
    ),

    "kpi_pressure": SimulationConfig(
        workload_multiplier=1.35,      # THE GRIND: High workload
        motivation_decay_rate=0.006,   
        shock_factor=0.10,
        stress_gain_rate=1.1,          # Manageable stress increase
    ),

    "hiring_freeze": SimulationConfig(
        hiring_active=False,
        workload_multiplier=1.25,      # OVERBURDEN: Work falls on survivors
        motivation_decay_rate=0.015,
        shock_factor=0.25,
        stress_gain_rate=2.8,          # Stress cascades quickly
    ),

    "layoff": SimulationConfig(
        layoff_ratio=0.15,
        stress_gain_rate=5.5,          # PANIC: Extreme stress spike
        shock_factor=0.6,              # Survivors feel immediate insecurity
        hiring_active=False,
        motivation_decay_rate=0.035,
    ),

    "promotion_freeze": SimulationConfig(
        motivation_decay_rate=0.040,   # STAGNATION: Devastating hit to identity/future
        workload_multiplier=1.0,       # Workload is normal, focus is on morale loss
        shock_factor=0.3,
        stress_gain_rate=1.0,
    ),

    "overtime_pay": SimulationConfig(
        workload_multiplier=1.45,      # INTENSIVE: High hours
        motivation_decay_rate=0.002,   # REWARD: Pay cushions the burden significantly
        shock_factor=0.3,
        stress_gain_rate=1.8,          # Still high stress, but lower than Hiring Freeze due to pay
        overtime_bonus=2.5,            # Strongest financial motivator
    ),
}


def get_policy(policy_name: str) -> SimulationConfig:
    if policy_name not in POLICIES:
        raise ValueError(f"Unknown policy: {policy_name}. "
                         f"Available: {list(POLICIES.keys())}")
    return copy.copy(POLICIES[policy_name])
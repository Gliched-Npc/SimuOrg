# backend/simulation/policies.py

from dataclasses import dataclass
import copy


@dataclass
class SimulationConfig:
    workload_multiplier:    float = 1.0
    motivation_decay_rate:  float = 0.005
    shock_factor:           float = 0.2
    hiring_active:          bool  = False
    layoff_ratio:           float = 0.0
    stress_gain_rate:       float = 1.0
    duration_months:        int   = 12


POLICIES = {
    "baseline": SimulationConfig(),

    "remote_work": SimulationConfig(
        workload_multiplier=0.9,
        motivation_decay_rate=0.004,
        shock_factor=0.15,
        stress_gain_rate=0.8,
    ),

    "kpi_pressure": SimulationConfig(
        workload_multiplier=1.3,
        motivation_decay_rate=0.008,
        shock_factor=0.25,
        stress_gain_rate=1.2,
    ),

    "hiring_freeze": SimulationConfig(
        hiring_active=False,
        workload_multiplier=1.2,
        motivation_decay_rate=0.008,
        shock_factor=0.25,
    ),

    "layoff": SimulationConfig(
        layoff_ratio=0.15,
        stress_gain_rate=1.8,
        shock_factor=0.4,
        hiring_active=False,
        motivation_decay_rate=0.02,
    ),

    "promotion_freeze": SimulationConfig(
        motivation_decay_rate=0.02,
        workload_multiplier=1.1,
        shock_factor=0.2,
    ),
}


def get_policy(policy_name: str) -> SimulationConfig:
    if policy_name not in POLICIES:
        raise ValueError(f"Unknown policy: {policy_name}. "
                         f"Available: {list(POLICIES.keys())}")
    return copy.copy(POLICIES[policy_name])
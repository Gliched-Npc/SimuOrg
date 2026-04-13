# backend/simulation/policies.py

import copy
import os
import json
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
    bonus:         float = 0.0
    wlb_boost:              float = 0.0


POLICIES = {
    "baseline": SimulationConfig(
        shock_factor=0.0,
        stress_gain_rate=0.8,
        motivation_decay_rate=0.005,
    ),

    "remote_work": SimulationConfig(
        workload_multiplier=0.9,
        motivation_decay_rate=0.004,  # ISOLATION: Higher decay due to lack of office touchpoints
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
        workload_multiplier=1.20,      # THE GRIND: High workload
        motivation_decay_rate=0.005,   
        shock_factor=0.10,
        stress_gain_rate=1.0,          # Manageable stress increase
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
        bonus=2.5,            # Strongest financial motivator
    ),

    "Gemini_policy": SimulationConfig(
        workload_multiplier=0.8,
        stress_gain_rate=0.7,
        wlb_boost=0.6,
        duration_months=3
    ),
}


def get_policy(policy_name: str, config_override: dict = None) -> SimulationConfig:
    """
    Return a SimulationConfig for the given policy name.

    Parameters
    ----------
    policy_name     : name of a built-in policy or "custom"
    config_override : if provided and policy_name == "custom", use this dict
                      directly instead of reading from disk (preferred path)
    """
    if policy_name == "custom":
        # Required: config dict passed in from the DB (via PolicyGenerationLog)
        if config_override is not None:
            return SimulationConfig(**config_override)
        raise ValueError(
            "No custom policy passed. Generate one via POST /api/llm/generate "
            "and pass the returned log_id as policy_log_id when running the simulation."
        )

    if policy_name not in POLICIES:
        raise ValueError(f"Unknown policy: {policy_name}. "
                         f"Available: {list(POLICIES.keys())} or 'custom'")
    return copy.copy(POLICIES[policy_name])

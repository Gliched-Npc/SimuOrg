# backend/core/llm/bounds.py

def get_param_bounds(calib: dict) -> dict:
    """
    Defines the safe minimum and maximum bounds for LLM-generated configurations.
    Multipliers are dynamically restricted based on the company's specific calibration anchors.
    """
    sgr = calib.get("behavior_stress_gain_rate", 0.01)
    mdr = calib.get("motivation_recovery_rate", 0.005)
    
    return {
        "workload_multiplier":   (0.4, 1.6),
        "stress_gain_rate":      (0.4 * sgr, 9.0 * sgr),
        "motivation_decay_rate": (0.3 * mdr, 10.0 * mdr),
        "shock_factor":          (0.0, 0.7),
        "layoff_ratio":          (0.0, 0.3),
        "bonus":                 (0.0, 5.0),
        "wlb_boost":             (-0.5, 1.0),
        "duration_months":       (1, 36),
    }

def clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))

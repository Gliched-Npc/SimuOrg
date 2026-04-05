def build_context(calib: dict) -> dict:
    """
    Extracts only the safe calibration anchors needed for LLM reasoning.
    Never passes the raw dataset or other sensitive params to the LLM.
    """
    return {
        "annual_attrition_rate":     calib.get("annual_attrition_rate", 0),
        "behavior_stress_gain_rate": calib.get("behavior_stress_gain_rate", 0),
        "motivation_recovery_rate":  calib.get("motivation_recovery_rate", 0),
        "avg_burnout_limit":         calib.get("avg_burnout_limit", 0),
        "calib_quality":             calib.get("calib_quality", "unknown"),
        "calib_attrition_std":       calib.get("calib_attrition_std", 0),
    }

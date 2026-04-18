# backend/services/simulation_service.py
# Placeholder — simulation orchestration service will go here.

# Orchestration layer between API/workers and core simulation.
# Routes and Celery tasks call this — never core directly.

from backend.core.simulation.monte_carlo import run_monte_carlo
from backend.core.simulation.policies import POLICIES, get_policy


def run_simulation_job(
    policy_name: str,
    runs: int = 10,
    duration_months: int | None = None,
    seed: int = 42,
    policy_config: dict | None = None,
) -> dict:
    """
    Run a Monte Carlo simulation for a given policy.
    Returns the full result dict from run_monte_carlo.

    policy_config: if provided and policy_name == "custom", uses this dict
                   directly instead of reading from disk.
    """
    if policy_name != "custom" and policy_name not in POLICIES:
        raise ValueError(f"Unknown policy: {policy_name}")

    config = get_policy(policy_name, config_override=policy_config)
    if duration_months is not None:
        config.duration_months = duration_months

    return run_monte_carlo(config, runs=runs, policy_name=policy_name, seed=seed)


def compare_simulation_jobs(
    policy_a: str,
    policy_b: str,
    runs: int = 10,
    duration_months: int | None = None,
    seed: int = 42,
) -> dict:
    """
    Run two policies and return combined comparison result.
    """
    if policy_a != "custom" and policy_a not in POLICIES:
        raise ValueError(f"Unknown policy: {policy_a}")
    if policy_b != "custom" and policy_b not in POLICIES:
        raise ValueError(f"Unknown policy: {policy_b}")

    config_a = get_policy(policy_a)
    if duration_months is not None:
        config_a.duration_months = duration_months

    config_b = get_policy(policy_b)
    if duration_months is not None:
        config_b.duration_months = duration_months

    result_a = run_monte_carlo(config_a, runs=runs, policy_name=policy_a, seed=seed)
    result_b = run_monte_carlo(config_b, runs=runs, policy_name=policy_b, seed=seed)

    return {"policy_a": result_a, "policy_b": result_b}


def run_training_job(quality_report: dict = None) -> dict:
    """
    Run full ML training pipeline.
    Returns calibration result.
    """
    import backend.core.simulation.agent as _agent_module
    from backend.core.ml.attrition_model import train_attrition_model
    from backend.core.ml.burnout_estimator import train_burnout_estimator
    from backend.core.ml.calibration import calibrate

    pre_clean = (
        {
            "trust_score": quality_report.get("trust_score", 100),
            "cleaning_audit": quality_report.get("cleaning_audit", []),
            "status": quality_report.get("status", "healthy"),
        }
        if quality_report
        else None
    )

    model_quality = train_attrition_model(pre_clean_metrics=pre_clean)
    train_burnout_estimator()
    _agent_module._quit_model_cache = None  # bust lazy-load cache
    _agent_module._quit_features_cache = None  # force reload of schema
    _agent_module._quit_encoders_cache = None  # force reload of encoders
    cal = calibrate()

    return {
        "model": {
            "auc_roc": model_quality.get("auc_roc"),
            "cv_auc_mean": model_quality.get("cv_auc_mean"),
            "features": model_quality.get("features_used"),
            "signal": model_quality.get("signal_strength"),
            "recommendation": model_quality.get("recommendation"),
        },
        "calibration": {
            "annual_attrition_rate": cal.get("annual_attrition_rate"),
            "empirical_attrition_rate": cal.get("empirical_attrition_rate"),
            "monthly_natural_rate": cal.get("monthly_natural_rate"),
            "quit_threshold": cal.get("quit_threshold"),
            "calib_quality": cal.get("calib_quality"),
            "calib_attrition_std": cal.get("calib_attrition_std"),
        },
    }

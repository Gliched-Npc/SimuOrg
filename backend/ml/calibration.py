# backend/ml/calibration.py

import numpy as np
import joblib
import json
import os
import pandas as pd
from sqlmodel import Session, select
from backend.database import engine
from backend.models import Employee
from backend.ml.burnout_estimator import burnout_threshold
from backend.ml.attrition_model import engineer_features


def calibrate(save_path="backend/ml/exports/calibration.json"):
    print("🔧 Running simulation calibration...")

    with Session(engine) as session:
        employees = session.exec(select(Employee)).all()

    if not employees:
        raise ValueError("No employees found in database. Run upload/ingest first.")

    model_path = "backend/ml/exports/quit_probability.pkl"
    if not os.path.exists(model_path):
        raise ValueError(
            f"Quit probability model not found at '{model_path}'. "
            "Train the attrition model before running calibration."
        )

    _saved          = joblib.load(model_path)
    quit_model      = _saved["model"]
    tuned_threshold = _saved["threshold"]
    saved_features  = _saved["features"]  # use exact features model was trained on
    saved_encoders  = _saved.get("label_encoders", {})  # pre-fitted encoders (backwards-compatible)

    # ── Batch prediction (vectorized — replaces per-employee loop) ──
    records = [{
        "job_satisfaction":           emp.job_satisfaction,
        "work_life_balance":          emp.work_life_balance,
        "environment_satisfaction":   emp.environment_satisfaction,
        "job_involvement":            emp.job_involvement,
        "monthly_income":             emp.monthly_income,
        "years_at_company":           emp.years_at_company,
        "total_working_years":        emp.total_working_years,
        "num_companies_worked":       emp.num_companies_worked,
        "job_level":                  emp.job_level,
        "years_since_last_promotion": emp.years_since_last_promotion,
        "years_with_curr_manager":    emp.years_with_curr_manager,
        "performance_rating":         emp.performance_rating,
        "stock_option_level":         emp.stock_option_level,
        "age":                        emp.age,
        "distance_from_home":         emp.distance_from_home,
        "percent_salary_hike":        emp.percent_salary_hike,
        "years_in_current_role":      getattr(emp, "years_in_current_role", 0) or 0,
        "marital_status":             emp.marital_status,
        "overtime":                   getattr(emp, "overtime", 0) or 0,
        "business_travel":            getattr(emp, "business_travel", 0) or 0,
        # Needed so engineer_features can create department_encoded / job_role_encoded
        "department":                 getattr(emp, "department", None),
        "job_role":                   getattr(emp, "job_role", None),
        "attrition":                  emp.attrition,
    } for emp in employees]

    df_all = pd.DataFrame(records)
    df_all = engineer_features(df_all, encoders=saved_encoders)

    # Single batch call — massively faster than N individual predict_proba calls
    quit_probs     = quit_model.predict_proba(df_all[saved_features])[:, 1]
    burnout_limits = np.array([
        burnout_threshold(emp.job_level, emp.total_working_years) for emp in employees
    ])
    labels = (df_all["attrition"] == "Yes").astype(int).values


    attrition_counts = sum(1 for emp in employees if emp.attrition == "Yes")
    total            = len(employees)
    annual_attrition_rate = attrition_counts / total if attrition_counts > 0 else 0.15

    monthly_natural_rate  = 1 - (1 - annual_attrition_rate) ** (1 / 12)
    monthly_probs        = 1 - (1 - quit_probs) ** (1 / 12)
    mean_monthly_prob    = float(np.mean(monthly_probs))
    if mean_monthly_prob > 0:
        raw_prob_scale = monthly_natural_rate / mean_monthly_prob
        # Keep within a reasonable band so tiny probabilities don't explode the scale.
        prob_scale = round(float(min(max(raw_prob_scale, 0.1), 5.0)), 4)
    else:
        prob_scale = 1.0

    quitter_probs         = quit_probs[labels == 1]
    stayer_probs          = quit_probs[labels == 0]
    mean_quitter          = float(np.mean(quitter_probs)) if len(quitter_probs) > 0 else 0.5
    mean_stayer           = float(np.mean(stayer_probs))  if len(stayer_probs)  > 0 else 0.2

    # Convert to monthly before computing ratio — avoids compounding mismatch
    mean_quitter_monthly  = 1 - (1 - mean_quitter) ** (1/12)
    mean_stayer_monthly   = 1 - (1 - mean_stayer)  ** (1/12)
    if mean_stayer_monthly > 0:
        raw_stress_amp = mean_quitter_monthly / mean_stayer_monthly
        # Clamp to avoid extreme ratios when quitter/stayer risks are almost identical or very noisy.
        stress_amplification = round(float(min(max(raw_stress_amp, 1.0), 10.0)), 4)
    else:
        stress_amplification = 2.0

    avg_job_satisfaction  = np.mean([emp.job_satisfaction for emp in employees])
    avg_work_life_balance = np.mean([emp.work_life_balance for emp in employees])

    # ── Data-driven stress physics ──
    # stress_gain and recovery derived from stress_amplification + observed natural quit rate.
    # The base multiplier is no longer hardcoded (0.02/0.015) — it is anchored to:
    #   monthly_natural_rate: observed monthly attrition speed
    #   avg_burnout_limit:    how much stress employees can absorb
    # Ratio of gain:recovery ← sqrt(stress_amplification) (geometric mean between max/min)
    gain_to_recovery_ratio = stress_amplification ** 0.5
    # Natural drift = how fast accumulated stress should grow for "average" employee
    #   anchored to monthly_natural_rate × burnout_limit (so drift ∝ real attrition)
    natural_drift = monthly_natural_rate * float(np.mean(burnout_limits))
    # With formula: gain - recovery = natural_drift, and gain/recovery = ratio:
    # Guard against ratio ~= 1 which would make the denominator tiny.
    if abs(gain_to_recovery_ratio - 1.0) < 1e-3:
        # Symmetric gain/recovery around natural drift to avoid numerical blow-up.
        base_gain = natural_drift * 0.75
        base_recovery = natural_drift * 0.25
    else:
        base_recovery  = natural_drift / (gain_to_recovery_ratio - 1)
        base_gain      = base_recovery * gain_to_recovery_ratio
    # Scale by actual satisfaction/WLB (same formula structure as before, but base is data-driven)
    stress_gain_rate = base_gain     * (1 - (avg_job_satisfaction / 4.0) * 0.5)
    recovery_rate    = base_recovery * (avg_work_life_balance / 4.0)
    # Final clamp of rates to a stable numeric range for month-level simulation.
    stress_gain_rate = round(float(min(max(stress_gain_rate, 0.0), 0.05)), 4)
    recovery_rate    = round(float(min(max(recovery_rate, 0.0), 0.05)), 4)

    avg_loyalty              = np.mean([min(emp.years_at_company / 10.0, 1.0) for emp in employees])
    shockwave_stress_factor  = round(0.3 * (1 - avg_loyalty * 0.3), 4)
    shockwave_loyalty_factor = round(0.1 * (1 - avg_loyalty * 0.2), 4)

    # ── Data-driven stress threshold ──
    # Use the actual attrition rate as the percentile -> the stress threshold
    # corresponds to the burnout tolerance of employees in the "attrition risk zone"
    attrition_percentile = annual_attrition_rate * 100  # e.g., 16.1
    stress_threshold     = round(float(np.percentile(burnout_limits, attrition_percentile)), 4)

    # ── Data-driven behavior engine constants ──
    # These replace all hardcoded floats in behavior_engine.py.
    # Each is derived from real employee data so the simulation adapts per dataset.

    avg_burnout = float(np.mean(burnout_limits))
    std_burnout = float(np.std(burnout_limits))

    # Neighbor stress influence — scaled by loyalty (high-loyalty orgs feel departures less)
    neighbor_stress_weight = round(monthly_natural_rate * (1 - avg_loyalty * 0.5), 4)

    # Fatigue contribution to stress — proportional to how tight burnout limits are
    fatigue_stress_weight = round(neighbor_stress_weight * 0.5, 4)

    # Communication quality cap — derived from inverse of stress_amplification
    # High-amplification datasets (big gap between quitter/stayer probs) get less comm benefit
    comm_quality_cap = round(max(3.0, min(8.0, 1.0 / monthly_natural_rate * 0.1)), 4)
    comm_quality_benefit = round(monthly_natural_rate * 0.1, 4)

    # Fatigue rates — derived from burnout limit distribution
    # Gain rate: how fast fatigue builds when stressed (faster if burnout limits are tight)
    fatigue_gain_rate    = round(monthly_natural_rate * 2.0, 4)
    # Recovery rate: how fast fatigue heals when not stressed (tied to WLB)
    fatigue_recovery_rate = round(fatigue_gain_rate * (avg_work_life_balance / 4.0) * 0.4, 4)

    # Stress threshold for fatigue accumulation — reuse burnout midpoint
    fatigue_stress_trigger = round(avg_burnout * 0.85, 4)

    # Motivation recovery — tied to how satisfied the workforce is
    motivation_recovery_rate = round((avg_job_satisfaction / 4.0) * monthly_natural_rate * 0.8, 4)

    # WLB decay mechanics — the key fix for KPI_PRESSURE responsiveness
    # Buffer: stress level below which WLB doesn't degrade (derived from stress_threshold)
    wlb_stress_buffer = round(stress_threshold * 0.45, 4)

    # WLB stress sensitivity: how strongly stress above buffer impacts WLB target
    # Driven by stress_amplification — high-amplification = stress matters more for WLB
    wlb_stress_sensitivity = round(stress_amplification ** 0.5 * 0.5, 4)

    # WLB drop rate: max WLB drop per month — proportional to monthly quit rate * amplification
    # This is the key cap that was previously hardcoded at 0.15
    wlb_drop_rate = round(monthly_natural_rate * stress_amplification ** 0.5 * 1.5, 4)

    # WLB recovery: how fast WLB recovers when stress is low
    wlb_recovery_rate = round(wlb_drop_rate * (avg_work_life_balance / 4.0) * 0.6, 4)

    # Burnout productivity penalty — derived from how severe burnout is in this dataset
    # More extreme burnout distribution = harder productivity hit
    burnout_severity = min(1.0, std_burnout / avg_burnout) if avg_burnout > 0 else 0.3
    burnout_productivity_penalty = round(1.0 - (burnout_severity * 0.05), 4)

    calibration = {
        "quit_threshold":           tuned_threshold,
        "stress_threshold":         stress_threshold,
        "avg_quit_prob":            round(float(np.mean(quit_probs)), 4),
        "avg_burnout_limit":        round(avg_burnout, 4),
        "annual_attrition_rate":    round(annual_attrition_rate, 4),
        "monthly_natural_rate":     round(monthly_natural_rate, 4),
        "stress_gain_rate":         stress_gain_rate,
        "recovery_rate":            recovery_rate,
        "natural_scale":            1,
        "shockwave_stress_factor":  shockwave_stress_factor,
        "shockwave_loyalty_factor": shockwave_loyalty_factor,
        "prob_scale":               prob_scale,
        "stress_amplification":     stress_amplification,
        # Behavior engine constants (all data-driven)
        "neighbor_stress_weight":      neighbor_stress_weight,
        "fatigue_stress_weight":       fatigue_stress_weight,
        "comm_quality_cap":            comm_quality_cap,
        "comm_quality_benefit":        comm_quality_benefit,
        "fatigue_gain_rate":           fatigue_gain_rate,
        "fatigue_recovery_rate":       fatigue_recovery_rate,
        "fatigue_stress_trigger":      fatigue_stress_trigger,
        "motivation_recovery_rate":    motivation_recovery_rate,
        "wlb_stress_buffer":           wlb_stress_buffer,
        "wlb_stress_sensitivity":      wlb_stress_sensitivity,
        "wlb_drop_rate":               wlb_drop_rate,
        "wlb_recovery_rate":           wlb_recovery_rate,
        "burnout_productivity_penalty": burnout_productivity_penalty,
    }


    os.makedirs("backend/ml/exports", exist_ok=True)
    with open(save_path, "w") as f:
        json.dump(calibration, f, indent=2)

    print("+++ Calibration complete:")
    for k, v in calibration.items():
        print(f"   {k}: {v}")

    return calibration


if __name__ == "__main__":
    calibrate()

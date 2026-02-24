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
from backend.ml.attrition_model import engineer_features, FEATURES


def calibrate(save_path="backend/ml/exports/calibration.json"):
    print("🔧 Running simulation calibration...")

    with Session(engine) as session:
        employees = session.exec(select(Employee)).all()

    if not employees:
        raise ValueError("No employees found in database. Run upload/ingest first.")

    _saved          = joblib.load("backend/ml/exports/quit_probability.pkl")
    quit_model      = _saved["model"]
    tuned_threshold = _saved["threshold"]
    saved_features  = _saved["features"]  # use exact features model was trained on

    quit_probs    = []
    burnout_limits = []
    labels=[]
    for emp in employees:
        df_emp = pd.DataFrame([{
            "job_satisfaction":            emp.job_satisfaction,
            "work_life_balance":           emp.work_life_balance,
            "environment_satisfaction":    emp.environment_satisfaction,
            "job_involvement":             emp.job_involvement,
            "monthly_income":              emp.monthly_income,
            "years_at_company":            emp.years_at_company,
            "total_working_years":         emp.total_working_years,
            "num_companies_worked":        emp.num_companies_worked,
            "job_level":                   emp.job_level,
            "years_since_last_promotion":  emp.years_since_last_promotion,
            "years_with_curr_manager":     emp.years_with_curr_manager,
            "performance_rating":          emp.performance_rating,
            "stock_option_level":          emp.stock_option_level,
            "age":                         emp.age,
            "distance_from_home":          emp.distance_from_home,
            "percent_salary_hike":         emp.percent_salary_hike,
            "years_in_current_role":       getattr(emp, "years_in_current_role", 0) or 0,
            "marital_status":              emp.marital_status,
            # Optional — only present if dataset had OverTime / BusinessTravel
            "overtime":                    getattr(emp, "overtime", 0) or 0,
            "business_travel":             getattr(emp, "business_travel", 0) or 0,
        }])
        df_emp = engineer_features(df_emp)

        # Use only the features the model was actually trained on
        prob = quit_model.predict_proba(df_emp[saved_features])[0][1]
        quit_probs.append(prob)
        burnout_limits.append(burnout_threshold(emp.job_level, emp.total_working_years))
        labels.append(1 if emp.attrition == "Yes" else 0)

    quit_probs     = np.array(quit_probs)
    burnout_limits = np.array(burnout_limits)
    labels         = np.array(labels)

    attrition_counts = sum(1 for emp in employees if emp.attrition == "Yes")
    total            = len(employees)
    annual_attrition_rate = attrition_counts / total if attrition_counts > 0 else 0.15

    monthly_natural_rate  = 1 - (1 - annual_attrition_rate) ** (1 / 12)
    monthly_probs        = 1 - (1 - quit_probs) ** (1 / 12)
    mean_monthly_prob    = float(np.mean(monthly_probs))
    prob_scale           = round(monthly_natural_rate / mean_monthly_prob, 4) if mean_monthly_prob > 0 else 1.0

    quitter_probs         = quit_probs[labels == 1]
    stayer_probs          = quit_probs[labels == 0]
    mean_quitter          = float(np.mean(quitter_probs)) if len(quitter_probs) > 0 else 0.5
    mean_stayer           = float(np.mean(stayer_probs))  if len(stayer_probs)  > 0 else 0.2

    # Convert to monthly before computing ratio — avoids compounding mismatch
    mean_quitter_monthly  = 1 - (1 - mean_quitter) ** (1/12)
    mean_stayer_monthly   = 1 - (1 - mean_stayer)  ** (1/12)
    stress_amplification  = round(mean_quitter_monthly / mean_stayer_monthly, 4) if mean_stayer_monthly > 0 else 2.0

    avg_job_satisfaction  = np.mean([emp.job_satisfaction for emp in employees])
    avg_work_life_balance = np.mean([emp.work_life_balance for emp in employees])

    stress_gain_rate = round(0.02 * (1 - (avg_job_satisfaction / 4.0) * 0.5), 4)
    recovery_rate    = round(0.015 * (avg_work_life_balance / 4.0), 4)

    avg_loyalty              = np.mean([min(emp.years_at_company / 10.0, 1.0) for emp in employees])
    shockwave_stress_factor  = round(0.3 * (1 - avg_loyalty * 0.3), 4)
    shockwave_loyalty_factor = round(0.1 * (1 - avg_loyalty * 0.2), 4)

    calibration = {
        "quit_threshold":        tuned_threshold,
        "stress_threshold":      round(float(np.percentile(burnout_limits, 30)), 4),
        "avg_quit_prob":         round(float(np.mean(quit_probs)), 4),
        "avg_burnout_limit":     round(float(np.mean(burnout_limits)), 4),
        "annual_attrition_rate": round(annual_attrition_rate, 4),
        "monthly_natural_rate":  round(monthly_natural_rate, 4),
        "stress_gain_rate":      stress_gain_rate,
        "recovery_rate":         recovery_rate,
        "natural_scale":         1,
        "shockwave_stress_factor":  shockwave_stress_factor,
        "shockwave_loyalty_factor": shockwave_loyalty_factor,
        "prob_scale":            prob_scale,
        "stress_amplification":  stress_amplification,
    }

    os.makedirs("backend/ml/exports", exist_ok=True)
    with open(save_path, "w") as f:
        json.dump(calibration, f, indent=2)

    print("✅ Calibration complete:")
    for k, v in calibration.items():
        print(f"   {k}: {v}")

    return calibration


if __name__ == "__main__":
    calibrate()
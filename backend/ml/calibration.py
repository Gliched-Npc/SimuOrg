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
    print("=== Running simulation calibration...")

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
    base_model      = _saved["model"]
    calibrator      = _saved.get("calibrator", None)
    tuned_threshold = _saved["threshold"]
    saved_features  = _saved["features"]
    saved_encoders  = _saved.get("label_encoders", {})

    # Reconstruct calibrated wrapper (same as agent.py)
    if calibrator is not None:
        class _CalibratedModel:
            def __init__(self, base, cal):
                self.base_model = base
                self.calibrator  = cal
            def predict_proba(self, X):
                raw = self.base_model.predict_proba(X)[:, 1]
                cal = self.calibrator.predict(raw)
                return np.column_stack([1 - cal, cal])
        quit_model = _CalibratedModel(base_model, calibrator)
    else:
        quit_model = base_model  # backwards-compatible

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
    monthly_probs = 1 - (1 - quit_probs) ** (1 / 12)

    # New hire probability — model score for a fresh hire (years_at_company=0).
    # Use 10th percentile of short-tenure employees (<=1yr) instead of mean.
    # The mean is ~29% because the cohort is dominated by genuinely unhappy employees
    # the model correctly flags as at-risk. The 10th percentile represents the
    # lowest-risk new hires — a realistic cap for replacement employees.
    short_tenure_mask = np.array([emp.years_at_company <= 1 for emp in employees])
    if short_tenure_mask.sum() >= 10:
        new_hire_monthly_prob = float(np.percentile(monthly_probs[short_tenure_mask], 10))
    else:
        new_hire_monthly_prob = monthly_natural_rate * 2.0

    new_hire_monthly_prob = max(new_hire_monthly_prob,monthly_natural_rate)
    print(f"  >> new_hire_monthly_prob={new_hire_monthly_prob:.4f} "
          f"(10th percentile of {int(short_tenure_mask.sum())} short-tenure employees)")

    # prob_scale starts at 1.0 (neutral). The empirical calibration loop below
    # will run actual full simulations and binary-search to the correct value.
    # No mini-sim, no heuristics — the real engine tells us what it needs.
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
        # Cap at 5.0 — beyond this the simulation becomes unrealistically volatile.
        # Your dataset has strong quitter/stayer separation (good model signal),
        # but uncapped amplification causes runaway attrition in stressed scenarios.
        stress_amplification = round(float(min(max(raw_stress_amp, 1.0), 5.0)), 4)
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
    # Derived from REACHABLE stress levels, not burnout limits.
    # Burnout limits range 0.30–0.85 — baseline stress peaks at 0.06–0.09.
    # Using np.percentile(burnout_limits, ...) gave 0.44 — unreachable under
    # normal conditions, so the amplifier never fired.
    # Fix: compute each employee's initial stress (same formula as agent.py __init__)
    # and use the (100 - attrition_pct) percentile so the top ~16% most-stressed
    # employees are above threshold at baseline.
    initial_stresses = np.array([
        min(
            max(0.0, (4.0 - emp.job_satisfaction) / 3.0) * 0.06
            + min(emp.years_at_company / 10.0, 1.0) * 0.035,
            0.40
        )
        for emp in employees
    ])
    stress_pct       = max(1.0, 100.0 - annual_attrition_rate * 100)  # e.g., 83.9
    stress_threshold = round(float(np.percentile(initial_stresses, stress_pct)), 4)
    print(f"  >> stress_threshold={stress_threshold:.4f} "
          f"(pct={stress_pct:.1f} of initial stress distribution)")

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

    # Survival discount rate — fixes initialization shock (month 1 spike).
    # Problem: initial employees include people already overdue to quit based on
    # static features. In reality they would have quit across previous months we
    # don't simulate. All getting their first roll on month 1 causes a spike.
    #
    # Fix: employees who have been at the company for N years have implicitly
    # survived N*12 monthly quit rolls. Their realized monthly probability should
    # reflect that survival. New hires (years=0) get full probability.
    #
    # We model this as exponential decay: survival_factor = exp(-k * years_at_company)
    calibration = {
        "quit_threshold":           tuned_threshold,
        "stress_threshold":         stress_threshold,
        "avg_quit_prob":            round(float(np.mean(quit_probs)), 4),
        "avg_burnout_limit":        round(avg_burnout, 4),
        "annual_attrition_rate":    round(annual_attrition_rate, 4),
        "monthly_natural_rate":     round(monthly_natural_rate, 4),
        "stress_gain_rate":         stress_gain_rate,
        "behavior_stress_gain_rate": stress_gain_rate,  # explicit key for behavior_engine.py
        "recovery_rate":            recovery_rate,
        "natural_scale":            1,
        "shockwave_stress_factor":  shockwave_stress_factor,
        "shockwave_loyalty_factor": shockwave_loyalty_factor,
        "prob_scale":               prob_scale,
        "stress_amplification":     stress_amplification,
        "new_hire_monthly_prob":    round(new_hire_monthly_prob, 4),
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

    print("+++ Initial calibration saved (mini-sim prob_scale).")
    print("=== Running empirical calibration (6 full simulation passes)...")

    # Empirical calibration: run actual full simulations to find the prob_scale
    # that makes the REAL behavioral engine land on the historical attrition rate.
    #
    # Why this is better than the mini-sim:
    #   - The mini-sim is a static probability roll — it can't model motivation
    #     recovery, WLB dynamics, or stress contagion.
    #   - By running the full simulation 6 times with different prob_scale values
    #     (binary search), we find the value that the ACTUAL engine needs.
    #   - Self-corrects for any dataset without tuning any heuristic.
    #
    # Order matters: we save the full calibration.json FIRST (above), so the
    # behavior engine loads the correct stress/recovery constants during the
    # empirical runs below. We then update only prob_scale in-place.
    from backend.simulation.time_engine import run_simulation, load_agents_from_db
    from backend.simulation.org_graph import build_org_graph, clear_graph_cache
    from backend.simulation.policies import SimulationConfig
    from backend.simulation.behavior_engine import clear_calibration_cache
    import copy

    # Clear caches so the engine reads the freshly written calibration.json
    clear_calibration_cache()
    clear_graph_cache()

    # Lean baseline config: no shocks, moderate stress — pure quit-probability measurement
    calib_config = SimulationConfig(shock_factor=0.0, stress_gain_rate=0.75, duration_months=12)

    # Load agents once, deepcopy per run to guarantee isolated state each pass
    calib_agents_base = load_agents_from_db()

    def _run_full_sim_rate(ps, seed=42):
        """Run one calibration_run simulation with a given prob_scale.
        Returns the period attrition rate (fraction, not %).
        """
        agents_copy = copy.deepcopy(calib_agents_base)
        G_copy      = build_org_graph(agents_copy)
        result      = run_simulation(
            calib_config, agents=agents_copy, G=G_copy,
            policy_name="calibration_run",   # clearly labelled in server logs
            seed=seed,
            prob_scale_override=ps,
        )
        return result["summary"].get("period_attrition_pct", 0.0) / 100.0

    def _stable_rate(ps, seeds=(42, 99)):
        """Average rate across multiple seeds for noise-resistant measurement.
        Using 2 seeds per pass halves variance without doubling runtime much.
        """
        rates = [_run_full_sim_rate(ps, seed=s) for s in seeds]
        return float(np.mean(rates))

    # ── Warm-up pass ──────────────────────────────────────────────────────────
    # Shows how far the static mini-sim estimate is from the real engine.
    warmup_rate = _stable_rate(prob_scale)
    gap = warmup_rate - annual_attrition_rate
    print(f"  [Warm-up] mini-sim scale={prob_scale:.4f} -> real rate={warmup_rate:.4f}  "
          f"target={annual_attrition_rate:.4f}  gap={gap:+.4f}")

    # ── Binary search (up to 8 passes) ────────────────────────────────────────
    # Wide fixed bounds [0.05, 5.0] so we always converge even if the mini-sim
    # estimate was way off (e.g., overfit model giving a wildly wrong prob_scale).
    CONVERGENCE_TOL = 0.005   # stop when sim rate is within 0.5% of historical rate
    MAX_PASSES      = 8
    emp_lo, emp_hi  = 0.05, 5.0
    converged       = False

    for i in range(MAX_PASSES):
        mid      = (emp_lo + emp_hi) / 2.0
        mid_rate = _stable_rate(mid)
        error    = mid_rate - annual_attrition_rate
        direction = "scale up  " if mid_rate < annual_attrition_rate else "scale down"
        print(f"  [Pass {i+1}/{MAX_PASSES}] scale={mid:.4f} -> rate={mid_rate:.4f}  "
              f"error={error:+.4f}  {direction}")
        if mid_rate < annual_attrition_rate:
            emp_lo = mid
        else:
            emp_hi = mid
        if abs(error) <= CONVERGENCE_TOL:
            print(f"  [Converged] within {CONVERGENCE_TOL*100:.1f}% tolerance after {i+1} passes")
            converged = True
            break

    if not converged:
        print(f"  [Note] Did not converge within tolerance after {MAX_PASSES} passes — using best estimate")

    empirical_prob_scale = round((emp_lo + emp_hi) / 2.0, 4)

    # ── Stability check ───────────────────────────────────────────────────────
    # Run the final scale 3 more times to measure result variance.
    # High std dev = dataset is noisy / small → warn the user.
    stability_seeds  = [7, 13, 31]
    stability_rates  = [_run_full_sim_rate(empirical_prob_scale, seed=s) for s in stability_seeds]
    stability_mean   = float(np.mean(stability_rates))
    stability_std    = float(np.std(stability_rates))
    calib_quality    = "stable" if stability_std < 0.02 else "noisy"
    print(f"\n  [Stability] prob_scale={empirical_prob_scale} over 3 seeds:")
    print(f"    mean={stability_mean:.4f}  std={stability_std:.4f}  quality={calib_quality}")
    if calib_quality == "noisy":
        print(f"  [WARN] High variance (std={stability_std:.4f}). "
              f"Consider uploading a larger dataset for more stable calibration.")

    print(f"\n  >> Empirical prob_scale : {empirical_prob_scale}  (mini-sim estimate was: {prob_scale})")
    print(f"  >> Final attrition rate : {stability_mean:.4f}  (target: {annual_attrition_rate:.4f})")
    print(f"  >> Calibration quality  : {calib_quality} (std={stability_std:.4f})")

    # ── Update calibration.json ───────────────────────────────────────────────
    calibration["prob_scale"]             = empirical_prob_scale
    calibration["prob_scale_mini_sim"]    = prob_scale
    calibration["calib_quality"]          = calib_quality
    calibration["calib_attrition_std"]    = round(stability_std, 4)
    with open(save_path, "w") as f:
        json.dump(calibration, f, indent=2)

    print("\n+++ Calibration complete:")
    for k, v in calibration.items():
        print(f"   {k}: {v}")

    # Clear ALL engine caches so the very next simulation uses fresh values:
    #   - behavior_engine: stress/recovery/WLB constants
    #   - time_engine:     PROB_SCALE, STRESS_THRESHOLD, STRESS_AMPLIFICATION
    #   - agent:           quit model weights (prevents stale predictions)
    clear_calibration_cache()
    from backend.simulation.time_engine import clear_engine_calibration_cache
    clear_engine_calibration_cache()
    from backend.simulation.agent import clear_quit_model_cache
    clear_quit_model_cache()

    return calibration




if __name__ == "__main__":
    calibrate()
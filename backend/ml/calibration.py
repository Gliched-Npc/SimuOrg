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

    new_hire_monthly_prob = max(new_hire_monthly_prob, monthly_natural_rate)
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
    gain_to_recovery_ratio = stress_amplification ** 0.5
    natural_drift = monthly_natural_rate * float(np.mean(burnout_limits))
    if abs(gain_to_recovery_ratio - 1.0) < 1e-3:
        base_gain = natural_drift * 0.75
        base_recovery = natural_drift * 0.25
    else:
        base_recovery  = natural_drift / (gain_to_recovery_ratio - 1)
        base_gain      = base_recovery * gain_to_recovery_ratio
    stress_gain_rate = base_gain     * (1 - (avg_job_satisfaction / 4.0) * 0.5)
    recovery_rate    = base_recovery * (avg_work_life_balance / 4.0)
    stress_gain_rate = round(float(min(max(stress_gain_rate, 0.0), 0.05)), 4)
    recovery_rate    = round(float(min(max(recovery_rate, 0.0), 0.05)), 4)

    avg_loyalty              = np.mean([min(emp.years_at_company / 10.0, 1.0) for emp in employees])
    shockwave_stress_factor  = round(0.3 * (1 - avg_loyalty * 0.3), 4)
    shockwave_loyalty_factor = round(0.1 * (1 - avg_loyalty * 0.2), 4)

    # ── Data-driven stress threshold ──
    # The threshold must sit ABOVE baseline peak stress but BELOW what pressure scenarios reach.
    #
    # Previous approach (percentile of initial stresses) gave 0.074 — too low.
    # Baseline stress peaks at ~0.08-0.10 by month 12, so the amplifier was firing
    # even during calibration runs, inflating prob_scale to 4.69.
    #
    # Correct approach: project the actual baseline stress peak forward using the
    # calibrated stress physics, then add a safety margin above it.
    #
    # baseline_stress_peak = max_initial_stress + 12 months of net accumulation at baseline
    # (stress_gain_rate * baseline_policy_stress_gain_rate) - recovery_rate per month
    #
    # baseline_policy_stress_gain_rate is read from POLICIES["baseline"] — single source of truth.
    from backend.simulation.policies import POLICIES
    baseline_policy_sgr  = POLICIES["baseline"].stress_gain_rate  # 0.75 currently
    net_gain_per_month   = max(0.0, stress_gain_rate * baseline_policy_sgr - recovery_rate)
    initial_stresses     = np.array([
        min(
            max(0.0, (4.0 - emp.job_satisfaction) / 3.0) * 0.06
            + min(emp.years_at_company / 10.0, 1.0) * 0.035,
            0.40
        )
        for emp in employees
    ])
    baseline_stress_peak = float(np.max(initial_stresses)) + 12 * net_gain_per_month

    # Safety margin: how far above baseline peak before amplifier fires.
    # Derived from gain/recovery ratio — volatile physics need more buffer.
    # Clamped to 1.1–1.5 range so it stays sensible.
    gain_recovery_ratio  = stress_gain_rate / recovery_rate if recovery_rate > 0 else 2.0
    safety_margin        = 1.0 + min(0.5, 0.1 * gain_recovery_ratio)
    raw_threshold        = baseline_stress_peak * safety_margin

    # Hard ceiling: threshold can never exceed avg burnout tolerance (that would
    # make the amplifier meaningless even under extreme pressure).
    avg_burnout          = float(np.mean(burnout_limits))
    stress_threshold     = round(min(raw_threshold, avg_burnout), 4)

    print(f"  >> stress_threshold={stress_threshold:.4f} "
          f"(baseline_peak={baseline_stress_peak:.4f} x margin={safety_margin:.2f}, "
          f"ceiling=avg_burnout={avg_burnout:.4f})")

    std_burnout = float(np.std(burnout_limits))

    # Neighbor stress influence — scaled by loyalty (high-loyalty orgs feel departures less)
    neighbor_stress_weight = round(monthly_natural_rate * (1 - avg_loyalty * 0.5), 4)

    # Fatigue contribution to stress — proportional to how tight burnout limits are
    fatigue_stress_weight = round(neighbor_stress_weight * 0.5, 4)

    # Communication quality cap
    comm_quality_cap = round(max(3.0, min(8.0, 1.0 / monthly_natural_rate * 0.1)), 4)
    comm_quality_benefit = round(monthly_natural_rate * 0.1, 4)

    # Fatigue rates
    fatigue_gain_rate    = round(monthly_natural_rate * 2.0, 4)
    fatigue_recovery_rate = round(fatigue_gain_rate * (avg_work_life_balance / 4.0) * 0.4, 4)

    # Stress threshold for fatigue accumulation
    fatigue_stress_trigger = round(avg_burnout * 0.85, 4)

    # Motivation recovery
    motivation_recovery_rate = round((avg_job_satisfaction / 4.0) * monthly_natural_rate * 0.8, 4)

    # WLB decay mechanics
    # Buffer derived from stress_threshold — now that threshold is ~0.15,
    # buffer ~0.07 means WLB only degrades when stress is noticeably elevated.
    wlb_stress_buffer = round(stress_threshold * 0.45, 4)
    wlb_stress_sensitivity = round(stress_amplification ** 0.5 * 0.5, 4)
    wlb_drop_rate = round(monthly_natural_rate * stress_amplification ** 0.5 * 1.5, 4)
    wlb_recovery_rate = round(wlb_drop_rate * (avg_work_life_balance / 4.0) * 0.6, 4)

    # Burnout productivity penalty
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

    print("+++ Initial calibration saved.")
    print("=== Running empirical calibration...")

    # Empirical calibration: run actual full simulations to find the prob_scale
    # that makes the REAL behavioral engine land on the historical attrition rate.
    #
    # CRITICAL: calibration runs use stress_amplification_override=0.0 so that
    # prob_scale is fitted against pure model probability only. The amplifier is
    # a separate behavioral layer for non-baseline scenarios — mixing it into
    # calibration inflates prob_scale (was 4.69) making pressure scenarios explode.
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
        stress_amplification_override=0.0 ensures prob_scale is calibrated
        independently of the amplifier — they are separate mechanisms.
        """
        agents_copy = copy.deepcopy(calib_agents_base)
        G_copy      = build_org_graph(agents_copy)
        result      = run_simulation(
            calib_config, agents=agents_copy, G=G_copy,
            policy_name="calibration_run",
            seed=seed,
            prob_scale_override=ps,
            stress_amplification_override=0.0,  # decouple amplifier from calibration
        )
        return result["summary"].get("period_attrition_pct", 0.0) / 100.0

    def _stable_rate(ps, seeds=(42, 99)):
        """Average rate across multiple seeds for noise-resistant measurement."""
        rates = [_run_full_sim_rate(ps, seed=s) for s in seeds]
        return float(np.mean(rates))

    # ── Warm-up pass ──────────────────────────────────────────────────────────
    warmup_rate = _stable_rate(prob_scale)
    gap = warmup_rate - annual_attrition_rate
    print(f"  [Warm-up] mini-sim scale={prob_scale:.4f} -> real rate={warmup_rate:.4f}  "
          f"target={annual_attrition_rate:.4f}  gap={gap:+.4f}")

    # ── Binary search (up to 8 passes) ────────────────────────────────────────
    CONVERGENCE_TOL = 0.005
    MAX_PASSES      = 8
    emp_lo, emp_hi  = 0.05, 10.0
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

    # Clear ALL engine caches so the very next simulation uses fresh values
    clear_calibration_cache()
    from backend.simulation.time_engine import clear_engine_calibration_cache
    clear_engine_calibration_cache()
    from backend.simulation.agent import clear_quit_model_cache
    clear_quit_model_cache()

    return calibration




if __name__ == "__main__":
    calibrate()
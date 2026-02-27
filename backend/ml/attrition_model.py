# backend/ml/attrition_model.py

import pandas as pd
import numpy as np
import joblib
import os
from sqlmodel import Session, select
from xgboost import XGBClassifier
from imblearn.over_sampling import SMOTE
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.metrics import classification_report, accuracy_score, roc_auc_score, f1_score

from backend.database import engine
from backend.models import Employee

# ── Base features — always present ──
BASE_FEATURES = [
    "job_satisfaction",
    "work_life_balance",
    "environment_satisfaction",
    "job_involvement",
    "monthly_income",
    "years_at_company",
    "total_working_years",
    "num_companies_worked",
    "job_level",
    "years_since_last_promotion",
    "years_with_curr_manager",
    "performance_rating",
    "stock_option_level",
    "age",
    "distance_from_home",
    "percent_salary_hike",
    "years_in_current_role",
    # Engineered
    "stagnation_score",
    "satisfaction_composite",
    "career_velocity",
    "loyalty_index",
    "is_single",
]

# ── Optional features — used only if present and non-zero variance ──
OPTIONAL_FEATURES = [
    "overtime",                   # strong predictor — IBM research shows 30%+ attrition for overtime workers
    "business_travel",            # frequent travelers quit ~2x more
    # New dataset columns — used if present and have signal
    "leadership_opportunities",   # encoded 0/1 — lack of growth = attrition signal
    "innovation_opportunities",   # encoded 0/1
    "company_reputation",         # encoded 0/1
    "employee_recognition",       # encoded 0/1
]

TARGET = "attrition"

# Global — set after training so agent.py and calibration.py use same features
FEATURES = BASE_FEATURES.copy()


def load_data_from_db():
    with Session(engine) as session:
        employees = session.exec(select(Employee)).all()
    df = pd.DataFrame([e.model_dump() for e in employees])
    return df


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Create stronger signals from existing columns."""
    df['stagnation_score']       = df['years_since_last_promotion'] / (df['years_at_company'] + 1)
    df['satisfaction_composite'] = (
        df['job_satisfaction'] + df['work_life_balance'] + df['environment_satisfaction']
    ) / 3
    df['career_velocity']  = df['job_level'] / (df['total_working_years'] + 1)
    df['loyalty_index']    = df['years_at_company'] / (df['total_working_years'] + 1)

    # Marital status — single employees quit more
    if 'marital_status' in df.columns:
        df['is_single'] = (df['marital_status'].str.lower() == 'single').astype(int)
    else:
        df['is_single'] = 0

    return df


def get_active_features(df: pd.DataFrame) -> list[str]:
    """
    Determine which features to use based on what's actually in the data.
    - BASE_FEATURES with zero variance (e.g. all-default columns) are dropped.
    - OPTIONAL_FEATURES are added only if present and have real signal.
    """
    features = []

    # Filter base features — drop any that are flat (zero variance)
    dropped_base = []
    for feat in BASE_FEATURES:
        if feat not in df.columns:
            continue
        if df[feat].std() > 0:
            features.append(feat)
        else:
            dropped_base.append(feat)

    if dropped_base:
        print(f"  ↳ Dropped {len(dropped_base)} zero-variance base features: {dropped_base}")

    for opt in OPTIONAL_FEATURES:
        if opt in df.columns:
            # Only use if it has real variance — not all zeros (default fill)
            if df[opt].std() > 0:
                features.append(opt)
                print(f"  ↳ Optional feature '{opt}' found with signal — added to model")
            else:
                print(f"  ↳ Optional feature '{opt}' found but all zeros — skipped")
        else:
            print(f"  ↳ Optional feature '{opt}' not in dataset — skipped")

    return features



def tune_threshold(model, X_val, y_val) -> float:
    probs = model.predict_proba(X_val)[:, 1]
    best_threshold = 0.5
    best_f1 = 0

    for t in np.arange(0.25, 0.70, 0.01):
        preds = (probs > t).astype(int)
        f1 = f1_score(y_val, preds, zero_division=0)
        if f1 > best_f1:
            best_f1 = f1
            best_threshold = round(t, 2)

    print(f"  ↳ Optimal threshold: {best_threshold} (F1: {best_f1:.3f})")
    return best_threshold


def train_attrition_model():
    global FEATURES

    print("📊 Loading data from database...")
    df = load_data_from_db()
    df = df.drop(columns=['employee_id', 'simulation_id'], errors='ignore')
    df = df.drop_duplicates()

    df[TARGET] = df[TARGET].map({"Yes": 1, "No": 0})
    df = df.dropna(subset=[TARGET])

    n_samples = len(df)
    print(f"  ↳ {n_samples} employees loaded")

    df = engineer_features(df)

    # Determine which features to use based on this dataset
    FEATURES = get_active_features(df)
    active_base     = [f for f in FEATURES if f in BASE_FEATURES]
    active_optional = [f for f in FEATURES if f in OPTIONAL_FEATURES]
    dropped_base    = [f for f in BASE_FEATURES if f not in FEATURES]
    print(f"  ↳ Using {len(FEATURES)} features "
          f"({len(active_base)} base + {len(active_optional)} optional"
          + (f", dropped {len(dropped_base)}: {dropped_base}" if dropped_base else "") + ")")

    X = df[FEATURES]
    y = df[TARGET]

    if n_samples < 500:
        max_depth = 3
    elif n_samples < 2000:
        max_depth = 4
    else:
        max_depth = 5

    print(f"  ↳ Dataset size: {n_samples} → max_depth: {max_depth}")

    # 3-way split
    X_trainval, X_test, y_trainval, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    X_train, X_val, y_train, y_val = train_test_split(
        X_trainval, y_trainval, test_size=0.25, random_state=42, stratify=y_trainval
    )
    print(f"  ↳ Split: Train={len(X_train)} | Val={len(X_val)} | Test={len(X_test)}")

    negative = (y_train == 0).sum()
    positive = (y_train == 1).sum()
    imbalance_ratio = round(negative / positive, 1)

    # Quick CV to decide imbalance strategy
    quick_model = XGBClassifier(
        n_estimators=50, max_depth=max_depth, learning_rate=0.05,
        scale_pos_weight=imbalance_ratio, random_state=42,
        eval_metric="logloss", verbosity=0,
    )
    quick_cv = cross_val_score(quick_model, X_train, y_train, cv=3, scoring='roc_auc')
    signal_strength = quick_cv.mean()

    if signal_strength >= 0.70:
        sm = SMOTE(random_state=42)
        X_train_final, y_train_final = sm.fit_resample(X_train, y_train)
        strategy = "SMOTE"
        print(f"  ↳ Before SMOTE: Stays={negative}, Quits={positive}")
        print(f"  ↳ After SMOTE:  Stays={(y_train_final==0).sum()}, Quits={(y_train_final==1).sum()}")
    else:
        X_train_final, y_train_final = X_train, y_train
        strategy = f"scale_pos_weight={imbalance_ratio}"
        print(f"  ↳ Weak signal (CV AUC {signal_strength:.2f}) — using {strategy} instead of SMOTE")

    # XGBoost with class weighting instead of SMOTE
    model = XGBClassifier(
        n_estimators=200,
        max_depth=max_depth,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=10,
        reg_alpha=1.0,
        reg_lambda=2.0,
        scale_pos_weight=1 if strategy == "SMOTE" else imbalance_ratio,
        random_state=42,
        eval_metric="logloss",
        early_stopping_rounds=20,
        verbosity=0,
    )
    model.fit(X_train_final, y_train_final, eval_set=[(X_val, y_val)], verbose=False)
    print(f"  ↳ Best iteration: {model.best_iteration} / 200")

    print("🔧 Tuning decision threshold on validation set...")
    best_threshold = tune_threshold(model, X_val, y_val)

    test_probs    = model.predict_proba(X_test)[:, 1]
    y_pred_test   = (test_probs > best_threshold).astype(int)
    train_probs   = model.predict_proba(X_train)[:, 1]
    y_pred_train  = (train_probs > best_threshold).astype(int)

    train_accuracy = accuracy_score(y_train, y_pred_train)
    test_accuracy  = accuracy_score(y_test, y_pred_test)
    auc            = roc_auc_score(y_test, test_probs)

    print("\n📈 Test Performance (held-out, never seen during training or tuning):")
    print(classification_report(y_test, y_pred_test, target_names=["Stays", "Quits"]))
    print(f"📈 AUC-ROC: {auc:.4f}")

    print(f"\n🔍 Training Performance (pre-{strategy} train set):")
    print(classification_report(y_train, y_pred_train, target_names=["Stays", "Quits"]))

    print(f"\n📊 Accuracy Summary:")
    print(f"  Training Accuracy : {train_accuracy*100:.2f}%")
    print(f"  Test Accuracy     : {test_accuracy*100:.2f}%")
    print(f"  Overfitting Gap   : {(train_accuracy - test_accuracy)*100:.2f}%")
    print(f"  AUC-ROC           : {auc:.4f}")

    # Cross-validation
    print("\n🔬 Cross-Validation Diagnostic (5-fold on full data):")
    cv_model = XGBClassifier(
        n_estimators=model.best_iteration,
        max_depth=max_depth,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=10,
        reg_alpha=1.0,
        reg_lambda=2.0,
        random_state=42,
        eval_metric="logloss",
        verbosity=0,
    )
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_scores = cross_val_score(cv_model, X, y, cv=cv, scoring='roc_auc')
    print(f"  AUC per fold: {[round(s, 4) for s in cv_scores]}")
    print(f"  Mean AUC:     {cv_scores.mean():.4f} ± {cv_scores.std():.4f}")

    if cv_scores.mean() < 0.65:
        print("  ⚠️  WARNING: Low AUC — features may lack predictive signal for this dataset.")
    if cv_scores.std() > 0.05:
        print("  ⚠️  WARNING: High variance across folds — model reliability is unstable.")

    cv_mean = float(cv_scores.mean())
    quality_report = {
        "auc_roc":             round(float(auc), 4),
        "cv_auc_mean":         round(cv_mean, 4),
        "cv_auc_std":          round(float(cv_scores.std()), 4),
        "test_accuracy":       round(float(test_accuracy), 4),
        "train_accuracy":      round(float(train_accuracy), 4),
        "features_used":       len(FEATURES),
        "optional_features":   [f for f in OPTIONAL_FEATURES if f in FEATURES],
        "signal_strength":     (
            "strong"   if cv_mean >= 0.80 else
            "moderate" if cv_mean >= 0.65 else
            "weak"
        ),
        "simulation_reliable": bool(cv_mean >= 0.65),
        "recommendation": (
            "Simulation results are reliable."
            if cv_mean >= 0.80 else
            "Simulation shows directional trends. Treat exact numbers with caution."
            if cv_mean >= 0.65 else
            "Signal too weak — simulation results are unreliable. "
            "Consider enriching your dataset with exit interview data, "
            "engagement scores, or compensation benchmarks."
        ),
    }

    os.makedirs("backend/ml/exports", exist_ok=True)
    joblib.dump(
        {"model": model, "threshold": best_threshold, "features": FEATURES},
        "backend/ml/exports/quit_probability.pkl"
    )
    print("✅ Model saved to backend/ml/exports/quit_probability.pkl")
    return quality_report


if __name__ == "__main__":
    train_attrition_model()
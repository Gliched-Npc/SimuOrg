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

FEATURES = [
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
    # Engineered features
    "stagnation_score",
    "satisfaction_composite",
    "career_velocity",
    "loyalty_index",
    "is_single",
]

TARGET = "attrition"


def load_data_from_db():
    with Session(engine) as session:
        employees = session.exec(select(Employee)).all()
    df = pd.DataFrame([e.model_dump() for e in employees])
    return df


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Create stronger signals from existing columns."""

    # Stagnation — stuck with no growth
    df['stagnation_score'] = df['years_since_last_promotion'] / (df['years_at_company'] + 1)

    # Satisfaction composite — average of all satisfaction scores
    df['satisfaction_composite'] = (
        df['job_satisfaction'] +
        df['work_life_balance'] +
        df['environment_satisfaction']
    ) / 3

    # Career velocity — how fast they're growing relative to experience
    df['career_velocity'] = df['job_level'] / (df['total_working_years'] + 1)

    # Loyalty index — tenure relative to total experience
    df['loyalty_index'] = df['years_at_company'] / (df['total_working_years'] + 1)

    # Marital status encoding — single employees quit more
    if 'marital_status' in df.columns:
        df['is_single'] = (df['marital_status'].str.lower() == 'single').astype(int)
    else:
        df['is_single'] = 0

    return df


def tune_threshold(model, X_val, y_val) -> float:
    """Find optimal threshold that maximizes F1 for quit class."""
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
    print("📊 Loading data from database...")
    df = load_data_from_db()
    # DROP DUPLICATES to stop data leakage!
    df = df.drop(columns=['employee_id', 'simulation_id'], errors='ignore')
    df = df.drop_duplicates()

    # Convert target to binary
    df[TARGET] = df[TARGET].map({"Yes": 1, "No": 0})
    df = df.dropna(subset=[TARGET])

    n_samples = len(df)
    print(f"  ↳ {n_samples} employees loaded")

    # Engineer features
    df = engineer_features(df)

    X = df[FEATURES]
    y = df[TARGET]

    # Dynamic max_depth — capped at 5 to prevent memorization
    if n_samples < 500:
        max_depth = 3
    elif n_samples < 2000:
        max_depth = 4
    else:
        max_depth = 5

    print(f"  ↳ Dataset size: {n_samples} → max_depth: {max_depth}")

    # ── Step 1: 3-way split (train 60% / val 20% / test 20%) ──
    X_trainval, X_test, y_trainval, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    X_train, X_val, y_train, y_val = train_test_split(
        X_trainval, y_trainval, test_size=0.25, random_state=42, stratify=y_trainval
    )
    # Result: 60% train, 20% val, 20% test

    print(f"  ↳ Split: Train={len(X_train)} | Val={len(X_val)} | Test={len(X_test)}")

    # ── Step 2: SMOTE on training set only ──
    negative = (y_train == 0).sum()
    positive = (y_train == 1).sum()
    print(f"  ↳ Before SMOTE: Stays={negative}, Quits={positive}")

    sm = SMOTE(random_state=42)
    X_train_sm, y_train_sm = sm.fit_resample(X_train, y_train)
    print(f"  ↳ After SMOTE:  Stays={(y_train_sm==0).sum()}, Quits={(y_train_sm==1).sum()}")

    # ── Step 3: XGBoost with regularization ──
    model = XGBClassifier(
        n_estimators=200,
        max_depth=max_depth,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=10,
        reg_alpha=1.0,        # L1 regularization
        reg_lambda=2.0,       # L2 regularization
        random_state=42,
        eval_metric="logloss",
        early_stopping_rounds=20,
        verbosity=0,
    )
    model.fit(
        X_train_sm, y_train_sm,
        eval_set=[(X_val, y_val)],
        verbose=False,
    )
    print(f"  ↳ Best iteration: {model.best_iteration} / 200")

    # ── Step 4: Tune threshold on VALIDATION set (not test!) ──
    print("🔧 Tuning decision threshold on validation set...")
    best_threshold = tune_threshold(model, X_val, y_val)

    # ── Step 5: Evaluate on held-out TEST set ──
    test_probs = model.predict_proba(X_test)[:, 1]
    y_pred_test = (test_probs > best_threshold).astype(int)

    # Training eval on real (pre-SMOTE) training data
    train_probs = model.predict_proba(X_train)[:, 1]
    y_pred_train = (train_probs > best_threshold).astype(int)

    train_accuracy = accuracy_score(y_train, y_pred_train)
    test_accuracy  = accuracy_score(y_test, y_pred_test)
    auc            = roc_auc_score(y_test, test_probs)

    print("\n📈 Test Performance (held-out, never seen during training or tuning):")
    print(classification_report(y_test, y_pred_test, target_names=["Stays", "Quits"]))
    print(f"📈 AUC-ROC: {auc:.4f}")

    print("\n🔍 Training Performance (pre-SMOTE train set):")
    print(classification_report(y_train, y_pred_train, target_names=["Stays", "Quits"]))

    print(f"\n📊 Accuracy Summary:")
    print(f"  Training Accuracy : {train_accuracy*100:.2f}%")
    print(f"  Test Accuracy     : {test_accuracy*100:.2f}%")
    print(f"  Overfitting Gap   : {(train_accuracy - test_accuracy)*100:.2f}%")
    print(f"  AUC-ROC           : {auc:.4f}")

    # ── Step 6: Cross-validation diagnostic ──
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

    # ── Step 7: Quality report ──
    cv_mean = float(cv_scores.mean())
    quality_report = {
        "auc_roc":         round(float(auc), 4),
        "cv_auc_mean":     round(cv_mean, 4),
        "cv_auc_std":      round(float(cv_scores.std()), 4),
        "test_accuracy":   round(float(test_accuracy), 4),
        "train_accuracy":  round(float(train_accuracy), 4),
        "signal_strength": (
            "strong"   if cv_mean >= 0.80 else
            "moderate" if cv_mean >= 0.65 else
            "weak"
        ),
        "simulation_reliable": cv_mean >= 0.65,
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

    # ── Step 8: Save ──
    os.makedirs("backend/ml/exports", exist_ok=True)
    joblib.dump(
        {"model": model, "threshold": best_threshold, "features": FEATURES},
        "backend/ml/exports/quit_probability.pkl"
    )
    print("✅ Model saved to backend/ml/exports/quit_probability.pkl")

    return quality_report


if __name__ == "__main__":
    train_attrition_model()
# backend/ml/attrition_model.py

import pandas as pd
import numpy as np
import joblib
import os
from sqlmodel import Session, select
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.metrics import classification_report, accuracy_score, roc_auc_score, f1_score, precision_score, recall_score
from sklearn.preprocessing import LabelEncoder

from backend.database import engine
from backend.models import Employee

# ── Features ──
# Driven strictly by the 14-column mandatory schema + engineered features.
BASE_FEATURES = [
    "job_satisfaction",
    "work_life_balance",
    "environment_satisfaction",
    "monthly_income",
    "years_at_company",
    "total_working_years",
    "num_companies_worked",
    "job_level",
    "years_since_last_promotion",
    "years_with_curr_manager",
    "age",
    # Engineered from mandatory columns — always available
    "stagnation_score",
    "satisfaction_composite",
    "career_velocity",
    "loyalty_index",
    "income_vs_level",    # monthly_income / job_level — flags underpaid employees
    "tenure_stability",   # years_with_curr_manager / years_at_company — manager instability
]

# Bonus features — used only if the uploaded dataset contains them
# Categorical ones are label-encoded in engineer_features before use
OPTIONAL_FEATURES = [
    "overtime",
    "department_encoded",
    "job_role_encoded",
]

TARGET = "attrition"

# Global — set after training so agent.py and calibration.py use same features
FEATURES = BASE_FEATURES.copy()

# Fitted LabelEncoders saved after training — keyed by encoded column name
# Used at inference time to guarantee identical integer codes as training
LABEL_ENCODERS: dict = {}


def load_data_from_db():
    with Session(engine) as session:
        employees = session.exec(select(Employee)).all()
    df = pd.DataFrame([e.model_dump() for e in employees])
    return df


def engineer_features(df: pd.DataFrame, encoders: dict = None) -> pd.DataFrame:
    """Create stronger signals from existing columns.
    encoders: pre-fitted LabelEncoders for inference (None = fit at training time).
    """
    df['stagnation_score']       = df['years_since_last_promotion'] / (df['years_at_company'] + 1)
    df['satisfaction_composite'] = (
        df['job_satisfaction'] + df['work_life_balance'] + df['environment_satisfaction']
    ) / 3
    df['career_velocity']  = df['job_level'] / (df['total_working_years'] + 1)
    df['loyalty_index']    = df['years_at_company'] / (df['total_working_years'] + 1)

    # Engineered: flag underpaid employees (lower income relative to job level)
    df['income_vs_level']  = df['monthly_income'] / (df['job_level'] * 1000 + 1)
    # Engineered: manager tenure relative to company tenure (instability indicator)
    df['tenure_stability'] = df['years_with_curr_manager'] / (df['years_at_company'] + 1)

    # Label-encode categorical optional features.
    # Training (encoders=None): fit + register in LABEL_ENCODERS global.
    # Inference (encoders provided): apply saved mapping so codes are consistent.
    cat_cols = [
        ("department", "department_encoded"),
        ("job_role",   "job_role_encoded"),
    ]
    for col, enc_col in cat_cols:
        if col not in df.columns or df[col].isna().all():
            continue
        if encoders and enc_col in encoders:
            le = encoders[enc_col]
            mapping = {cls: i for i, cls in enumerate(le.classes_)}
            df[enc_col] = df[col].fillna("Unknown").astype(str).map(mapping).fillna(-1).astype(int)
        else:
            le = LabelEncoder()
            df[enc_col] = le.fit_transform(df[col].fillna("Unknown").astype(str))
            LABEL_ENCODERS[enc_col] = le

    return df


def get_active_features(df: pd.DataFrame) -> list[str]:
    """
    Determine which features to use.
    BASE_FEATURES are guaranteed by schema.py.
    """
    features = BASE_FEATURES.copy()

    for opt in OPTIONAL_FEATURES:
        if opt in df.columns and df[opt].std() > 0:
            features.append(opt)
            print(f"  ↳ Bonus feature '{opt}' found with signal — added to model")

    return features



# Minimum precision floor for the recall-optimised threshold tuner.
# At 0.30: for every 10 flagged employees, at least 3 are real quitters.
MIN_PRECISION_FLOOR = 0.30


def tune_threshold(model, X_val, y_val) -> float:
    """
    CEO-optimised: maximise Quits recall while precision >= MIN_PRECISION_FLOOR.
    Falls back to best-F1 threshold if the precision floor can never be satisfied.
    """
    probs = model.predict_proba(X_val)[:, 1]
    best_threshold     = 0.5
    best_recall        = 0.0
    fallback_threshold = 0.5
    fallback_f1        = 0.0

    for t in np.arange(0.10, 0.75, 0.01):
        preds = (probs > t).astype(int)
        if preds.sum() == 0:
            continue
        prec = precision_score(y_val, preds, zero_division=0)
        rec  = recall_score(y_val, preds, zero_division=0)
        f1   = f1_score(y_val, preds, zero_division=0)

        if f1 > fallback_f1:
            fallback_f1        = f1
            fallback_threshold = round(t, 2)

        if prec >= MIN_PRECISION_FLOOR and rec > best_recall:
            best_recall    = rec
            best_threshold = round(t, 2)

    if best_recall == 0.0:
        best_threshold = fallback_threshold
        print(f"  -> Precision floor not met - using best-F1 threshold: {best_threshold} (F1: {fallback_f1:.3f})")
    else:
        val_preds = (probs > best_threshold).astype(int)
        val_prec  = precision_score(y_val, val_preds, zero_division=0)
        print(f"  -> Recall-optimised threshold: {best_threshold} (Recall: {best_recall:.3f}, Precision: {val_prec:.3f})")

    return best_threshold


def train_attrition_model():
    global FEATURES

    print("=== Loading data from database...")
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

    # Basic sanity check: need both classes for a meaningful classifier.
    class_counts = y.value_counts()
    if len(class_counts) < 2:
        raise ValueError(
            f"Training data contains only a single attrition class: {class_counts.to_dict()}. "
            "At least some 'Yes' and 'No' rows are required to train the quit probability model."
        )

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

    negative = int((y_train == 0).sum())
    positive = int((y_train == 1).sum())
    if positive == 0 or negative == 0:
        raise ValueError(
            f"Stratified train split produced a single-class set: "
            f"negatives={negative}, positives={positive}. "
            "This usually happens on very small or highly imbalanced datasets. "
            "Please upload more data or rebalance labels before training."
        )
    imbalance_ratio = round(negative / positive, 1)

    # Quick CV to decide imbalance strategy
    capped_spw_quick = min(imbalance_ratio, 10.0)
    quick_model = XGBClassifier(
        n_estimators=50,
        max_depth=max_depth,
        learning_rate=0.05,
        scale_pos_weight=capped_spw_quick,
        random_state=42,
        eval_metric="logloss", verbosity=0,
    )
    # For very small datasets, ensure class counts support the chosen number of folds.
    min_class_count = min(negative, positive)
    quick_cv_folds = max(2, min(3, min_class_count))  # 2–3 folds
    quick_cv = cross_val_score(quick_model, X_train, y_train, cv=quick_cv_folds, scoring='roc_auc')
    signal_strength = quick_cv.mean()

    # -- Imbalance strategy: cost-sensitive learning --
    # scale_pos_weight is derived from the actual class ratio in THIS dataset.
    # It changes per uploaded dataset (data-driven, not hardcoded).
    # More stable than SMOTE: no synthetic data, no artificial overfitting.
    X_train_final, y_train_final = X_train, y_train
    spw_main = round(min(imbalance_ratio ** 0.5, 10.0), 2)
    strategy = f"cost-sensitive (scale_pos_weight={spw_main})"
    print(f"  -> Imbalance ratio: {imbalance_ratio} Stays per Quitter | {strategy}")

    # XGBoost with class weighting instead of SMOTE
    model = XGBClassifier(
        n_estimators=200,
        max_depth=max_depth,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=5,
        reg_alpha=1.0,
        reg_lambda=2.0,
        # sqrt(imbalance_ratio): recall-biased but keeps probabilities calibrated.
        # Full imbalance_ratio pushes probs to 0.9+ for quitters → simulation explodes.
        # Square root is standard practice for production simulation-based products.
        scale_pos_weight=spw_main,
        random_state=42,
        eval_metric="logloss",
        early_stopping_rounds=30,
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

    print("\n=== Test Performance (held-out, never seen during training or tuning):")
    print(classification_report(y_test, y_pred_test, target_names=["Stays", "Quits"]))
    print(f"=== AUC-ROC: {auc:.4f}")

    print(f"\n🔍 Training Performance (pre-{strategy} train set):")
    print(classification_report(y_train, y_pred_train, target_names=["Stays", "Quits"]))

    print(f"\n=== Accuracy Summary:")
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
        min_child_weight=5,       # kept in sync with main model
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
        print("  ---  WARNING: Low AUC - features may lack predictive signal for this dataset.")
    if cv_scores.std() > 0.05:
        print("  ---  WARNING: High variance across folds - model reliability is unstable.")

    cv_mean = float(cv_scores.mean())
    quality_report = {
        "auc_roc":             round(float(auc), 4),
        "cv_auc_mean":         round(cv_mean, 4),
        "cv_auc_std":          round(float(cv_scores.std()), 4),
        "test_accuracy":       round(float(test_accuracy), 4),
        "train_accuracy":      round(float(train_accuracy), 4),
        "features_used":       len(FEATURES),
        "bonus_features":      [f for f in OPTIONAL_FEATURES if f in FEATURES],
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
        {
            "model":          model,
            "threshold":      best_threshold,
            "features":       FEATURES,
            "label_encoders": LABEL_ENCODERS,  # saved for consistent inference
        },
        "backend/ml/exports/quit_probability.pkl"
    )
    print("+++ Model saved to backend/ml/exports/quit_probability.pkl")
    return quality_report


if __name__ == "__main__":
    train_attrition_model()
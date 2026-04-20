# backend/quality_checker.py
#
# Pre-cleaning data quality report with severity tiers and actionable suggestions.
# Returns structured issues that the frontend can display before the user commits to ingest.

import pandas as pd


def check_data_quality(
    df: pd.DataFrame,
    duplicates_removed: int = 0,
    junk_removed: int = 0,
    null_rates: dict = None,
    cleaning_audit: list[str] = None,
) -> dict:
    """
    Analyse a normalized + cleaned DataFrame and return a list of issues.

    Each issue is a dict:
        severity  : "error" | "warning" | "info"
        code      : short machine-readable key (e.g. "high_attrition_rate")
        message   : plain-English description of the consequence
        suggestion: actionable fix for the client (Fix vs Proceed)
    """
    issues: list[dict] = []
    total = len(df)
    trust_score = 100

    if total == 0:
        issues.append(
            {
                "severity": "error",
                "code": "empty_dataset",
                "message": "CONSEQUENCE: The dataset is empty after cleaning. The Machine Learning model has zero data to train on.",
                "suggestion": "SOLUTION: You must fix the dataset and re-upload. Ensure the file contains at least 50 valid employee rows with no severe formatting corruption.",
            }
        )
        return issues

    # ── Identical Clones (Contamination) ──
    df_no_id = df.drop(columns=["EmployeeID", "EmployeeNumber", "ManagerID"], errors="ignore")
    clone_count = int(df_no_id.duplicated().sum())
    if clone_count > 0:
        trust_score -= 15 if clone_count > total * 0.1 else 5
        severity = "error" if clone_count > total * 0.3 else "warning"
        issues.append(
            {
                "severity": severity,
                "code": "identical_clones_detected",
                "message": f"CONSEQUENCE: {clone_count} rows are mathematically identical clones of other employees across all behavioral columns. This means the dataset was likely copy-pasted or merged twice. The AI expects unique humans—it will 'hallucinate' artificially high accuracy by memorizing these clone instances instead of learning real behavioral patterns.",
                "suggestion": "SOLUTION: [OPTION 1] Cancel upload and fix your HR export to stop duplicating rows. [OPTION 2] Proceed anyway, but be aware the AI metrics will be distorted and hallucinated.",
            }
        )

    # ── Attrition rate ──
    attrition_count = (df["Attrition"] == "Yes").sum()
    attrition_rate = attrition_count / total
    if attrition_rate > 0.40:
        issues.append(
            {
                "severity": "error",
                "code": "extreme_attrition_rate",
                "message": f"CONSEQUENCE: Attrition rate is {attrition_rate*100:.1f}%. The ML model will assume firing/quitting is the normal operational state, completely invalidating the simulation physics.",
                "suggestion": "SOLUTION: Fix the dataset by verifying your Attrition column values (a common mistake is encoding all active employees as 'Yes'). You cannot proceed with this upload.",
            }
        )
    elif attrition_rate > 0.25:
        issues.append(
            {
                "severity": "warning",
                "code": "high_attrition_rate",
                "message": f"CONSEQUENCE: Attrition rate is {attrition_rate*100:.1f}% (industry average is 10–20%). If you proceed, the simulation engine's baseline will skew extremely pessimistic.",
                "suggestion": "SOLUTION: [OPTION 1] Fix the data by filtering out older historical terminations before uploading. [OPTION 2] Proceed anyway, but treat the simulation results as a 'worst-case scenario' stress test.",
            }
        )
    elif attrition_rate < 0.03 and total > 100:
        trust_score -= 10
        issues.append(
            {
                "severity": "warning",
                "code": "low_attrition_rate",
                "message": f"CONSEQUENCE: Attrition rate is only {attrition_rate*100:.1f}%. The ML model will not have enough examples of 'Quitters' to learn what causes attrition, resulting in weak predictive signal.",
                "suggestion": "SOLUTION: [OPTION 1] Fix the dataset by extending your historical export window from 1 year to 3 years to capture more exits. [OPTION 2] Proceed anyway, but expect the model metrics to report 'Low Reliability'.",
            }
        )

    # ── Dataset size ──
    if total < 30:
        issues.append(
            {
                "severity": "error",
                "code": "dataset_too_small",
                "message": f"CONSEQUENCE: Only {total} employees found. Deep learning and XGBoost models will immediately violently overfit to this tiny sample size.",
                "suggestion": "SOLUTION: You must fix the dataset. Upload a file containing at least 50 employees (ideally 200+) to generate statistically meaningful cross-validation folds.",
            }
        )
    elif total < 100:
        issues.append(
            {
                "severity": "warning",
                "code": "small_dataset",
                "message": f"CONSEQUENCE: Dataset has only {total} employees. The ML model will struggle to generalize, and simulation projections will have high statistical variance.",
                "suggestion": "SOLUTION: [OPTION 1] Fix by uploading more historical data if available in your HRIS. [OPTION 2] Proceed anyway, but treat all simulation headcount projections as directional trends rather than precise numbers.",
            }
        )
    elif total < 2000:
        issues.append(
            {
                "severity": "warning",
                "code": "moderate_dataset",
                "message": f'CONSEQUENCE: Dataset has {total} employees. Advanced AI models require huge datasets to perfect patterns. It is highly likely the Model Quality Report will show an "Overfitting Gap" (Train Accuracy much higher than Test Accuracy) and lower overall predictive confidence.',
                "suggestion": "SOLUTION: [OPTION 1] Proceed normally; the engine will attempt to handle this by shrinking complexity automatically. [OPTION 2] Upload a larger dataset (3000+ rows) to close the gap.",
            }
        )

    # ── Duplicates ──
    duplication_rate = (
        duplicates_removed / (total + duplicates_removed) if (total + duplicates_removed) > 0 else 0
    )
    if duplication_rate > 0.20:
        issues.append(
            {
                "severity": "warning",
                "code": "high_duplication",
                "message": f"CONSEQUENCE: {duplicates_removed} duplicate IDs were found ({duplication_rate*100:.0f}% of raw data). Excessive duplicates usually mean your SQL export JOINed incorrectly.",
                "suggestion": "SOLUTION: [OPTION 1] Fix your HRIS export script to prevent cross-joining data. [OPTION 2] Proceed anyway; we have automatically purged the duplicates, but double-check that your total headcount is accurate.",
            }
        )
    elif duplicates_removed > 0:
        issues.append(
            {
                "severity": "info",
                "code": "duplicates_removed",
                "message": f"CONSEQUENCE: {duplicates_removed} minor duplicate EmployeeIDs were detected and dropped to prevent ML data leakage.",
                "suggestion": "SOLUTION: Proceed normally. No action needed.",
            }
        )

    # ── Junk rows ──
    if junk_removed > 0:
        issues.append(
            {
                "severity": "warning",
                "code": "junk_rows_purged",
                "message": f"CONSEQUENCE: {junk_removed} junk rows were detected (employees missing more than 40% of standard HR data). These rows were purged because they provide no learnable pattern for the AI.",
                "suggestion": "SOLUTION: [OPTION 1] Fix your HRIS export to ensure a full column-set is exported for all active employees. [OPTION 2] Proceed anyway; we have cleaned the 'phantom' data to protect model accuracy.",
            }
        )

    # ── Job level validity ──
    invalid_levels = ((df["JobLevel"] < 1) | (df["JobLevel"] > 5)).sum()
    if invalid_levels > total * 0.10:
        issues.append(
            {
                "severity": "warning",
                "code": "invalid_job_levels",
                "message": f"CONSEQUENCE: {invalid_levels} employees had job levels outside the standard 1–5 range. The ML model uses Job Level to calculate career trajectory; invalid levels corrupt this calculation.",
                "suggestion": "SOLUTION: [OPTION 1] Fix the JobLevel column in your CSV to map correctly to a 1 (Entry) to 5 (Executive) scale. [OPTION 2] Proceed anyway; we will Auto-Clip extreme values to 1 or 5, but precision will drop.",
            }
        )

    # ── Negative income ──
    negative_income = (df["MonthlyIncome"] < 0).sum()
    if negative_income > 0:
        issues.append(
            {
                "severity": "warning",
                "code": "negative_income",
                "message": f"CONSEQUENCE: {negative_income} employees had negative monthly income. The ML model interprets salary as a core retention driver; negative numbers will severely distort the compensation importance coefficients.",
                "suggestion": "SOLUTION: [OPTION 1] Fix your HRIS data export to resolve negative salary entry errors. [OPTION 2] Proceed anyway; we will Auto-Clip these to 0, but compensation analysis accuracy will be degraded.",
            }
        )

    # ── Suspicious Rounding (Synthetic Data) ──
    if "MonthlyIncome" in df.columns and total > 500:
        clean_income = df["MonthlyIncome"].dropna()
        if len(clean_income) > 0:
            unique_ratio = len(clean_income.unique()) / len(clean_income)
            divisible_by_100_ratio = (clean_income % 100 == 0).mean()

            if unique_ratio < 0.05 and divisible_by_100_ratio >= 0.80:
                trust_score -= 10
                issues.append(
                    {
                        "severity": "warning",
                        "code": "synthetic_income_rounding",
                        "message": f"CONSEQUENCE: The MonthlyIncome column has an unnaturally low variance ({unique_ratio*100:.1f}% unique values) and {divisible_by_100_ratio*100:.1f}% of them are perfectly rounded multiples of $100. This highly suggests artificial or bucketed data. Real-world financial sensitivity might be inaccurate.",
                        "suggestion": "SOLUTION: [OPTION 1] Ignore if this is a test/demo dataset. [OPTION 2] Upload real, unrounded payroll data for accurate compensation analysis.",
                    }
                )

    # ── Feature Sparsity (Exact Row Counts & Column Priority) ──
    # CRITICAL: Mandatory for core simulation physics + ML signal
    CRITICAL_FEATURES = {
        "MonthlyIncome",
        "JobLevel",
        "YearsAtCompany",
        "TotalWorkingYears",
        "JobSatisfaction",
        "WorkLifeBalance",
        "EnvironmentSatisfaction",
        "Attrition",
        "PerformanceRating",
        "JobInvolvement",
        "YearsWithCurrManager",
    }

    if null_rates:
        for col, null_rate in null_rates.items():
            if null_rate == 0:
                continue

            missing_count = int(null_rate * total)
            is_critical = col in CRITICAL_FEATURES

            # Severity Logic:
            # If data is missing, we must impute it, which is always a warning.
            severity = "warning"
            if is_critical and null_rate > 0.50:
                severity = "error"  # Too much critical data missing

            if severity in ["error", "warning"]:
                tier = "CRITICAL CORE" if is_critical else "BONUS ENRICHMENT"
                if severity == "warning":
                    trust_score -= 8 if is_critical else 3
                else:
                    trust_score -= 2 if is_critical else 1  # Slight penalty for info-level gaps
                issues.append(
                    {
                        "severity": severity,
                        "code": f"sparsity_{col.lower()}",
                        "message": f"CONSEQUENCE: {tier} feature '{col}' is missing {missing_count} rows ({null_rate*100:.1f}%).",
                        "suggestion": f"SOLUTION: [OPTION 1] Fix the {col} column in your source data to restore full accuracy. [OPTION 2] Proceed anyway; we will Auto-Fill these using company medians, but results will be generalized.",
                    }
                )

    # ── Satisfaction columns with no variance ──
    for col in [
        "JobSatisfaction",
        "WorkLifeBalance",
        "EnvironmentSatisfaction",
        "PerformanceRating",
    ]:
        if col in df.columns and df[col].std() < 0.01:
            trust_score -= 10
            issues.append(
                {
                    "severity": "warning",
                    "code": f"no_variance_{col.lower()}",
                    "message": f"CONSEQUENCE: The '{col}' column has near-zero variance (everyone has the exact same score). The ML model will completely ignore this feature because it provides zero mathematical signal.",
                    "suggestion": f"SOLUTION: [OPTION 1] Fix the data. Ensure you aren't uploading 'default' or 'median' values instead of actual employee survey results. [OPTION 2] Proceed anyway, but realize the simulation cannot test policies related to {col}.",
                }
            )

    # ── Pre-Training Mathematical Correlation (Sanity Check) ──
    # Check if ANY numeric features actually correlate with Attrition
    try:
        numeric_cols = df.select_dtypes(include=["number"]).columns
        if len(numeric_cols) > 0 and "Attrition" in df.columns:
            # Map 'Yes'/'No' to numeric for correlation mapping
            temp_y = df["Attrition"].map({"Yes": 1, "No": 0})
            if temp_y.notna().any() and temp_y.std() > 0:
                # Filter out columns with zero variance to avoid divide-by-zero warnings
                valid_cols = [c for c in numeric_cols if df[c].std() > 0]

                locked_columns = set()
                # ── Mechanically Locked Features (Multi-collinearity) ──
                if len(valid_cols) > 1 and total >= 200:
                    corr_matrix = df[valid_cols].corr()
                    locked_pairs = []

                    for i in range(len(corr_matrix.columns)):
                        for j in range(i + 1, len(corr_matrix.columns)):
                            if abs(corr_matrix.iloc[i, j]) > 0.95:
                                col1 = corr_matrix.columns[i]
                                col2 = corr_matrix.columns[j]
                                locked_pairs.append(f"{col1} & {col2}")
                                locked_columns.add(col1)
                                locked_columns.add(col2)

                    if locked_pairs:
                        trust_score -= 5
                        pairs_str = ", ".join(locked_pairs)
                        issues.append(
                            {
                                "severity": "warning",
                                "code": "mechanically_locked_features",
                                "message": f"CONSEQUENCE: We detected pairs of columns mathematically locked together ({pairs_str} have >0.95 correlation). The AI will treat them as redundant duplicated signals.",
                                "suggestion": "SOLUTION: Proceed normally; advanced models naturally ignore redundant columns, though SHAP explainability graphs may split credit between them.",
                            }
                        )

                if valid_cols:
                    corrs = df[valid_cols].apply(lambda x: x.corr(temp_y))
                    max_corr = corrs.abs().max()
                else:
                    max_corr = 0

                # If absolutely no feature has even a 5% correlation with attrition
                if max_corr < 0.05:
                    trust_score -= 20
                    issues.append(
                        {
                            "severity": "warning",
                            "code": "zero_mathematical_signal",
                            "message": "CONSEQUENCE: Our pre-training mathematical scan detects almost zero relationship between your employee features (age, income, satisfaction) and whether they quit. The ML model will struggle to find a flight-risk pattern, and simulation outputs will be highly randomized.",
                            "suggestion": "SOLUTION: [OPTION 1] Fix the dataset by ensuring your data isn't randomized, obfuscated, or synthesized poorly. [OPTION 2] Proceed anyway, but be aware your resulting 'quit_probability' predictions and SHAP graphs will be completely flat and unreliable.",
                        }
                    )
                else:
                    # ── Dynamic Per-Feature Zero Signal ──
                    # Run this only if the global signal is not already considered catastrophic
                    signal_floor = max(0.01, 0.10 * max_corr)

                    zero_signal_cols = []
                    for col in valid_cols:
                        if col in locked_columns:
                            continue  # Exclude columns already flagged for redundancy
                        if abs(corrs[col]) < signal_floor:
                            zero_signal_cols.append(col)

                    if zero_signal_cols:
                        issues.append(
                            {
                                "severity": "info",
                                "code": "specific_feature_zero_signal",
                                "message": f"CONSEQUENCE: The columns {zero_signal_cols} have near-zero mathematical correlation with turnover (less than 10% of the strongest signal). They act as pure noise.",
                                "suggestion": "SOLUTION: No action needed. The model may automatically discard these features during training.",
                            }
                        )
    except Exception:
        pass  # Silently fail the sanity check if Pandas correlation calculation fails

    # ── Missing Gender ──
    if "Gender" not in df.columns:
        issues.append(
            {
                "severity": "warning",
                "code": "no_gender_column",
                "message": "CONSEQUENCE: Gender column not found. The model will not be able to analyze demographic-based flight risks.",
                "suggestion": "SOLUTION: [OPTION 1] Fix by uploading Demographics data if you want Diversity & Inclusion retention insights. [OPTION 2] Proceed normally; 'Unknown' will be used. This is optional and does not affect core model physics.",
            }
        )

    # ── All-clear ──
    if not issues:
        issues.append(
            {
                "severity": "info",
                "code": "all_checks_passed",
                "message": "CONSEQUENCE: All quality checks passed. The dataset structure perfectly matches the engine's requirements.",
                "suggestion": "SOLUTION: Proceed with confidence.",
            }
        )

    # --- Trust Score Adjustments for Global Metrics ---
    if attrition_rate > 0.40:
        trust_score -= 20
    elif attrition_rate > 0.25:
        trust_score -= 10

    if total < 50:
        trust_score -= 20
    elif total < 100:
        trust_score -= 10
    elif total < 2000:
        trust_score -= 5

    if junk_removed > total * 0.1:
        trust_score -= 10
    if duplicates_removed > 0:
        trust_score -= 5

    trust_score = max(10, min(100, trust_score))  # Clamp 10-100

    return {
        "status": "danger"
        if any(i["severity"] == "error" for i in issues)
        else "warning"
        if issues
        else "healthy",
        "trust_score": trust_score,
        "issues": issues,
        "cleaning_audit": cleaning_audit or [],
    }

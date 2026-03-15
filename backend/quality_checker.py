# backend/quality_checker.py
#
# Pre-cleaning data quality report with severity tiers and actionable suggestions.
# Returns structured issues that the frontend can display before the user commits to ingest.

import pandas as pd


def check_data_quality(df: pd.DataFrame, duplicates_removed: int = 0) -> list[dict]:
    """
    Analyse a normalized + cleaned DataFrame and return a list of issues.

    Each issue is a dict:
        severity  : "error" | "warning" | "info"
        code      : short machine-readable key (e.g. "high_attrition_rate")
        message   : plain-English description
        suggestion: actionable fix for the client
    """
    issues: list[dict] = []
    total = len(df)

    if total == 0:
        issues.append({
            "severity": "error",
            "code": "empty_dataset",
            "message": "The dataset is empty after cleaning.",
            "suggestion": "Re-upload a file with at least 50 employee rows.",
        })
        return issues

    # ── Attrition rate ──
    attrition_count = (df["Attrition"] == "Yes").sum()
    attrition_rate = attrition_count / total
    if attrition_rate > 0.40:
        issues.append({
            "severity": "error",
            "code": "extreme_attrition_rate",
            "message": f"Attrition rate is {attrition_rate*100:.1f}% — this is unrealistically high.",
            "suggestion": "Verify your Attrition column values. Common mistake: encoding all employees as 'Yes'.",
        })
    elif attrition_rate > 0.25:
        issues.append({
            "severity": "warning",
            "code": "high_attrition_rate",
            "message": f"Attrition rate is {attrition_rate*100:.1f}% (industry average is 10–20%).",
            "suggestion": "If this rate is real, simulation results may skew pessimistic. Consider filtering to active-only employees.",
        })
    elif attrition_rate < 0.03 and total > 100:
        issues.append({
            "severity": "warning",
            "code": "low_attrition_rate",
            "message": f"Attrition rate is only {attrition_rate*100:.1f}% — the model may lack signal.",
            "suggestion": "Consider augmenting with exit-interview data or a longer historical window.",
        })

    # ── Dataset size ──
    if total < 30:
        issues.append({
            "severity": "error",
            "code": "dataset_too_small",
            "message": f"Only {total} employees — too few to train a reliable model.",
            "suggestion": "Upload at least 50 employees (ideally 200+) for statistically meaningful results.",
        })
    elif total < 100:
        issues.append({
            "severity": "warning",
            "code": "small_dataset",
            "message": f"Dataset has {total} employees. Results will have high variance.",
            "suggestion": "Upload more data if available. Treat simulation numbers as directional, not precise.",
        })

    # ── Duplicates ──
    duplication_rate = duplicates_removed / (total + duplicates_removed) if (total + duplicates_removed) > 0 else 0
    if duplication_rate > 0.20:
        issues.append({
            "severity": "warning",
            "code": "high_duplication",
            "message": f"{duplicates_removed} duplicate employee IDs were removed ({duplication_rate*100:.0f}% of raw data).",
            "suggestion": "Check your data source for repeated exports or merge errors.",
        })
    elif duplicates_removed > 0:
        issues.append({
            "severity": "info",
            "code": "duplicates_removed",
            "message": f"{duplicates_removed} duplicate EmployeeIDs removed automatically.",
            "suggestion": "No action needed — duplicates were safely dropped.",
        })

    # ── Job level validity ──
    invalid_levels = ((df["JobLevel"] < 1) | (df["JobLevel"] > 5)).sum()
    if invalid_levels > total * 0.10:
        issues.append({
            "severity": "warning",
            "code": "invalid_job_levels",
            "message": f"{invalid_levels} employees had job levels outside 1–5 (auto-clipped).",
            "suggestion": "Review the JobLevel column — values outside 1–5 reduce model accuracy.",
        })

    # ── Negative income ──
    negative_income = (df["MonthlyIncome"] < 0).sum()
    if negative_income > 0:
        issues.append({
            "severity": "warning",
            "code": "negative_income",
            "message": f"{negative_income} employees had negative monthly income (set to 0).",
            "suggestion": "Verify income data — negative values usually indicate data entry errors.",
        })

    # ── Satisfaction columns with no variance ──
    for col in ["JobSatisfaction", "WorkLifeBalance", "EnvironmentSatisfaction"]:
        if col in df.columns and df[col].std() < 0.01:
            issues.append({
                "severity": "warning",
                "code": f"no_variance_{col.lower()}",
                "message": f"{col} has near-zero variance — all employees have the same value.",
                "suggestion": f"The model can't learn from {col}. If this is survey data, check that scores were actually collected.",
            })

    # ── Missing Gender ──
    if "Gender" not in df.columns:
        issues.append({
            "severity": "info",
            "code": "no_gender_column",
            "message": "Gender column not found — 'Unknown' will be used for all employees.",
            "suggestion": "This is optional and does not affect simulation accuracy.",
        })

    # ── All-clear ──
    if not issues:
        issues.append({
            "severity": "info",
            "code": "all_checks_passed",
            "message": "All quality checks passed — dataset looks clean.",
            "suggestion": "Proceed with confidence.",
        })

    return issues

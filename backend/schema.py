# backend/schema.py
#
# Handles all incoming dataset normalization:
#   - Column name aliases (different HR systems name things differently)
#   - Attrition value normalization (Yes/No/Left/Stayed/1/0 etc.)
#   - Optional column defaults (fill missing columns with sensible values)
#   - Schema report (tell CEO what was found vs missing)

import pandas as pd

# ── Hard required — upload fails without these ──
# Reduced to exactly 14 strictly required columns based on feature importance.
REQUIRED_COLUMNS = [
    "EmployeeID",
    "ManagerID",
    "Department",
    "JobRole",
    "Age",
    "JobSatisfaction",
    "WorkLifeBalance",
    "EnvironmentSatisfaction",
    "YearsAtCompany",
    "TotalWorkingYears",
    "NumCompaniesWorked",
    "YearsWithCurrManager",
    "YearsSinceLastPromotion",
    "JobLevel",
    "MonthlyIncome",
    "Attrition",
]

# ── Column name aliases ──
# Maps any known variation → our canonical schema name.
COLUMN_ALIASES = {
    # EmployeeID
    "EmployeeNumber":             "EmployeeID",
    "Employee ID":                "EmployeeID",
    "employee_id":                "EmployeeID",
    "EmpID":                      "EmployeeID",

    # Department
    "Dept":                       "Department",

    # Job fields
    "Job Role":                   "JobRole",
    "Job_Role":                   "JobRole",
    "Job Level":                  "JobLevel",
    "Job_Level":                  "JobLevel",

    # Income
    "Monthly Income":             "MonthlyIncome",
    "Monthly_Income":             "MonthlyIncome",
    "Salary":                     "MonthlyIncome",
    "monthly_salary":             "MonthlyIncome",

    # Tenure — 'Years at Company' and 'Company Tenure' both map here
    "Years at Company":           "YearsAtCompany",
    "Years_at_Company":           "YearsAtCompany",
    "Company Tenure":             "CompanyTenure",  
    "Tenure":                     "YearsAtCompany",

    # Total experience
    "Total Working Years":        "TotalWorkingYears",
    "Total_Working_Years":        "TotalWorkingYears",
    "TotalExperience":            "TotalWorkingYears",

    # Satisfaction
    "Work-Life Balance":          "WorkLifeBalance",
    "Work Life Balance":          "WorkLifeBalance",
    "Job Satisfaction":           "JobSatisfaction",
    "Job_Satisfaction":           "JobSatisfaction",
    "Environment Satisfaction":   "EnvironmentSatisfaction",
    "Environment_Satisfaction":   "EnvironmentSatisfaction",

    # Other IBM HR fields
    "Performance Rating":         "PerformanceRating",
    "Job Involvement":            "JobInvolvement",
    "Num Companies Worked":       "NumCompaniesWorked",
    "Number of Companies":        "NumCompaniesWorked",
    "Stock Option Level":         "StockOptionLevel",
    "Years Since Last Promotion": "YearsSinceLastPromotion",
    "Years With Current Manager": "YearsWithCurrManager",
    "Distance from Home":         "DistanceFromHome",
    "Distance From Home":         "DistanceFromHome",
    "Marital Status":             "MaritalStatus",
    "Percent Salary Hike":        "PercentSalaryHike",

    # OverTime
    "Over Time":                  "OverTime",
    "over_time":                  "OverTime",
    "overtime":                   "OverTime",
    "Overtime":                   "OverTime",          


    # ── New dataset specific aliases ──
    "Number of Promotions":       "NumberOfPromotions",  
    "Number of Dependents":       "NumberOfDependents",  
    "Education Level":            "EducationLevel",
    "Company Size":               "CompanySize",         
    "Remote Work":                "RemoteWork",          
    "Leadership Opportunities":   "LeadershipOpportunities",
    "Innovation Opportunities":   "InnovationOpportunities",
    "Company Reputation":         "CompanyReputation",
    "Employee Recognition":       "EmployeeRecognition",
}

# ── Attrition value sets ──
ATTRITION_YES = {
    "yes", "1", "true", "left", "voluntary",
    "resigned", "quit", "churned", "attrited"
}
ATTRITION_NO = {
    "no", "0", "false", "stayed", "active",
    "current", "retained", "employed"
}


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Step 1 — Rename columns to match our schema.
    Uses exact alias match first, then fuzzy lowercase match.
    """
    # Exact alias match
    df = df.rename(columns=COLUMN_ALIASES)

    # Fuzzy match — strip spaces, underscores, hyphens + lowercase
    # Now we only target REQUIRED_COLUMNS, plus keeping any extra columns safe for aliasing.
    our_cols = set(REQUIRED_COLUMNS)
    df_col_normalized = {
        c.lower().replace(" ", "").replace("_", "").replace("-", ""): c
        for c in df.columns
    }
    rename = {}
    for target in our_cols:
        if target in df.columns:
            continue
        key = target.lower().replace(" ", "").replace("_", "").replace("-", "")
        if key in df_col_normalized:
            rename[df_col_normalized[key]] = target

    return df.rename(columns=rename)


def normalize_attrition(df: pd.DataFrame) -> pd.DataFrame:
    """
    Step 2 — Normalize attrition column to Yes/No
    regardless of source format (Left/Stayed, 1/0, true/false etc.)
    """
    if "Attrition" not in df.columns:
        return df

    def map_val(val):
        if pd.isna(val):
            return "No"
        v = str(val).strip().lower()
        if v in ATTRITION_YES:
            return "Yes"
        if v in ATTRITION_NO:
            return "No"
        return "No"  

    df["Attrition"] = df["Attrition"].apply(map_val)
    return df


def encode_overtime(df: pd.DataFrame) -> pd.DataFrame:
    """
    Step 3a — Encode OverTime to binary integer.
    Defaults to 0 if column is missing.
    """
    if "OverTime" in df.columns:
        df["overtime"] = df["OverTime"].apply(
            lambda x: 1 if str(x).strip().lower() in {"yes", "1", "true"} else 0
        )
        print("  >> OverTime encoded: overtime (1=Yes, 0=No)")
    else:
        df["overtime"] = 0
    return df



def build_schema_report(
    df: pd.DataFrame,
    overtime_was_present: bool = False,
) -> dict:
    """
    Step 5 — Build report for CEO showing what was found.
    Since all core columns are strictly mandatory now, we just report
    whether the bonus features (overtime, travel) were found.
    """
    overtime_active = bool("overtime" in df.columns and df["overtime"].sum() > 0)

    bonus_features = []
    if overtime_active: bonus_features.append("OverTime")

    return {
        "bonus_features_found":      bonus_features,
        "overtime_encoded":          overtime_active,
        "overtime_was_in_upload":    overtime_was_present,
        "note": (
            "All mandatory columns present. Model will run successfully."
        ),
    }


def derive_missing_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Step 1b — Derive columns from alternative sources when primary is missing.
    Handles new dataset formats that don't have IBM HR column names.
    """
    # CompanyTenure → YearsAtCompany 
    if "YearsAtCompany" not in df.columns and "CompanyTenure" in df.columns:
        df["YearsAtCompany"] = df["CompanyTenure"]
        print("  >> YearsAtCompany: derived from CompanyTenure")

    # TotalWorkingYears — new dataset doesn't have this. Proxy = YearsAtCompany.
    if "TotalWorkingYears" not in df.columns and "YearsAtCompany" in df.columns:
        df["TotalWorkingYears"] = df["YearsAtCompany"]
        print("  >> TotalWorkingYears: derived from YearsAtCompany (proxy)")

    # NumberOfPromotions → YearsSinceLastPromotion (inverse relationship:
    # more promotions ≈ promoted recently → fewer years since last promotion)
    if "YearsSinceLastPromotion" not in df.columns and "NumberOfPromotions" in df.columns:
        import numpy as np
        promo = pd.to_numeric(df["NumberOfPromotions"], errors="coerce").fillna(0)
        # Simple inversion: 0 promotions → ~3 years, 5+ → ~0 years
        df["YearsSinceLastPromotion"] = (3 / (promo + 1)).round(0).astype(int)
        print("  >> YearsSinceLastPromotion: derived from NumberOfPromotions (inverted)")

    return df


def encode_satisfaction_scores(df: pd.DataFrame) -> pd.DataFrame:
    """
    Encode string satisfaction/rating columns to numeric 1-4 scale.
    Handles datasets that use 'Low/Medium/High/Very High' instead of integers.
    IBM HR datasets use integers already — those pass through unchanged.
    Detection uses pd.to_numeric (robust) rather than dtype check.
    """
    level_map = {
        "very low":       1, "low":           1, "poor":          1,
        "below average":  2, "medium":         2, "average":       2, "fair":          2,
        "high":           3, "good":           3, "above average": 3,
        "very high":      4, "excellent":      4, "outstanding":   4,
    }

    satisfaction_cols = [
        "JobSatisfaction", "WorkLifeBalance", "EnvironmentSatisfaction",
        "JobInvolvement", "PerformanceRating",
    ]

    for col in satisfaction_cols:
        if col not in df.columns:
            continue
        # Check if any values are non-numeric (i.e., strings like 'Low', 'High')
        numeric_attempt = pd.to_numeric(df[col], errors="coerce")
        has_string_values = numeric_attempt.isna().any() and df[col].notna().any()
        if has_string_values:
            encoded = df[col].apply(
                lambda x: level_map.get(str(x).strip().lower(), None)
            )
            mapped_mask = encoded.notna()
            df[col] = df[col].where(~mapped_mask, encoded)  # only overwrite mapped rows
            if mapped_mask.sum() > 0:
                print(f"  >> {col}: {mapped_mask.sum()} string labels encoded to 1-4")

    # ── JobLevel: encode string tiers to numeric scale ──
    # Handles 'Entry/Mid/Senior' style datasets instead of integers 1-5.
    job_level_map = {
        "entry":        1, "entry level":  1, "junior":       1,
        "associate":    2, "intermediate": 2,
        "mid":          3, "middle":       3,
        "lead":         4, "manager":      4,
        "senior":       5, "sr":           5, "director":     5, "executive":    5,
    }
    if "JobLevel" in df.columns:
        numeric_attempt = pd.to_numeric(df["JobLevel"], errors="coerce")
        if numeric_attempt.isna().any() and df["JobLevel"].notna().any():
            encoded = df["JobLevel"].apply(
                lambda x: job_level_map.get(str(x).strip().lower(), None)
            )
            mapped_mask = encoded.notna()
            df["JobLevel"] = df["JobLevel"].where(~mapped_mask, encoded)
            print(f"  >> JobLevel: {mapped_mask.sum()} string tiers encoded (Entry=1 Mid=3 Senior=5)")

    return df


def normalize_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, bool]:
    """
    Full normalization pipeline — call this in upload_routes.py.
    Returns (normalized_df, overtime_was_present).
    """
    df = normalize_columns(df)
    df = derive_missing_columns(df)         # handle dataset-specific derivations
    df = encode_satisfaction_scores(df)      # convert Low/High/Very High → 1-4 BEFORE cleaning
    overtime_was_present = "OverTime" in df.columns  # capture BEFORE encode drops it
    df = normalize_attrition(df)
    df = encode_overtime(df)
    return df, overtime_was_present

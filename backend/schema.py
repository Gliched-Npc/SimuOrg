# backend/schema.py
#
# Handles all incoming dataset normalization:
#   - Column name aliases (different HR systems name things differently)
#   - Attrition value normalization (Yes/No/Left/Stayed/1/0 etc.)
#   - Optional column defaults (fill missing columns with sensible values)
#   - Schema report (tell CEO what was found vs missing)

import pandas as pd

# ── Hard required — upload fails without these ──
REQUIRED_COLUMNS = [
    "EmployeeID", "Department", "JobRole", "JobLevel",
    "MonthlyIncome", "YearsAtCompany", "TotalWorkingYears",
    "NumCompaniesWorked", "JobSatisfaction", "WorkLifeBalance",
    "EnvironmentSatisfaction", "JobInvolvement", "PerformanceRating",
    "Attrition",
]

# ── Optional — filled with defaults if missing ──
OPTIONAL_COLUMNS = {
    "ManagerID":               0,
    "Age":                     35,
    "Gender":                  "Unknown",
    "MaritalStatus":           "Unknown",
    "DistanceFromHome":        0,
    "PercentSalaryHike":       0,
    "StockOptionLevel":        0,
    "YearsSinceLastPromotion": 0,
    "YearsWithCurrManager":    0,
    "YearsInCurrentRole":      0,
    # OverTime and BusinessTravel handled separately — need encoding
}

# ── High-value optional features — shown in schema report if missing ──
HIGH_VALUE_COLUMNS = {
    "OverTime": "strong attrition predictor — could improve model AUC by 3-5%",
    "BusinessTravel": "frequent travelers quit ~2x more — strong signal",
}

# ── Column name aliases ──
# Maps any known variation to our canonical schema name
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

    # Tenure
    "Years at Company":           "YearsAtCompany",
    "Years_at_Company":           "YearsAtCompany",
    "Company Tenure":             "YearsAtCompany",
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

    # Other fields
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

    # BusinessTravel
    "Business Travel":            "BusinessTravel",
    "Business_Travel":            "BusinessTravel",
    "business_travel":            "BusinessTravel",
    "Travel":                     "BusinessTravel",
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
    our_cols = set(REQUIRED_COLUMNS) | set(OPTIONAL_COLUMNS.keys()) | set(HIGH_VALUE_COLUMNS.keys())
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
        return "No"  # safe default

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
        print("  ↳ OverTime encoded → overtime (1=Yes, 0=No)")
    else:
        df["overtime"] = 0
    return df


def encode_business_travel(df: pd.DataFrame) -> pd.DataFrame:
    """
    Step 3b — Encode BusinessTravel to ordinal integer.
    Non-Travel=0, Travel_Rarely=1, Travel_Frequently=2.
    Defaults to 0 if column is missing.
    """
    travel_map = {
        "non-travel": 0, "non_travel": 0, "no": 0, "none": 0,
        "travel_rarely": 1, "rarely": 1, "low": 1,
        "travel_frequently": 2, "frequently": 2, "high": 2, "yes": 2,
    }
    if "BusinessTravel" in df.columns:
        df["business_travel"] = df["BusinessTravel"].apply(
            lambda x: travel_map.get(str(x).strip().lower().replace(" ", "_"), 0)
        )
        print("  ↳ BusinessTravel encoded → business_travel (0=No, 1=Rarely, 2=Frequently)")
    else:
        df["business_travel"] = 0
    return df


def apply_optional_defaults(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str], list[str]]:
    """
    Step 4 — Fill missing optional columns with defaults.
    Returns (df, missing_optional, found_optional).
    """
    missing = []
    found   = []

    for col, default in OPTIONAL_COLUMNS.items():
        if col not in df.columns:
            df[col] = default
            missing.append(col)
            print(f"  ↳ {col}: not found — using default ({default})")
        else:
            found.append(col)

    return df, missing, found


def build_schema_report(
    df: pd.DataFrame,
    missing_optional: list[str],
    found_optional: list[str],
    overtime_was_present: bool = False,
    travel_was_present: bool = False,
) -> dict:
    """
    Step 5 — Build report for CEO showing what was found vs missing.
    overtime_was_present: True if OverTime column existed in the original upload.
    """
    high_value_missing = []
    for col, reason in HIGH_VALUE_COLUMNS.items():
        # OverTime/BusinessTravel are consumed by encoders — use flags
        if col == "OverTime" and not overtime_was_present:
            high_value_missing.append(
                f"{col} ({reason}) — defaulted to 0 (no overtime) for all employees"
            )
        elif col == "BusinessTravel" and not travel_was_present:
            high_value_missing.append(
                f"{col} ({reason}) — defaulted to 0 (non-travel) for all employees"
            )

    overtime_active = bool("overtime" in df.columns and df["overtime"].sum() > 0)
    travel_active   = bool("business_travel" in df.columns and df["business_travel"].sum() > 0)

    return {
        "optional_features_found":   found_optional,
        "optional_features_missing": missing_optional,
        "high_value_missing":        high_value_missing,
        "overtime_encoded":          overtime_active,
        "overtime_was_in_upload":    overtime_was_present,
        "travel_encoded":            travel_active,
        "travel_was_in_upload":      travel_was_present,
        "note": (
            "All recommended columns present. Model will use full feature set."
            if not missing_optional and not high_value_missing else
            f"{len(missing_optional)} optional column(s) missing — filled with defaults. "
            f"Providing these would improve simulation accuracy."
        ),
    }


def normalize_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str], list[str], bool, bool]:
    """
    Full normalization pipeline — call this in upload_routes.py.
    Returns (normalized_df, missing_optional, found_optional, overtime_was_present, travel_was_present).
    """
    df = normalize_columns(df)
    overtime_was_present = "OverTime" in df.columns  # capture BEFORE encode drops it
    travel_was_present   = "BusinessTravel" in df.columns
    df = normalize_attrition(df)
    df = encode_overtime(df)
    df = encode_business_travel(df)
    df, missing_optional, found_optional = apply_optional_defaults(df)
    return df, missing_optional, found_optional, overtime_was_present, travel_was_present
# backend/upload.py

import pandas as pd
from sqlalchemy import text
from sqlmodel import Session

from backend.db.database import engine, init_db
from backend.db.models import Employee

# ── Column definitions and normalization logic live in backend/schema.py ──


def clean_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, int, int, dict, list[str]]:
    print("=== Cleaning data...")
    raw_total = len(df)
    cleaning_audit = []

    # Capture missing data stats BEFORE filling NaNs
    null_rates = (df.isnull().sum() / raw_total).to_dict() if raw_total > 0 else {}

    # --- EmployeeID ---
    df["EmployeeID"] = pd.to_numeric(df["EmployeeID"], errors="coerce")
    df["EmployeeID"] = df["EmployeeID"].round(0)
    df = df.dropna(subset=["EmployeeID"])
    df["EmployeeID"] = df["EmployeeID"].astype(int)

    before_junk = len(df)
    # Drop rows where more than 40% of values are NaN (Sparse/Trash rows)
    # We have ~25-30 columns, so if > 10-12 are missing, the row is junk.
    thresh = int(len(df.columns) * 0.6)
    df = df.dropna(thresh=thresh)
    junk_removed = before_junk - len(df)
    if junk_removed > 0:
        print(f"  >> Purged {junk_removed} junk rows (insufficient data)")

    before_dupes = len(df)
    df = df.drop_duplicates(subset=["EmployeeID"])
    duplicates_removed = before_dupes - len(df)
    if duplicates_removed > 0:
        print(f"  >> Removed {duplicates_removed} duplicate EmployeeIDs")

    # --- ManagerID ---
    df["ManagerID"] = pd.to_numeric(df["ManagerID"], errors="coerce")
    df["ManagerID"] = df["ManagerID"].round(0).fillna(0).astype(int)

    # --- Age ---
    df["Age"] = pd.to_numeric(df["Age"], errors="coerce")
    age_nulls = df["Age"].isna().sum()
    _median_age = df["Age"].median()
    df["Age"] = df["Age"].round(0).fillna(_median_age).astype(int)
    if age_nulls > 0:
        cleaning_audit.append(
            f"Age: Filled {age_nulls} missing values with median ({_median_age:.0f})"
        )

    age_clipped = ((df["Age"] < 18) | (df["Age"] > 80)).sum()
    df["Age"] = df["Age"].clip(lower=18, upper=80)
    if age_clipped > 0:
        cleaning_audit.append(f"Age: Clipped {age_clipped} extreme values to [18, 80] range")

    # --- JobLevel ---
    df["JobLevel"] = pd.to_numeric(df["JobLevel"], errors="coerce")
    jl_nulls = df["JobLevel"].isna().sum()
    df["JobLevel"] = df["JobLevel"].round(0).fillna(1).astype(int)
    if jl_nulls > 0:
        cleaning_audit.append(f"JobLevel: Filled {jl_nulls} missing values with 1 (Entry)")

    jl_clipped = ((df["JobLevel"] < 1) | (df["JobLevel"] > 5)).sum()
    df["JobLevel"] = df["JobLevel"].clip(lower=1, upper=5)
    if jl_clipped > 0:
        cleaning_audit.append(f"JobLevel: Clipped {jl_clipped} values to [1, 5] range")

    # --- MonthlyIncome ---
    df["MonthlyIncome"] = pd.to_numeric(df["MonthlyIncome"], errors="coerce")
    mi_nulls = df["MonthlyIncome"].isna().sum()
    _med_income = df["MonthlyIncome"].median()
    df["MonthlyIncome"] = df["MonthlyIncome"].fillna(_med_income)
    if mi_nulls > 0:
        cleaning_audit.append(
            f"MonthlyIncome: Filled {mi_nulls} missing values with median (${_med_income:,.0f})"
        )

    mi_neg = (df["MonthlyIncome"] < 0).sum()
    df["MonthlyIncome"] = df["MonthlyIncome"].clip(lower=0).round(0).astype(int)
    if mi_neg > 0:
        cleaning_audit.append(f"MonthlyIncome: Clipped {mi_neg} negative values to $0")

    # --- YearsAtCompany ---
    df["YearsAtCompany"] = pd.to_numeric(df["YearsAtCompany"], errors="coerce")
    yac_nulls = df["YearsAtCompany"].isna().sum()
    df["YearsAtCompany"] = df["YearsAtCompany"].round(0).fillna(0).astype(int)
    if yac_nulls > 0:
        cleaning_audit.append(f"YearsAtCompany: Filled {yac_nulls} missing values with 0")
    df["YearsAtCompany"] = df["YearsAtCompany"].clip(lower=0)

    # --- PerformanceRating ---
    if "PerformanceRating" in df.columns:
        df["PerformanceRating"] = pd.to_numeric(df["PerformanceRating"], errors="coerce")
        pr_nulls = df["PerformanceRating"].isna().sum()
        _perf_mode = (
            int(df["PerformanceRating"].dropna().mode().iloc[0])
            if df["PerformanceRating"].notna().any()
            else 3
        )
        df["PerformanceRating"] = df["PerformanceRating"].round(0).fillna(_perf_mode).astype(int)
        if pr_nulls > 0:
            cleaning_audit.append(
                f"PerformanceRating: Filled {pr_nulls} missing values with mode ({_perf_mode})"
            )
        df["PerformanceRating"] = df["PerformanceRating"].clip(lower=1, upper=4)
    else:
        df["PerformanceRating"] = 3  # Neutral default

    # --- JobInvolvement ---
    if "JobInvolvement" in df.columns:
        df["JobInvolvement"] = pd.to_numeric(df["JobInvolvement"], errors="coerce")
        ji_nulls = df["JobInvolvement"].isna().sum()
        _inv_mode = (
            int(df["JobInvolvement"].dropna().mode().iloc[0])
            if df["JobInvolvement"].notna().any()
            else 3
        )
        df["JobInvolvement"] = df["JobInvolvement"].round(0).fillna(_inv_mode).astype(int)
        if ji_nulls > 0:
            cleaning_audit.append(
                f"JobInvolvement: Filled {ji_nulls} missing values with mode ({_inv_mode})"
            )
        df["JobInvolvement"] = df["JobInvolvement"].clip(lower=1, upper=4)
    else:
        df["JobInvolvement"] = 3  # Neutral default

    # --- YearsSinceLastPromotion ---
    df["YearsSinceLastPromotion"] = pd.to_numeric(df["YearsSinceLastPromotion"], errors="coerce")
    yslp_nulls = df["YearsSinceLastPromotion"].isna().sum()
    df["YearsSinceLastPromotion"] = df["YearsSinceLastPromotion"].round(0).fillna(0).astype(int)
    if yslp_nulls > 0:
        cleaning_audit.append(f"YearsSinceLastPromotion: Filled {yslp_nulls} missing values with 0")
    df["YearsSinceLastPromotion"] = df["YearsSinceLastPromotion"].clip(lower=0)

    # --- YearsWithCurrManager ---
    df["YearsWithCurrManager"] = pd.to_numeric(df["YearsWithCurrManager"], errors="coerce")
    ywcm_nulls = df["YearsWithCurrManager"].isna().sum()
    df["YearsWithCurrManager"] = df["YearsWithCurrManager"].round(0).fillna(0).astype(int)
    if ywcm_nulls > 0:
        cleaning_audit.append(f"YearsWithCurrManager: Filled {ywcm_nulls} missing values with 0")
    df["YearsWithCurrManager"] = df["YearsWithCurrManager"].clip(lower=0)

    # --- StockOptionLevel ---
    df["StockOptionLevel"] = pd.to_numeric(df.get("StockOptionLevel", 0), errors="coerce")
    sol_nulls = df["StockOptionLevel"].isna().sum()
    df["StockOptionLevel"] = df["StockOptionLevel"].round(0).fillna(0).astype(int)
    if sol_nulls > 0:
        cleaning_audit.append(f"StockOptionLevel: Filled {sol_nulls} missing values with 0")
    df["StockOptionLevel"] = df["StockOptionLevel"].clip(lower=0)

    # --- DistanceFromHome ---
    df["DistanceFromHome"] = pd.to_numeric(df.get("DistanceFromHome", 0), errors="coerce")
    dfh_nulls = df["DistanceFromHome"].isna().sum()
    df["DistanceFromHome"] = df["DistanceFromHome"].fillna(0).round(0).astype(int)
    if dfh_nulls > 0:
        cleaning_audit.append(f"DistanceFromHome: Filled {dfh_nulls} missing values with 0")
    df["DistanceFromHome"] = df["DistanceFromHome"].clip(lower=0)

    # --- PercentSalaryHike ---
    df["PercentSalaryHike"] = pd.to_numeric(df.get("PercentSalaryHike", 0), errors="coerce")
    psh_nulls = df["PercentSalaryHike"].isna().sum()
    df["PercentSalaryHike"] = df["PercentSalaryHike"].fillna(0).round(0).astype(int)
    if psh_nulls > 0:
        cleaning_audit.append(f"PercentSalaryHike: Filled {psh_nulls} missing values with 0%")
    df["PercentSalaryHike"] = df["PercentSalaryHike"].clip(lower=0)

    # --- YearsInCurrentRole ---
    df["YearsInCurrentRole"] = pd.to_numeric(df.get("YearsInCurrentRole", 0), errors="coerce")
    yicr_nulls = df["YearsInCurrentRole"].isna().sum()
    df["YearsInCurrentRole"] = df["YearsInCurrentRole"].round(0).fillna(0).astype(int)
    if yicr_nulls > 0:
        cleaning_audit.append(f"YearsInCurrentRole: Filled {yicr_nulls} missing values with 0")
    df["YearsInCurrentRole"] = df["YearsInCurrentRole"].clip(lower=0)

    # --- Fill nulls with median for float columns ---
    median_cols = [
        "TotalWorkingYears",
        "NumCompaniesWorked",
        "JobSatisfaction",
        "WorkLifeBalance",
        "EnvironmentSatisfaction",
    ]
    for col in median_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
            missing = df[col].isna().sum()
            _med = df[col].median()
            df[col] = df[col].fillna(_med)
            if missing > 0:
                cleaning_audit.append(
                    f"{col}: Filled {missing} missing values with median ({_med:.1f})"
                )

    # --- Clip satisfaction scores ---
    for col in ["JobSatisfaction", "WorkLifeBalance", "EnvironmentSatisfaction"]:
        df[col] = df[col].clip(lower=1.0, upper=4.0)

    df["TotalWorkingYears"] = df["TotalWorkingYears"].clip(lower=0)
    df["NumCompaniesWorked"] = df["NumCompaniesWorked"].clip(lower=0)

    # --- Normalize string columns if present ---
    df["Attrition"] = df["Attrition"].fillna("No")
    if "Gender" in df.columns:
        df["Gender"] = df["Gender"].fillna("Unknown").str.strip().str.capitalize()
    if "JobRole" in df.columns:
        df["JobRole"] = df["JobRole"].fillna("Unknown").str.strip().str.title()
    if "Department" in df.columns:
        df["Department"] = df["Department"].fillna("Unknown").str.strip().str.title()
    if "MaritalStatus" in df.columns:
        df["MaritalStatus"] = df["MaritalStatus"].fillna("Unknown").str.strip().str.capitalize()

    # NOTE: OverTime is already encoded to `overtime` by schema.normalize_dataframe()
    # before clean_dataframe() is called — no re-encoding needed here.

    print(f"[done] Cleaning done. {len(df)} rows ready.")
    return df, duplicates_removed, junk_removed, null_rates, cleaning_audit


def ingest_from_dataframe(df: pd.DataFrame, session_id: str = "global") -> dict:
    employees = []
    skipped = 0

    records = df.to_dict("records")
    for row in records:
        try:
            mgr_id = int(row["ManagerID"])
            if mgr_id == 0:
                mgr_id = None

            emp = Employee(
                employee_id=int(row["EmployeeID"]),
                department=row["Department"],
                job_role=row["JobRole"],
                job_level=int(row["JobLevel"]),
                manager_id=mgr_id,
                simulation_id="master",
                age=int(row["Age"]),
                gender=row.get("Gender", "Unknown"),
                monthly_income=int(row["MonthlyIncome"]),
                years_at_company=int(row["YearsAtCompany"]),
                total_working_years=float(row["TotalWorkingYears"]),
                num_companies_worked=float(row["NumCompaniesWorked"]),
                performance_rating=int(row["PerformanceRating"]),
                job_satisfaction=float(row["JobSatisfaction"]),
                work_life_balance=float(row["WorkLifeBalance"]),
                environment_satisfaction=float(row["EnvironmentSatisfaction"]),
                job_involvement=int(row["JobInvolvement"]),
                attrition=row["Attrition"],
                years_since_last_promotion=int(row["YearsSinceLastPromotion"]),
                years_with_curr_manager=int(row["YearsWithCurrManager"]),
                stock_option_level=int(row.get("StockOptionLevel", 0)),
                marital_status=str(row.get("MaritalStatus", "Unknown")),
                distance_from_home=int(row.get("DistanceFromHome", 0)),
                percent_salary_hike=int(row.get("PercentSalaryHike", 0)),
                years_in_current_role=int(row.get("YearsInCurrentRole", 0)),
                overtime=int(row.get("overtime", 0)),
                session_id=session_id,
            )
            employees.append(emp)
        except Exception as e:
            print(f"--- Skipping bad row: {e}")
            skipped += 1
            continue

    with Session(engine) as session:
        session.exec(
            text("DELETE FROM employee WHERE session_id = :sid"), params={"sid": session_id}
        )
        session.add_all(employees)
        session.commit()

    print(f"[done] {len(employees)} employees ingested. Skipped: {skipped}")
    return {"ingested": len(employees), "skipped": skipped}


def ingest_data():
    print("=== Starting Ingestion...")
    init_db()
    print("+++ Database Connection: OK")

    try:
        df = pd.read_csv("backend/data/SimuOrg_Master_Dataset.csv")
    except FileNotFoundError:
        print("--- Error: File not found in backend/data/")
        return

    print(f">> Found {len(df)} rows. Normalizing...")
    from backend.schema import normalize_dataframe

    df, *_ = normalize_dataframe(df)  # same normalization as Swagger path
    print(">> Cleaning...")
    df, *_ = clean_dataframe(df)
    ingest_from_dataframe(df)


if __name__ == "__main__":
    ingest_data()

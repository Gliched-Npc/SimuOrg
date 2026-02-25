# backend/upload.py

import pandas as pd
from sqlalchemy import text
from sqlmodel import Session
from backend.database import engine, init_db
from backend.models import Employee

# ── Column definitions and normalization logic live in backend/schema.py ──


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    print("🧹 Cleaning data...")

    # --- EmployeeID ---
    df['EmployeeID'] = pd.to_numeric(df['EmployeeID'], errors='coerce')
    df['EmployeeID'] = df['EmployeeID'].round(0)
    df = df.dropna(subset=['EmployeeID'])
    df['EmployeeID'] = df['EmployeeID'].astype(int)

    before = len(df)
    df = df.drop_duplicates(subset=['EmployeeID'])
    if len(df) < before:
        print(f"  ↳ Removed {before - len(df)} duplicate EmployeeIDs")

    # --- ManagerID ---
    if 'ManagerID' in df.columns:
        df['ManagerID'] = pd.to_numeric(df['ManagerID'], errors='coerce')
        df['ManagerID'] = df['ManagerID'].round(0).fillna(0).astype(int)
    else:
        df['ManagerID'] = 0

    # --- Age ---
    df['Age'] = pd.to_numeric(df['Age'], errors='coerce')
    df['Age'] = df['Age'].round(0).fillna(35).astype(int)
    df['Age'] = df['Age'].clip(lower=18, upper=80)

    # --- JobLevel ---
    df['JobLevel'] = pd.to_numeric(df['JobLevel'], errors='coerce')
    df['JobLevel'] = df['JobLevel'].round(0).fillna(1).astype(int)
    df['JobLevel'] = df['JobLevel'].clip(lower=1)

    # --- MonthlyIncome ---
    df['MonthlyIncome'] = pd.to_numeric(df['MonthlyIncome'], errors='coerce')
    df['MonthlyIncome'] = df['MonthlyIncome'].fillna(df['MonthlyIncome'].median())
    df['MonthlyIncome'] = df['MonthlyIncome'].clip(lower=0).round(0).astype(int)

    # --- YearsAtCompany ---
    df['YearsAtCompany'] = pd.to_numeric(df['YearsAtCompany'], errors='coerce')
    df['YearsAtCompany'] = df['YearsAtCompany'].round(0).fillna(0).astype(int)
    df['YearsAtCompany'] = df['YearsAtCompany'].clip(lower=0)

    # --- PerformanceRating ---
    df['PerformanceRating'] = pd.to_numeric(df['PerformanceRating'], errors='coerce')
    df['PerformanceRating'] = df['PerformanceRating'].round(0).fillna(3).astype(int)
    df['PerformanceRating'] = df['PerformanceRating'].clip(lower=1, upper=4)

    # --- JobInvolvement ---
    df['JobInvolvement'] = pd.to_numeric(df['JobInvolvement'], errors='coerce')
    df['JobInvolvement'] = df['JobInvolvement'].round(0).fillna(2).astype(int)
    df['JobInvolvement'] = df['JobInvolvement'].clip(lower=1, upper=4)

    # --- YearsSinceLastPromotion ---
    df['YearsSinceLastPromotion'] = pd.to_numeric(df['YearsSinceLastPromotion'], errors='coerce')
    df['YearsSinceLastPromotion'] = df['YearsSinceLastPromotion'].round(0).fillna(0).astype(int)
    df['YearsSinceLastPromotion'] = df['YearsSinceLastPromotion'].clip(lower=0)

    # --- YearsWithCurrManager ---
    df['YearsWithCurrManager'] = pd.to_numeric(df['YearsWithCurrManager'], errors='coerce')
    df['YearsWithCurrManager'] = df['YearsWithCurrManager'].round(0).fillna(0).astype(int)
    df['YearsWithCurrManager'] = df['YearsWithCurrManager'].clip(lower=0)

    # --- StockOptionLevel ---
    df['StockOptionLevel'] = pd.to_numeric(df.get('StockOptionLevel', 0), errors='coerce')
    df['StockOptionLevel'] = df['StockOptionLevel'].round(0).fillna(0).astype(int)
    df['StockOptionLevel'] = df['StockOptionLevel'].clip(lower=0)

    # --- DistanceFromHome ---
    df['DistanceFromHome'] = pd.to_numeric(df.get('DistanceFromHome', 0), errors='coerce')
    df['DistanceFromHome'] = df['DistanceFromHome'].fillna(0).round(0).astype(int)
    df['DistanceFromHome'] = df['DistanceFromHome'].clip(lower=0)

    # --- PercentSalaryHike ---
    df['PercentSalaryHike'] = pd.to_numeric(df.get('PercentSalaryHike', 0), errors='coerce')
    df['PercentSalaryHike'] = df['PercentSalaryHike'].fillna(0).round(0).astype(int)
    df['PercentSalaryHike'] = df['PercentSalaryHike'].clip(lower=0)

    # --- YearsInCurrentRole ---
    df['YearsInCurrentRole'] = pd.to_numeric(df.get('YearsInCurrentRole', 0), errors='coerce')
    df['YearsInCurrentRole'] = df['YearsInCurrentRole'].round(0).fillna(0).astype(int)
    df['YearsInCurrentRole'] = df['YearsInCurrentRole'].clip(lower=0)

    # --- Fill nulls with median for float columns ---
    median_cols = [
        'TotalWorkingYears', 'NumCompaniesWorked',
        'JobSatisfaction', 'WorkLifeBalance', 'EnvironmentSatisfaction',
    ]
    for col in median_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            missing = df[col].isna().sum()
            df[col] = df[col].fillna(df[col].median())
            if missing > 0:
                print(f"  ↳ {col}: filled {missing} nulls with median")

    # --- Clip satisfaction scores ---
    for col in ['JobSatisfaction', 'WorkLifeBalance', 'EnvironmentSatisfaction']:
        df[col] = df[col].clip(lower=1.0, upper=4.0)

    df['NumCompaniesWorked'] = df['NumCompaniesWorked'].clip(lower=0)
    df['TotalWorkingYears']  = df['TotalWorkingYears'].clip(lower=0)

    # --- Normalize string columns ---
    df['Attrition']     = df['Attrition'].fillna('No')
    df['Gender']        = df['Gender'].fillna('Unknown').str.strip().str.capitalize()
    df['JobRole']       = df['JobRole'].fillna('Unknown').str.strip().str.title()
    df['Department']    = df['Department'].fillna('Unknown').str.strip().str.title()
    df['MaritalStatus'] = df['MaritalStatus'].fillna('Unknown').str.strip().str.capitalize()

    # NOTE: OverTime is already encoded to `overtime` by schema.normalize_dataframe()
    # before clean_dataframe() is called — no re-encoding needed here.

    print(f"✅ Cleaning done. {len(df)} rows ready.")
    return df


def validate_data_quality(df: pd.DataFrame) -> dict:
    warnings = []
    errors   = []
    total    = len(df)

    attrition_count = (df['Attrition'] == 'Yes').sum()
    attrition_rate  = attrition_count / total
    if attrition_rate > 0.30:
        warnings.append(
            f"High attrition rate detected: {attrition_rate*100:.1f}% "
            f"(industry average is 10-20%). Data may be unreliable."
        )

    if total < 50:
        warnings.append(
            f"Small dataset: only {total} employees. "
            f"Simulation results may not be statistically reliable."
        )

    duplication_rate = 1 - (total / (total + df.duplicated().sum()))
    if duplication_rate > 0.20:
        warnings.append("High duplication rate detected before cleaning. Data quality may be poor.")

    invalid_levels = ((df['JobLevel'] < 1) | (df['JobLevel'] > 5)).sum()
    if invalid_levels > total * 0.10:
        warnings.append(
            f"{invalid_levels} employees had invalid job levels (outside 1-5). "
            f"These were clipped automatically."
        )

    negative_income = (df['MonthlyIncome'] < 0).sum()
    if negative_income > 0:
        warnings.append(
            f"{negative_income} employees had negative monthly income. "
            f"These were set to 0 automatically."
        )

    return {"warnings": warnings, "errors": errors, "passed": len(errors) == 0}


def ingest_from_dataframe(df: pd.DataFrame) -> dict:
    employees = []
    skipped   = 0

    for _, row in df.iterrows():
        try:
            mgr_id = int(row['ManagerID'])
            if mgr_id == 0:
                mgr_id = None

            emp = Employee(
                employee_id                = int(row['EmployeeID']),
                department                 = row['Department'],
                job_role                   = row['JobRole'],
                job_level                  = int(row['JobLevel']),
                manager_id                 = mgr_id,
                simulation_id              = "master",
                age                        = int(row['Age']),
                gender                     = row['Gender'],
                monthly_income             = int(row['MonthlyIncome']),
                years_at_company           = int(row['YearsAtCompany']),
                total_working_years        = float(row['TotalWorkingYears']),
                num_companies_worked       = float(row['NumCompaniesWorked']),
                performance_rating         = int(row['PerformanceRating']),
                job_satisfaction           = float(row['JobSatisfaction']),
                work_life_balance          = float(row['WorkLifeBalance']),
                environment_satisfaction   = float(row['EnvironmentSatisfaction']),
                job_involvement            = int(row['JobInvolvement']),
                attrition                  = row['Attrition'],
                years_since_last_promotion = int(row['YearsSinceLastPromotion']),
                years_with_curr_manager    = int(row['YearsWithCurrManager']),
                stock_option_level         = int(row.get('StockOptionLevel', 0)),
                marital_status             = str(row.get('MaritalStatus', 'Unknown')),
                distance_from_home         = int(row.get('DistanceFromHome', 0)),
                percent_salary_hike        = int(row.get('PercentSalaryHike', 0)),
                years_in_current_role      = int(row.get('YearsInCurrentRole', 0)),
                overtime                   = int(row.get('overtime', 0)),
                business_travel            = int(row.get('business_travel', 0)),
            )
            employees.append(emp)
        except Exception as e:
            print(f"⚠️ Skipping bad row: {e}")
            skipped += 1
            continue

    with Session(engine) as session:
        session.exec(text("TRUNCATE TABLE employee RESTART IDENTITY CASCADE"))
        session.commit()
        session.add_all(employees)
        session.commit()

    print(f"✅ SUCCESS! {len(employees)} employees ingested. Skipped: {skipped}")
    return {"ingested": len(employees), "skipped": skipped}


def ingest_data():
    print("🚀 Starting Ingestion...")
    init_db()
    print("✅ Database Connection: OK")

    try:
        df = pd.read_csv("backend/data/SimuOrg_Master_Dataset.csv")
    except FileNotFoundError:
        print("❌ Error: File not found in backend/data/")
        return

    print(f"📄 Found {len(df)} rows. Cleaning...")
    df = clean_dataframe(df)
    ingest_from_dataframe(df)


if __name__ == "__main__":
    ingest_data()
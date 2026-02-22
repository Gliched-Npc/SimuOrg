# backend/upload.py

import pandas as pd
from sqlalchemy import text
from sqlmodel import Session, delete
from backend.database import engine, init_db
from backend.models import Employee

REQUIRED_COLUMNS = [
    "EmployeeID", "Department", "JobRole", "JobLevel",
    "Age", "Gender", "MonthlyIncome", "YearsAtCompany",
    "TotalWorkingYears", "NumCompaniesWorked", "PerformanceRating",
    "JobSatisfaction", "WorkLifeBalance", "EnvironmentSatisfaction",
    "JobInvolvement", "Attrition", "YearsSinceLastPromotion",
    "YearsWithCurrManager",
]


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    print("🧹 Cleaning data...")

    # --- EmployeeID ---
    df['EmployeeID'] = pd.to_numeric(df['EmployeeID'], errors='coerce')
    df['EmployeeID'] = df['EmployeeID'].round(0)
    df = df.dropna(subset=['EmployeeID'])  # drop rows with no EmployeeID
    df['EmployeeID'] = df['EmployeeID'].astype(int)

    # Remove duplicates after cleaning EmployeeID
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
    df['Age'] = df['Age'].round(0).fillna(30).astype(int)
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

    # --- Clip satisfaction scores to valid 1-4 range ---
    for col in ['JobSatisfaction', 'WorkLifeBalance', 'EnvironmentSatisfaction']:
        df[col] = df[col].clip(lower=1.0, upper=4.0)

    # --- NumCompaniesWorked ---
    df['NumCompaniesWorked'] = df['NumCompaniesWorked'].clip(lower=0)

    # --- TotalWorkingYears ---
    df['TotalWorkingYears'] = df['TotalWorkingYears'].clip(lower=0)

    # --- Normalize string columns ---
    
    df['Attrition']  = df['Attrition'].fillna('No').str.strip().str.capitalize()
    df['Attrition']  = df['Attrition'].map({'Yes': 'Yes', 'No': 'No'}).fillna('No')
    df['Gender']     = df['Gender'].fillna('Unknown').str.strip().str.capitalize()
    df['JobRole']    = df['JobRole'].fillna('Unknown').str.strip().str.title()
    df['Department'] = df['Department'].fillna('Unknown').str.strip().str.title()

    print(f"✅ Cleaning done. {len(df)} rows ready.")
    return df

def validate_data_quality(df: pd.DataFrame) -> dict:
    warnings = []
    errors   = []

    total = len(df)

    # Attrition rate check
    attrition_count = (df['Attrition'] == 'Yes').sum()
    attrition_rate  = attrition_count / total
    if attrition_rate > 0.30:
        warnings.append(
            f"High attrition rate detected: {attrition_rate*100:.1f}% "
            f"(industry average is 10-20%). Data may be unreliable."
        )

    # Minimum employee count
    if total < 50:
        warnings.append(
            f"Small dataset: only {total} employees. "
            f"Simulation results may not be statistically reliable."
        )

    # Duplicate check after cleaning
    duplication_rate = 1 - (total / (total + df.duplicated().sum()))
    if duplication_rate > 0.20:
        warnings.append(
            f"High duplication rate detected before cleaning. "
            f"Data quality may be poor."
        )

    # JobLevel sanity
    invalid_levels = ((df['JobLevel'] < 1) | (df['JobLevel'] > 5)).sum()
    if invalid_levels > total * 0.10:
        warnings.append(
            f"{invalid_levels} employees had invalid job levels (outside 1-5). "
            f"These were clipped automatically."
        )

    # Negative income check
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
            )
            employees.append(emp)
        except Exception as e:
            print(f"⚠️ Skipping bad row: {e}")
            skipped += 1
            continue

    # TRUNCATE is instant and guaranteed — bypasses SQLAlchemy batching
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
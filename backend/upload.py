import pandas as pd
from sqlmodel import Session, delete
from backend.database import engine, init_db
from backend.models import Employee

def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    print("🧹 Cleaning data...")

    df['ManagerID'] = pd.to_numeric(df['ManagerID'], errors='coerce')
    df['ManagerID'] = df['ManagerID'].fillna(0).astype(int)

    median_cols = [
        'TotalWorkingYears',
        'NumCompaniesWorked',
        'JobSatisfaction',
        'WorkLifeBalance',
        'EnvironmentSatisfaction'
    ]
    for col in median_cols:
        median_val = df[col].median()
        missing = df[col].isna().sum()
        df[col] = df[col].fillna(median_val)
        if missing > 0:
            print(f"  ↳ {col}: filled {missing} nulls with median ({median_val})")

    print("✅ Cleaning done.")
    return df


def ingest_data():
    print("🚀 Starting Ingestion...")

    # 1. Initialize DB
    init_db()
    print("✅ Database Connection: OK")

    # 2. Read CSV
    try:
        df = pd.read_csv("backend/data/SimuOrg_Master_Dataset.csv")
    except FileNotFoundError:
        print("❌ Error: File not found in backend/data/")
        return

    # 3. Clean
    print(f"📄 Found {len(df)} rows. Cleaning...")
    df = clean_dataframe(df)

    # 4. ← CLEAR EXISTING DATA HERE
    with Session(engine) as session:
        session.exec(delete(Employee))
        session.commit()
        print("🗑️ Cleared existing data.")

    # 5. Build employees list
    employees = []
    for _, row in df.iterrows():
        try:
            mgr_id = int(row['ManagerID'])
            if mgr_id == 0:
                mgr_id = None

            emp = Employee(
                employee_id=int(row['EmployeeID']),
                department=row['Department'],
                job_role=row['JobRole'],
                job_level=int(row['JobLevel']),
                manager_id=mgr_id,
                simulation_id="master",

                age=int(row['Age']),
                gender=row['Gender'],
                monthly_income=int(row['MonthlyIncome']),
                years_at_company=int(row['YearsAtCompany']),
                total_working_years=float(row['TotalWorkingYears']),
                num_companies_worked=float(row['NumCompaniesWorked']),

                performance_rating=int(row['PerformanceRating']),
                job_satisfaction=float(row['JobSatisfaction']),
                work_life_balance=float(row['WorkLifeBalance']),
                environment_satisfaction=float(row['EnvironmentSatisfaction']),
                job_involvement=int(row['JobInvolvement']),
                attrition=row['Attrition'],

                years_since_last_promotion=int(row['YearsSinceLastPromotion']),
                years_with_curr_manager=int(row['YearsWithCurrManager']),
            )
            employees.append(emp)
        except Exception as e:
            print(f"⚠️ Skipping bad row: {e}")
            continue

    # 6. Insert and commit
    with Session(engine) as session:
        session.add_all(employees)
        session.commit()

    print(f"✅ SUCCESS! {len(employees)} employees ingested into database.")


if __name__ == "__main__":
    ingest_data()
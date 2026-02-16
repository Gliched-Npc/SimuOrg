import pandas as pd
from sqlmodel import Session
from backend.database import engine, init_db
from backend.models import Employee

def ingest_data():
    print("🚀 Starting Ingestion...")
    
    # 1. Initialize DB (This tests the connection)
    init_db()
    print("✅ Database Connection: OK")
    
    # 2. Read CSV
    try:
        df = pd.read_csv("backend/data/SimuOrg_Master_Dataset.csv")
    except FileNotFoundError:
        print("❌ Error: File not found in backend/data/")
        return
    
    # 3. CLEANING: Handle "CEO" and other garbage in ManagerID
    # Force "CEO" or any text to become NaN (Not a Number)
    df['ManagerID'] = pd.to_numeric(df['ManagerID'], errors='coerce')
    # Fill those NaNs with 0
    df['ManagerID'] = df['ManagerID'].fillna(0).astype(int)
    
    employees = []
    print(f"📄 Found {len(df)} rows. Processing...")
    
    for _, row in df.iterrows():
        try:
            # Handle the 0 we just created
            mgr_id = int(row['ManagerID'])
            if mgr_id == 0:
                mgr_id = None  # In Database, None means "Top of the Hierarchy"

            emp = Employee(
                employee_id=int(row['EmployeeID']),
                department=row['Department'],
                job_role=row['JobRole'],
                job_level=int(row['JobLevel']),
                manager_id=mgr_id,
                
                # Critical Data
                age=int(row['Age']),
                gender=row['Gender'],
                monthly_income=int(row['MonthlyIncome']),
                performance_rating=int(row['PerformanceRating']),
                years_at_company=int(row['YearsAtCompany']),
                
                simulation_id="master"
            )
            employees.append(emp)
        except Exception as e:
            print(f"⚠️ Skipping bad row: {e}")
            continue

    # 4. Save to Database
    with Session(engine) as session:
        session.add_all(employees)
        session.commit()
    
    print("✅ SUCCESS! Database Hydrated.")

if __name__ == "__main__":
    ingest_data()
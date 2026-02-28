import sys
import os

# Ensure backend can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.ml.explain import explain_employee
from sqlmodel import Session, select
from backend.database import engine
from backend.models import Employee

def test_explain():
    # Find an employee to test with
    with Session(engine) as session:
        emp = session.exec(select(Employee)).first()
        
    if not emp:
        print("No employees found in DB!")
        return
        
    print(f"Testing employee {emp.employee_id}...")
    
    result = explain_employee(emp.employee_id)
    print("\n--- XAI Result ---")
    import json
    print(json.dumps(result, indent=2))
    
if __name__ == "__main__":
    test_explain()

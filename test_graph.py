from sqlmodel import Session, select
from backend.database import engine
from backend.models import Employee
from backend.simulation.engine import SimulationEngine

def run_simulation_test():
    # 1. Setup
    with Session(engine) as session:
        employees = session.exec(select(Employee)).all()

    print(f"🌍 Starting World with {len(employees)} employees.")
    sim = SimulationEngine(employees)

    # 2. Simulate 3 Months
    months = [
        {"name": "Month 1 (Stable)", "boost": 0.0},
        {"name": "Month 2 (Market Crash)", "boost": 0.05},
        {"name": "Month 3 (Panic)", "boost": 0.10}
    ]

    for m in months:
        print(f"\n� Running {m['name']}...")
        result = sim.run_step(attrition_boost=m['boost'])
        print(f"   📉 New Leavers: {result['new_leavers']}")
        print(f"   👥 Total Lost: {result['total_leavers']}")

    # 3. Final Report
    print("\n� FINAL SIMULATION REPORT:")
    print(sim.get_summary())

if __name__ == "__main__":
    run_simulation_test()
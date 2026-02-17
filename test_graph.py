from sqlmodel import Session, select
from backend.database import engine
from backend.models import Employee
from backend.simulation.graph_logic import OrgGraph
import time

def test_performance():
    print("⏳ Connecting to Docker Database...")
    
    # 1. Fetch Data
    t0 = time.time()
    with Session(engine) as session:
        employees = session.exec(select(Employee)).all()
    t1 = time.time()
    
    print(f"📄 Loaded {len(employees)} rows in {t1-t0:.4f}s")

    # 2. Build Graph
    print("\n🚀 Starting Graph Build...")
    org = OrgGraph()
    org.build(employees)

    # 3. Test Lookup Speed (O(1))
    # Let's find a manager with a lot of reports (e.g. Employee 2)
    # Note: If ID 2 doesn't exist, this won't crash, just returns empty list.
    # Find the "Power User" (Manager with most direct reports)
    # We sort all nodes by how many 'successors' (reports) they have
    top_manager = max(org.graph.nodes(), key=lambda n: len(list(org.graph.successors(n))))
    count = len(list(org.graph.successors(top_manager)))
    
    print(f"👑 Manager ID {top_manager} has the biggest team: {count} direct reports.")
    print(f"\n🔎 Testing Lookup for Manager ID {top_manager}...")
    
    t2 = time.time()
    team = org.get_team(top_manager)
    t3 = time.time()
    
    print(f"✅ Found {len(team)} direct reports in {t3-t2:.6f}s")

    # ... (keep your imports and setup)

    # 4. VISUALIZE THE TEAM
    print("\n🌳 Organizational Tree for Manager 4035 (Depth 1):")
    org.print_subtree(4035, max_depth=1)


    print("\n🕵️ Checking the team of Director 699 (who reports to 4035):")
    org.print_subtree(699, max_depth=1)

if __name__ == "__main__":
    test_performance()
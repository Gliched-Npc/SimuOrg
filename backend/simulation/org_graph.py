# backend/simulation/org_graph.py

import networkx as nx
from backend.simulation.agent import EmployeeAgent


def build_org_graph(agents: list[EmployeeAgent]) -> nx.Graph:
    print("🔨 Building organizational graph...")

    G = nx.Graph()

    # Step 1 — Add all agents as nodes
    for agent in agents:
        G.add_node(agent.employee_id, agent=agent)

    # Step 2 — Build lookup map
    id_to_agent = {a.employee_id: a for a in agents}
    avg_mgr_years = sum(
        getattr(a, 'years_with_curr_manager', 0) for a in agents
    ) / max(len(agents), 1)
    manager_edge_weight = round(min(0.6 + (avg_mgr_years / 10.0) * 0.35, 0.95), 2)


    # Step 3 — Add manager edges (real reporting lines)
    for agent in agents:
        if agent.manager_id and agent.manager_id in id_to_agent:
            G.add_edge(
                agent.employee_id,
                agent.manager_id,
                weight=manager_edge_weight,
                edge_type="manager"
            )

    # Step 4 — Dynamic peer weights based on actual max level in company
    # Higher level = less peer influence (more senior = more independent)
    max_level = max((a.job_level for a in agents), default=5)

    def peer_weight(level: int) -> float:
        # Scales from 0.8 (lowest level) to 0.5 (highest level)
        return round(0.8 - (level / max_level) * 0.3, 2)

    agents_by_dept_level = {}
    for agent in agents:
        key = (agent.department, agent.job_level)
        if key not in agents_by_dept_level:
            agents_by_dept_level[key] = []
        agents_by_dept_level[key].append(agent)

    MAX_PEERS = 10

    for (dept, level), group in agents_by_dept_level.items():
        weight = peer_weight(level)
        for i in range(len(group)):
            count = 0
            for j in range(i + 1, len(group)):
                if count >= MAX_PEERS:
                    break
                a1 = group[i]
                a2 = group[j]
                if not G.has_edge(a1.employee_id, a2.employee_id):
                    G.add_edge(
                        a1.employee_id,
                        a2.employee_id,
                        weight=weight,
                        edge_type="peer"
                    )
                    count += 1

    # Step 5 — Dynamic skip level edges
    # Any two levels that are 2+ apart in same department
    def skip_weight(level_low: int, level_high: int) -> float:
        gap = level_high - level_low
        # Larger gap = weaker influence
        return round(max(0.1, 0.4 - (gap - 1) * 0.1), 2)

    agents_by_dept = {}
    for agent in agents:
        if agent.department not in agents_by_dept:
            agents_by_dept[agent.department] = []
        agents_by_dept[agent.department].append(agent)

    MAX_SKIP = 5

    for dept, group in agents_by_dept.items():
        for i in range(len(group)):
            skip_count = 0
            for j in range(i + 1, len(group)):
                if skip_count >= MAX_SKIP:
                    break
                a1 = group[i]
                a2 = group[j]
                low  = min(a1.job_level, a2.job_level)
                high = max(a1.job_level, a2.job_level)
                gap  = high - low
                if gap >= 2:
                    if not G.has_edge(a1.employee_id, a2.employee_id):
                        G.add_edge(
                            a1.employee_id,
                            a2.employee_id,
                            weight=skip_weight(low, high),
                            edge_type="skip"
                        )
                        skip_count += 1

    print(f"✅ Graph built: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    return G


if __name__ == "__main__":
    from sqlmodel import Session, select
    from backend.database import engine
    from backend.models import Employee
    from backend.simulation.agent import EmployeeAgent

    with Session(engine) as session:
        employees = session.exec(select(Employee)).all()
    agents = [EmployeeAgent(emp) for emp in employees]
    G = build_org_graph(agents)
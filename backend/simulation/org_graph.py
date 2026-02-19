# backend/simulation/org_graph.py

import networkx as nx
from backend.simulation.agent import EmployeeAgent

def build_org_graph(agents: list[EmployeeAgent]) -> nx.Graph:
    print("🔨 Building organizational graph...")

    G = nx.Graph()

    # Step 1 — Add all agents as nodes
    for agent in agents:
        G.add_node(agent.employee_id, agent=agent)

    # Step 2 — Build lookup maps
    id_to_agent = {a.employee_id: a for a in agents}

    # Step 3 — Add edges based on ManagerID (real reporting lines)
    for agent in agents:
        if agent.manager_id and agent.manager_id in id_to_agent:
            G.add_edge(
                agent.employee_id,
                agent.manager_id,
                weight=0.9,
                edge_type="manager"
            )

    # Step 4 — Add peer edges (same department, same job level)
    peer_weights = {1: 0.8, 2: 0.7, 3: 0.6, 4: 0.6, 5: 0.5}

    agents_by_dept_level = {}
    for agent in agents:
        key = (agent.department, agent.job_level)
        if key not in agents_by_dept_level:
            agents_by_dept_level[key] = []
        agents_by_dept_level[key].append(agent)

    MAX_PEERS = 10

    for (dept, level), group in agents_by_dept_level.items():
        weight = peer_weights.get(level, 0.5)
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

    # Step 5 — Skip level edges (same dept, 2 levels apart)
    skip_weights = {(1, 3): 0.3, (1, 4): 0.2, (1, 5): 0.1,
                    (2, 4): 0.3, (2, 5): 0.15, (3, 5): 0.25}

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
                level_pair = tuple(sorted([a1.job_level, a2.job_level]))
                if level_pair in skip_weights:
                    if not G.has_edge(a1.employee_id, a2.employee_id):
                        G.add_edge(
                            a1.employee_id,
                            a2.employee_id,
                            weight=skip_weights[level_pair],
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
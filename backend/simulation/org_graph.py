# backend/simulation/org_graph.py

import networkx as nx
from backend.simulation.agent import EmployeeAgent


class OrgGraph:
    def __init__(self, agents: list[EmployeeAgent] = None, template_graph: nx.Graph = None):
        """
        Initialize the OrgGraph. If template_graph is provided, copy it and inject agents.
        Otherwise build from scratch.
        """
        if template_graph is not None and agents is not None:
            self.G = template_graph.copy()
            for agent in agents:
                if self.G.has_node(agent.employee_id):
                    self.G.nodes[agent.employee_id]['agent'] = agent
        elif agents is not None:
            self.G = self._build_graph(agents)
        else:
            self.G = nx.Graph()
            
    def _build_graph(self, agents: list[EmployeeAgent]) -> nx.Graph:
        print("🔨 Building organizational graph from scratch...")
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
        max_level = max((a.job_level for a in agents), default=5)
        
        def peer_weight(level: int) -> float:
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
        def skip_weight(level_low: int, level_high: int) -> float:
            gap = level_high - level_low
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

    # --- NETWORKX EXPOSED METHODS ___
    def has_node(self, n): return self.G.has_node(n)
    def add_node(self, node_for_adding, **attr): return self.G.add_node(node_for_adding, **attr)
    def remove_node(self, n): return self.G.remove_node(n)
    def has_edge(self, u, v): return self.G.has_edge(u, v)
    def add_edge(self, u_of_edge, v_of_edge, **attr): return self.G.add_edge(u_of_edge, v_of_edge, **attr)
    def neighbors(self, n): return self.G.neighbors(n)
    @property
    def nodes(self): return self.G.nodes
    @property
    def edges(self): return self.G.edges
    def __getitem__(self, n): return self.G[n]

    # --- ADVANCED TRAVERSAL LOGIC ---
    def get_direct_reports(self, manager_id: int) -> list[EmployeeAgent]:
        """Return a list of agents who report directly to manager_id."""
        if not self.has_node(manager_id):
            return []
        reports = []
        for neighbor_id in self.G.neighbors(manager_id):
            edge_data = self.G[manager_id][neighbor_id]
            if edge_data.get("edge_type") == "manager":
                # Check directional relationship from the node attributes or agents
                agent = self.G.nodes[neighbor_id].get("agent")
                if agent and agent.manager_id == manager_id:
                    reports.append(agent)
        return reports

    def get_chain_of_command(self, employee_id: int) -> list[EmployeeAgent]:
        """Return the chain of command going up to the CEO."""
        if not self.has_node(employee_id):
            return []
        
        chain = []
        current_id = employee_id
        
        # Safety limit for bad data (cycles)
        visited = set()
        
        while current_id is not None and current_id not in visited:
            visited.add(current_id)
            if not self.has_node(current_id):
                break
            agent = self.G.nodes[current_id].get("agent")
            if not agent:
                break
            chain.append(agent)
            current_id = agent.manager_id
            
            # Reached top (CEO)
            if current_id is None or current_id == chain[-1].employee_id:
                break
                
        return chain


# Global cache for Monte Carlo speedups
_cached_template_graph = None
_cached_agents_count = 0

def clear_graph_cache():
    global _cached_template_graph
    global _cached_agents_count
    _cached_template_graph = None
    _cached_agents_count = 0

def build_org_graph(agents: list[EmployeeAgent]) -> OrgGraph:
    """
    Retains original function signature for compatibility but returns an OrgGraph wrapper.
    Implements a caching mechanism so Monte Carlo is significantly faster.
    """
    global _cached_template_graph
    global _cached_agents_count
    
    # Use cached template if number of agents hasn't changed (typical across MC initialisations)
    if _cached_template_graph is not None and len(agents) == _cached_agents_count:
        return OrgGraph(agents=agents, template_graph=_cached_template_graph)
    
    # Otherwise build from scratch and cache the NetworkX graph as template
    org_graph = OrgGraph(agents=agents)
    _cached_template_graph = org_graph.G.copy()
    _cached_agents_count = len(agents)
    return org_graph


if __name__ == "__main__":
    from sqlmodel import Session, select
    from backend.database import engine
    from backend.models import Employee
    from backend.simulation.agent import EmployeeAgent

    with Session(engine) as session:
        employees = session.exec(select(Employee)).all()
    agents = [EmployeeAgent(emp) for emp in employees]
    G = build_org_graph(agents)
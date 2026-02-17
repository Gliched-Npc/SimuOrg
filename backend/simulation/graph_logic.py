import networkx as nx
import time
from typing import List, Dict, Optional
from backend.models import Employee

class OrgGraph:
    def __init__(self):
        # The Graph (Who reports to whom?)
        self.graph = nx.DiGraph()
        
        # The Lookup Table (O(1) speed for finding employee details)
        self.employee_map: Dict[int, Employee] = {}

    def build(self, employees: List[Employee]):
        """
        Converts a flat list of employees into a NetworkX Directional Graph.
        """
        print(f"🔄 Building Graph from {len(employees)} records...")
        start_time = time.time()
        
        self.graph.clear()
        self.employee_map.clear()
        
        # 1. Add Nodes & Build Lookup (O(N))
        for emp in employees:
            self.graph.add_node(emp.employee_id)
            self.employee_map[emp.employee_id] = emp
            
        # 2. Add Edges (Relationships) (O(N))
        # Edge Direction: Manager -> Employee (Influence flows down)
        edge_count = 0
        for emp in employees:
            if emp.manager_id and emp.manager_id in self.employee_map:
                self.graph.add_edge(emp.manager_id, emp.employee_id)
                edge_count += 1
        
        end_time = time.time()
        duration = end_time - start_time
        
        # This is the "Console Log" you wanted!
        print(f"✅ Graph built in {duration:.4f}s: {self.graph.number_of_nodes()} Nodes, {edge_count} Edges")

    def get_team(self, manager_id: int) -> List[Employee]:
        """
        Returns direct reports of a manager.
        NetworkX 'successors' is optimized for O(1) lookup.
        """
        if manager_id not in self.graph:
            return []
        
        # specific direct reports (Team)
        direct_reports_ids = list(self.graph.successors(manager_id))
        return [self.employee_map[e_id] for e_id in direct_reports_ids]

    def get_skip_level_reports(self, manager_id: int) -> List[Employee]:
        """
        Example of Graph Traversal: Get reports of reports.
        """
        if manager_id not in self.graph:
            return []
            
        team_ids = list(self.graph.successors(manager_id))
        skip_reports = []
        for member_id in team_ids:
            skip_reports.extend(list(self.graph.successors(member_id)))
            
        return [self.employee_map[e_id] for e_id in skip_reports]

    def print_subtree(self, manager_id: int, level: int = 0, max_depth: int = 3):
        """
        Prints a text-based tree structure starting from a specific manager.
        Limits depth to avoid spamming the console.
        """
        if level > max_depth:
            return

        # Get employee details
        emp = self.employee_map.get(manager_id)
        if not emp:
            return

        # Indentation for hierarchy visual
        indent = "  " * level
        icon = "👑" if level == 0 else "├─"
        
        print(f"{indent}{icon} {emp.job_role} (ID: {emp.employee_id})")
        
        # Recursively print children
        team = self.get_team(manager_id)
        for report in team:
            self.print_subtree(report.employee_id, level + 1, max_depth)    
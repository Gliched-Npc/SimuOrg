import random
from typing import List, Dict, Set
from backend.models import Employee
from backend.simulation.graph_logic import OrgGraph

class SimulationEngine:
    def __init__(self, employees: List[Employee]):
        # 1. Initialize the hierarchy (The Brain we just built)
        self.graph = OrgGraph()
        self.graph.build(employees)
        
        # 2. Store the current population for O(1) lookups
        self.population: Dict[int, Employee] = {e.employee_id: e for e in employees}
        
        # 3. Track leavers (Who has left the company?)
        self.leavers: Set[int] = set()

    def run_step(self, attrition_boost: float = 0.0):
        """
        Runs ONE month of simulation.
        attrition_boost: A global risk factor (e.g., 0.10 adds 10% risk to everyone).
        """
        new_leavers = []
        
        # Iterate through everyone still in the company
        for emp_id, emp in self.population.items():
            if emp_id in self.leavers:
                continue
            
            # --- THE RIPPLE LOGIC ---
            # Base probability (Baseline risk is 2%)
            prob = 0.02 
            
            # The Manager Impact: If my boss is in the 'leavers' set, my risk spikes
            if emp.manager_id and emp.manager_id in self.leavers:
                prob += 0.15  # 15% increase in attrition risk
                
            # Global factor (Market trends, bad news, etc.)
            prob += attrition_boost
            
            # MONTE CARLO: Roll the dice
            if random.random() < prob:
                new_leavers.append(emp_id)
        
        # Update the master list of leavers
        for leaver_id in new_leavers:
            self.leavers.add(leaver_id)
            
        return {
            "new_leavers": len(new_leavers),
            "total_leavers": len(self.leavers)
        }

    def get_summary(self):
        """Returns a snapshot of the current company state."""
        total = len(self.population)
        left = len(self.leavers)
        return {
            "total_employees": total,
            "retained": total - left,
            "attrition_rate": f"{(left / total) * 100:.2f}%"
        }
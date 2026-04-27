from backend.core.simulation.agent import EmployeeAgent
from backend.core.simulation.org_graph import build_org_graph


def test_build_org_graph():
    class MockEmployee:
        def __init__(self, emp_id, mgr_id=None):
            self.employee_id = emp_id
            self.manager_id = mgr_id
            self.department = "Engineering"
            self.job_role = "Dev"
            self.job_level = 2
            self.age = 30
            self.gender = "M"
            self.marital_status = "Single"
            self.distance_from_home = 5
            self.monthly_income = 5000
            self.percent_salary_hike = 10
            self.years_at_company = 2
            self.total_working_years = 5
            self.num_companies_worked = 1
            self.years_in_current_role = 2
            self.performance_rating = 3
            self.job_satisfaction = 3.0
            self.work_life_balance = 3.0
            self.environment_satisfaction = 3.0
            self.job_involvement = 3
            self.attrition = "No"
            self.years_since_last_promotion = 1
            self.years_with_curr_manager = 1
            self.stock_option_level = 1
            self.overtime = 0

    emp1 = EmployeeAgent(MockEmployee(1))
    emp2 = EmployeeAgent(MockEmployee(2, mgr_id=1))
    emp3 = EmployeeAgent(MockEmployee(3, mgr_id=1))

    G = build_org_graph([emp1, emp2, emp3])

    # Graph should have 3 nodes
    assert len(G.nodes) == 3

    # Manager should have edges to reports
    assert G.has_edge(2, 1)
    assert G.has_edge(3, 1)

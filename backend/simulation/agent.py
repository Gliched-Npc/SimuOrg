import pandas as pd
import joblib
from backend.ml.productivity_decay import productivity_decay
from backend.ml.burnout_estimator import burnout_threshold as burnout_fn

# Load frozen models once at startup
quit_model = joblib.load("backend/ml/exports/quit_probability.pkl")


class EmployeeAgent:
    def __init__(self, db_employee):
        self.employee_id         = db_employee.employee_id
        self.department          = db_employee.department
        self.job_role            = db_employee.job_role
        self.job_level           = db_employee.job_level
        self.manager_id          = db_employee.manager_id
        self.years_at_company    = db_employee.years_at_company
        self.total_working_years = db_employee.total_working_years
        self.monthly_income      = db_employee.monthly_income
        self.job_satisfaction    = db_employee.job_satisfaction
        self.work_life_balance   = db_employee.work_life_balance
        self.performance_rating  = db_employee.performance_rating

        self.stress       = 0.0
        self.fatigue      = 0.0
        self.motivation   = db_employee.job_satisfaction / 4.0
        self.loyalty      = min(db_employee.years_at_company / 10.0, 1.0)
        self.is_active    = True
        self.productivity = 1.0

        self.burnout_limit = burnout_fn(
            db_employee.job_level,
            db_employee.total_working_years
        )

    def get_quit_features(self):
        return pd.DataFrame([{
            "job_satisfaction":         self.job_satisfaction,
            "work_life_balance":        self.work_life_balance,
            "environment_satisfaction": self.motivation * 4.0,
            "job_involvement":          self.job_level,
            "monthly_income":           self.monthly_income,
            "years_at_company":         self.years_at_company,
            "total_working_years":      self.total_working_years,
            "num_companies_worked":     1.0,
            "job_level":                self.job_level,
        }])

    def update_productivity(self):
        self.productivity = productivity_decay(
            stress=self.stress,
            fatigue=self.fatigue,
            job_satisfaction=self.job_satisfaction,
            work_life_balance=self.work_life_balance
        )

    def __repr__(self):
        return (f"Agent({self.employee_id} | "
                f"Dept:{self.department} | "
                f"L{self.job_level} | "
                f"stress:{self.stress:.2f} | "
                f"productivity:{self.productivity:.2f})")
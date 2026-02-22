import pandas as pd
import joblib
import os
from backend.ml.productivity_decay import productivity_decay
from backend.ml.burnout_estimator import burnout_threshold as burnout_fn

# Load frozen models once at startup
_QUIT_MODEL_PATH = "backend/ml/exports/quit_probability.pkl"
if not os.path.exists(_QUIT_MODEL_PATH):
    raise FileNotFoundError(
        f"Quit model not found at {_QUIT_MODEL_PATH}. "
        "Run backend/ml/train.py first."
    )
_saved         = joblib.load(_QUIT_MODEL_PATH)
quit_model     = _saved["model"]
quit_threshold = _saved["threshold"]
quit_features  = _saved["features"]


class EmployeeAgent:
    def __init__(self, db_employee):
        self.employee_id            = db_employee.employee_id
        self.department             = db_employee.department
        self.job_role               = db_employee.job_role
        self.job_level              = db_employee.job_level
        self.manager_id             = db_employee.manager_id
        self.years_at_company       = db_employee.years_at_company
        self.total_working_years    = db_employee.total_working_years
        self.num_companies_worked   = db_employee.num_companies_worked  # fixed: use actual value
        self.monthly_income         = db_employee.monthly_income
        self.job_satisfaction       = db_employee.job_satisfaction
        self.work_life_balance      = db_employee.work_life_balance
        self.performance_rating     = db_employee.performance_rating
        self.years_since_last_promotion = db_employee.years_since_last_promotion
        self.years_with_curr_manager    = db_employee.years_with_curr_manager
        self.stock_option_level         = getattr(db_employee, 'stock_option_level', 0) or 0
        self.age                        = db_employee.age
        self.distance_from_home         = getattr(db_employee, 'distance_from_home', 0) or 0
        self.percent_salary_hike        = getattr(db_employee, 'percent_salary_hike', 0) or 0
        self.marital_status             = getattr(db_employee, 'marital_status', 'Unknown') or 'Unknown'

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
        df= pd.DataFrame([{
            "job_satisfaction":           self.job_satisfaction,
            "work_life_balance":          self.work_life_balance,
            "environment_satisfaction":   self.motivation * 4.0,
            "job_involvement":            self.job_level,
            "monthly_income":             self.monthly_income,
            "years_at_company":           self.years_at_company,
            "total_working_years":        self.total_working_years,
            "num_companies_worked":       self.num_companies_worked,  # fixed: use actual value
            "job_level":                  self.job_level,
            "years_since_last_promotion": self.years_since_last_promotion,
            "years_with_curr_manager":    self.years_with_curr_manager,
            "performance_rating":         self.performance_rating,
            "stock_option_level":         self.stock_option_level,
            "age":                        self.age,
            "distance_from_home":         self.distance_from_home,
            "percent_salary_hike":        self.percent_salary_hike,
            "marital_status":             self.marital_status,
        }])
        # Engineered features — must match attrition_model.py
        df['stagnation_score']      = df['years_since_last_promotion'] / (df['years_at_company'] + 1)
        df['satisfaction_composite'] = (df['job_satisfaction'] + df['work_life_balance'] + df['environment_satisfaction']) / 3
        df['career_velocity']       = df['job_level'] / (df['total_working_years'] + 1)
        df['loyalty_index']         = df['years_at_company'] / (df['total_working_years'] + 1)
        df['is_single']             = (df['marital_status'].str.lower() == 'single').astype(int)

        return df[quit_features]        

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
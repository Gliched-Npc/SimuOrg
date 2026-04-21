# backend/simulation/agent.py


import pandas as pd

from backend.core.ml.attrition_model import engineer_features
from backend.core.ml.burnout_estimator import burnout_threshold as burnout_fn
from backend.core.ml.productivity_decay import productivity_decay

# Lazy-loaded — model is loaded on first use, not at import time.
# This allows the server to start even if no model has been trained yet.
_quit_model_cache = None


def _get_quit_model():
    """Load (and cache) the quit model on first call."""
    global _quit_model_cache
    if _quit_model_cache is None:
        from backend.storage.storage import load_artifact

        _saved = load_artifact("quit_model")
        if not _saved:
            raise FileNotFoundError(
                "Quit model not found in DB. "
                "Please upload a dataset first via POST /api/upload/dataset."
            )

        # Reconstruct calibrated wrapper if calibrator is present (new format).
        # Falls back to raw model for backwards compatibility with old .pkl files.
        base_model = _saved["model"]
        calibrator = _saved.get("calibrator", None)

        if calibrator is not None:
            import numpy as np

            class _CalibratedModel:
                def __init__(self, base, cal):
                    self.base_model = base
                    self.calibrator = cal

                def predict_proba(self, X):
                    raw = self.base_model.predict_proba(X)[:, 1]
                    cal = self.calibrator.predict(raw)
                    return np.column_stack([1 - cal, cal])

            loaded_model = _CalibratedModel(base_model, calibrator)
        else:
            loaded_model = base_model  # backwards-compatible

        _quit_model_cache = {
            "model": loaded_model,
            "threshold": _saved["threshold"],
            "features": _saved["features"],
            "label_encoders": _saved.get("label_encoders", {}),
        }
    return _quit_model_cache


# Convenience aliases — resolved lazily on first simulation call
def _quit_model():
    return _get_quit_model()["model"]


def _quit_threshold():
    return _get_quit_model()["threshold"]


def _quit_features():
    return _get_quit_model()["features"]


def _quit_encoders():
    return _get_quit_model()["label_encoders"]


def clear_quit_model_cache():
    """Reset the cached quit model so the next call to _get_quit_model() re-reads from disk.
    Must be called after retraining/recalibration to prevent stale predictions."""
    global _quit_model_cache
    _quit_model_cache = None


class EmployeeAgent:
    def __init__(self, db_employee):
        self.employee_id = db_employee.employee_id
        self.department = db_employee.department
        self.job_role = db_employee.job_role
        self.job_level = db_employee.job_level
        self.manager_id = db_employee.manager_id
        self.years_at_company = db_employee.years_at_company
        self.total_working_years = db_employee.total_working_years
        self.num_companies_worked = db_employee.num_companies_worked
        self.monthly_income = db_employee.monthly_income
        self.job_satisfaction = db_employee.job_satisfaction
        self.work_life_balance = db_employee.work_life_balance
        self.environment_satisfaction = getattr(db_employee, "environment_satisfaction", 3.0) or 3.0
        self.job_involvement = getattr(db_employee, "job_involvement", 3.0) or 3.0
        self.performance_rating = db_employee.performance_rating
        self.years_since_last_promotion = db_employee.years_since_last_promotion
        self.years_with_curr_manager = db_employee.years_with_curr_manager
        self.stock_option_level = getattr(db_employee, "stock_option_level", 0) or 0
        self.age = db_employee.age
        self.distance_from_home = getattr(db_employee, "distance_from_home", 0) or 0
        self.percent_salary_hike = getattr(db_employee, "percent_salary_hike", 0) or 0
        self.marital_status = getattr(db_employee, "marital_status", "Unknown") or "Unknown"

        self.years_in_current_role = getattr(db_employee, "years_in_current_role", 0) or 0

        # Optional — only present if dataset had OverTime column
        self.overtime = getattr(db_employee, "overtime", 0) or 0

        # Simulation state
        self.baseline_satisfaction = db_employee.job_satisfaction
        self.baseline_wlb = db_employee.work_life_balance

        # Ambient initial stress — employees don't start at zero.
        # Years of work accumulate psychological load. Dissatisfied employees
        # carry more. Long-tenured employees have had more time to build it up.
        # Scale: satisfaction 1→ ~15% of threshold | satisfaction 4 → ~0%
        #        tenure 10+yr adds another 10% of threshold
        _sat_stress = max(0.0, (4.0 - db_employee.job_satisfaction) / 3.0) * 0.06
        _tenure_stress = min(db_employee.years_at_company / 10.0, 1.0) * 0.035
        self.stress = round(min(_sat_stress + _tenure_stress, 0.40), 4)

        self.fatigue = 0.0
        self.motivation = self.baseline_satisfaction / 4.0
        self.loyalty = min(db_employee.years_at_company / 10.0, 1.0)
        self.is_active = True
        self.productivity = 1.0

        self.burnout_limit = burnout_fn(db_employee.job_level, db_employee.total_working_years)

    def get_raw_quit_dict(self):
        """Build raw feature dict matching dataset columns."""
        return {
            "job_satisfaction": self.job_satisfaction,
            "work_life_balance": self.work_life_balance,
            "environment_satisfaction": self.environment_satisfaction,
            "job_involvement": self.job_involvement,
            "monthly_income": self.monthly_income,
            "years_at_company": self.years_at_company,
            "total_working_years": self.total_working_years,
            "num_companies_worked": self.num_companies_worked,
            "job_level": self.job_level,
            "years_since_last_promotion": self.years_since_last_promotion,
            "years_with_curr_manager": self.years_with_curr_manager,
            "performance_rating": self.performance_rating,
            "stock_option_level": self.stock_option_level,
            "age": self.age,
            "distance_from_home": self.distance_from_home,
            "percent_salary_hike": self.percent_salary_hike,
            "years_in_current_role": self.years_in_current_role,
            "overtime": self.overtime,
            "department": self.department,
            "job_role": self.job_role,
        }

    def get_quit_features(self):
        """
        Build feature dict matching exact features the model was trained on.
        Lazy-loads the model on first call via _quit_features().
        """
        raw = self.get_raw_quit_dict()
        df = pd.DataFrame([raw])
        df = engineer_features(df, encoders=_quit_encoders())
        return df[_quit_features()]

    def update_productivity(self, workload_multiplier: float = 1.0):
        self.productivity = productivity_decay(
            stress=self.stress,
            fatigue=self.fatigue,
            job_satisfaction=self.job_satisfaction,
            work_life_balance=self.work_life_balance,
            workload_multiplier=workload_multiplier,
        )

    @classmethod
    def from_template(cls, template_agent, new_id: int, rng):
        """
        Creates a new hire agent to replace a departed employee.
        Inherits role/department but resets tenure, stress, etc.
        """
        from backend.core.ml.burnout_estimator import burnout_threshold as burnout_fn

        # Create a blank instance bypassing __init__ (which expects an ORM model)
        new_agent = cls.__new__(cls)
        new_agent.employee_id = new_id
        new_agent.department = template_agent.department
        new_agent.job_role = template_agent.job_role
        new_agent.job_level = template_agent.job_level
        new_agent.manager_id = template_agent.manager_id
        new_agent.years_at_company = 0
        new_agent.total_working_years = 0
        new_agent.num_companies_worked = 1.0
        new_agent.monthly_income = template_agent.monthly_income
        new_agent.job_satisfaction = 3.0
        new_agent.work_life_balance = 3.0
        new_agent.environment_satisfaction = 3.0
        new_agent.baseline_satisfaction = 3.0
        new_agent.baseline_wlb = 3.0
        new_agent.job_involvement = 3
        new_agent.performance_rating = 3
        new_agent.stress = 0.1
        new_agent.fatigue = 0.0
        new_agent.motivation = 0.75
        new_agent.loyalty = 0.1
        new_agent.productivity = 1.0
        new_agent.is_active = True
        new_agent.burnout_limit = burnout_fn(template_agent.job_level, 0)
        new_agent.years_since_last_promotion = 0
        new_agent.years_with_curr_manager = 0
        new_agent.stock_option_level = 0
        new_agent.age = rng.integers(22, 36)
        new_agent.distance_from_home = template_agent.distance_from_home
        new_agent.percent_salary_hike = 15
        new_agent.overtime = template_agent.overtime
        new_agent.years_in_current_role = 0
        return new_agent

    def __repr__(self):
        return (
            f"Agent({self.employee_id} | "
            f"Dept:{self.department} | "
            f"L{self.job_level} | "
            f"stress:{self.stress:.2f} | "
            f"productivity:{self.productivity:.2f})"
        )

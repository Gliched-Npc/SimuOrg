#backend/models.py

from typing import Optional
from sqlmodel import SQLModel, Field
import uuid as _uuid
from datetime import datetime
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB


class Employee(SQLModel, table=True):
    # Identity
    employee_id: int = Field(primary_key=True)
    department: str = Field(default="General")
    job_role: str = Field(default="Unknown")
    job_level: int
    manager_id: Optional[int] = Field(default=None)
    simulation_id: str = Field(default="master", index=True)

    # Demographics
    age: int
    gender: str
    marital_status: Optional[str] = Field(default="Unknown")
    distance_from_home: Optional[int] = Field(default=0)

    # Financial
    monthly_income: int
    percent_salary_hike: Optional[int] = Field(default=0)

    # Experience
    years_at_company: int
    total_working_years: float
    num_companies_worked: float
    years_in_current_role: Optional[int] = Field(default=0)

    # Performance & Satisfaction (ML needs these)
    performance_rating: int
    job_satisfaction: float
    work_life_balance: float
    environment_satisfaction: float
    job_involvement: int
    attrition: Optional[str] =Field(default="No")          # "Yes" / "No"  ← ML target

    # Promotion & Manager history
    years_since_last_promotion: Optional[int] = Field(default=0)
    years_with_curr_manager: Optional[int] = Field(default=0)
    stock_option_level:int = Field(default=0)
    overtime: Optional[int] = Field(default=0)
    

    class Config:
        populate_by_name = True

class SimulationJob(SQLModel, table=True):
    __tablename__ = "simulation_job"

    job_id:      str = Field(default_factory=lambda: str(_uuid.uuid4()), primary_key=True)
    job_type:    str = Field(default="simulation")  # "simulation" | "training"
    status:      str = Field(default="queued")       # queued → running → completed → failed
    policy_name: Optional[str] = Field(default=None)
    runs:        Optional[int] = Field(default=None)
    duration_months: Optional[int] = Field(default=None)
    created_at:  datetime = Field(default_factory=datetime.utcnow)
    updated_at:  datetime = Field(default_factory=datetime.utcnow)
    error:       Optional[str] = Field(default=None)
    result:      Optional[str] = Field(default=None)  # JSON string
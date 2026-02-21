from typing import Optional
from sqlmodel import SQLModel, Field

class Employee(SQLModel, table=True):
    # Identity
    employee_id: int = Field(primary_key=True)
    department: str
    job_role: str
    job_level: int
    manager_id: Optional[int] = Field(default=None)
    simulation_id: str = Field(default="master", index=True)

    # Demographics
    age: int
    gender: str

    # Financial
    monthly_income: int

    # Experience
    years_at_company: int
    total_working_years: float
    num_companies_worked: float

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
    
    class Config:
        populate_by_name = True
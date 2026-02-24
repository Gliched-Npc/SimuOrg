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
    business_travel: Optional[int] = Field(default=0)
    
    class Config:
        populate_by_name = True
from typing import Optional
from sqlmodel import SQLModel, Field

class Employee(SQLModel, table=True):
    employee_id: int = Field(primary_key=True)
    department: str
    job_role: str
    job_level: int
    manager_id: Optional[int] = Field(default=None)
    
    # Critical Data
    age: int = Field(alias="Age")
    gender: str = Field(alias="Gender")
    monthly_income: int = Field(alias="MonthlyIncome")
    performance_rating: int = Field(alias="PerformanceRating")
    years_at_company: int = Field(alias="YearsAtCompany")
    
    simulation_id: str = Field(default="master", index=True) 
    
    class Config:
        populate_by_name = True
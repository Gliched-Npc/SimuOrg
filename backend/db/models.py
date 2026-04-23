# backend/models.py

import uuid as _uuid
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def get_utc_now():
    return datetime.now(timezone.utc)


class Employee(SQLModel, table=True):
    # Identity
    employee_id: int = Field(primary_key=True)
    department: str = Field(default="General")
    job_role: str = Field(default="Unknown")
    job_level: int
    manager_id: int | None = Field(default=None)
    simulation_id: str = Field(default="master", index=True)
    session_id: str = Field(default="global", index=True)

    # Demographics
    age: int
    gender: str
    marital_status: str | None = Field(default="Unknown")
    distance_from_home: int | None = Field(default=0)

    # Financial
    monthly_income: int
    percent_salary_hike: int | None = Field(default=0)

    # Experience
    years_at_company: int
    total_working_years: float
    num_companies_worked: float
    years_in_current_role: int | None = Field(default=0)

    # Performance & Satisfaction (ML needs these)
    performance_rating: int
    job_satisfaction: float
    work_life_balance: float
    environment_satisfaction: float
    job_involvement: int
    attrition: str | None = Field(default="No")  # "Yes" / "No"  ← ML target

    # Promotion & Manager history
    years_since_last_promotion: int | None = Field(default=0)
    years_with_curr_manager: int | None = Field(default=0)
    stock_option_level: int = Field(default=0)
    overtime: int | None = Field(default=0)

    model_config = {"populate_by_name": True}


class SimulationJob(SQLModel, table=True):
    __tablename__ = "simulation_job"

    job_id: str = Field(default_factory=lambda: str(_uuid.uuid4()), primary_key=True)
    job_type: str = Field(default="simulation")  # "simulation" | "training"
    status: str = Field(default="queued")  # queued → running → completed → failed
    policy_name: str | None = Field(default=None)
    runs: int | None = Field(default=None)
    duration_months: int | None = Field(default=None)
    seed: int | None = Field(default=None)
    created_at: datetime = Field(default_factory=get_utc_now)
    updated_at: datetime = Field(default_factory=get_utc_now)
    data_issues: str | None = Field(default=None)
    error: str | None = Field(default=None)
    result: str | None = Field(default=None)  # JSON string
    policy_config: str | None = Field(default=None)  # JSON of exact SimulationConfig used
    policy_log_id: str | None = Field(default=None)  # Link to PolicyGenerationLog (if custom)
    executive_summary: str | None = Field(default=None)  # CEO reasoning output (future)
    session_id: str = Field(default="global", index=True)


class MLArtifact(SQLModel, table=True):
    """Stores ML model artifacts and calibration data so they survive server restarts."""

    __tablename__ = "ml_artifact"

    name: str = Field(primary_key=True)  # "quit_model" | "burnout" | "calibration" | "quality"
    session_id: str = Field(default="global", primary_key=True)
    artifact_type: str = Field(default="json")  # "pkl" | "json"
    data: str = Field()  # base64 str for pkl, raw JSON str for json
    updated_at: datetime = Field(default_factory=get_utc_now)


class PolicyGenerationLog(SQLModel, table=True):
    """Logs every LLM-generated policy so configs are traceable and not lost between requests."""

    __tablename__ = "policy_generation_log"

    log_id: str = Field(default_factory=lambda: str(_uuid.uuid4()), primary_key=True)
    user_prompt: str = Field()  # raw CEO input text
    generated_config: str = Field()  # JSON of SimulationConfig
    justification: str = Field(default="{}")  # JSON of LLM justification
    created_at: datetime = Field(default_factory=get_utc_now)
    session_id: str = Field(default="global", index=True)


class OrchestrateJob(SQLModel, table=True):
    """Tracks a full orchestration pipeline run (intent → sim → reasoning) as an async job."""

    __tablename__ = "orchestrate_job"

    job_id: str = Field(default_factory=lambda: str(_uuid.uuid4()), primary_key=True)
    status: str = Field(default="queued")  # queued → running → completed → failed
    user_text: str = Field()  # original CEO input
    result: str | None = Field(default=None)  # full JSON payload when done
    error: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=get_utc_now)
    updated_at: datetime = Field(default_factory=get_utc_now)
    session_id: str = Field(default="global", index=True)

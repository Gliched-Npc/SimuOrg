import pytest
from sqlmodel import Session, SQLModel, create_engine

from backend.db.models import Employee, PolicyGenerationLog, SimulationJob


@pytest.fixture(name="db_session")
def session_fixture():
    # We use an explicit in-memory SQLite database for DB tests
    # This purposefully bypasses the global 'engine=None' in conftest.py
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_create_and_retrieve_employee(db_session):
    emp = Employee(
        employee_id=101,
        job_level=3,
        age=35,
        gender="Female",
        monthly_income=8500,
        years_at_company=4,
        total_working_years=10,
        num_companies_worked=3,
        performance_rating=4,
        job_satisfaction=4,
        work_life_balance=2,
        environment_satisfaction=4,
        job_involvement=3,
        attrition="No",
    )
    db_session.add(emp)
    db_session.commit()

    saved_emp = db_session.get(Employee, 101)
    assert saved_emp is not None
    assert saved_emp.monthly_income == 8500
    assert saved_emp.attrition == "No"
    assert saved_emp.department == "General"  # From default Field


def test_create_and_retrieve_simulation_job(db_session):
    job = SimulationJob(policy_name="baseline", runs=10, duration_months=12)
    db_session.add(job)
    db_session.commit()

    assert job.job_id is not None  # Auto-generated UUID
    assert job.status == "queued"  # Default status

    saved_job = db_session.get(SimulationJob, job.job_id)
    assert saved_job.policy_name == "baseline"
    assert saved_job.runs == 10


def test_policy_generation_log_defaults(db_session):
    log = PolicyGenerationLog(user_prompt="Make everyone happy", generated_config="{}")
    db_session.add(log)
    db_session.commit()

    assert log.log_id is not None
    assert log.justification == "{}"  # Default value

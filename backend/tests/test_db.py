from sqlmodel import Session, select

from backend.db.database import engine
from backend.db.models import Employee, SimulationJob


def test_create_and_read_employee():
    with Session(engine) as session:
        # Create
        emp = Employee(
            employee_id=9999,
            job_level=2,
            age=30,
            gender="Male",
            monthly_income=5000,
            years_at_company=2,
            total_working_years=5,
            num_companies_worked=2,
            performance_rating=3,
            job_satisfaction=3.0,
            work_life_balance=3.0,
            environment_satisfaction=3.0,
            job_involvement=3,
            session_id="test_db",
        )
        session.add(emp)
        session.commit()

        # Read
        fetched = session.exec(
            select(Employee).where(Employee.employee_id == 9999, Employee.session_id == "test_db")
        ).first()
        assert fetched is not None
        assert fetched.monthly_income == 5000

        # Cleanup
        session.delete(fetched)
        session.commit()


def test_create_simulation_job():
    with Session(engine) as session:
        job = SimulationJob(
            job_type="simulation",
            status="queued",
            policy_name="test_policy",
            runs=1,
            duration_months=1,
            session_id="test_db",
        )
        session.add(job)
        session.commit()

        assert job.job_id is not None

        # Cleanup
        session.delete(job)
        session.commit()

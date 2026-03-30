# backend/workers/tasks.py
# Placeholder — Celery task definitions will go here.
# backend/workers/tasks.py

import json
from datetime import datetime
from backend.workers.celery_app import celery_app
from backend.services.simulation_service import (
    run_simulation_job,
    compare_simulation_jobs,
    run_training_job,
)


def _update_job(job_id: str, status: str, result: dict = None, error: str = None):
    """Update job status in DB."""
    from sqlmodel import Session
    from backend.db.database import engine
    from backend.db.models import SimulationJob

    with Session(engine) as session:
        job = session.get(SimulationJob, job_id)
        if job:
            job.status     = status
            job.updated_at = datetime.utcnow()
            if result:
                job.result = json.dumps(result)
            if error:
                job.error = error
            session.add(job)
            session.commit()


@celery_app.task(bind=True, name="tasks.run_simulation")
def run_simulation_task(self, job_id: str, policy_name: str, runs: int, duration_months: int, seed: int = 42):
    _update_job(job_id, "running")
    try:
        result = run_simulation_job(policy_name, runs, duration_months, seed)
        _update_job(job_id, "completed", result=result)
        return result
    except Exception as e:
        _update_job(job_id, "failed", error=str(e))
        raise


@celery_app.task(bind=True, name="tasks.run_training")
def run_training_task(self, job_id: str, quality_report: dict = None):
    _update_job(job_id, "running")
    try:
        result = run_training_job(quality_report)
        _update_job(job_id, "completed", result=result)
        return result
    except Exception as e:
        _update_job(job_id, "failed", error=str(e))
        raise


@celery_app.task(bind=True, name="tasks.compare_simulations")
def compare_simulations_task(self, job_id: str, policy_a: str, policy_b: str, runs: int, duration_months: int, seed: int = 42):
    _update_job(job_id, "running")
    try:
        result = compare_simulation_jobs(policy_a, policy_b, runs, duration_months, seed)
        _update_job(job_id, "completed", result=result)
        return result
    except Exception as e:
        _update_job(job_id, "failed", error=str(e))
        raise
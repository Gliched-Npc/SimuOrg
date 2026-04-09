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
from sqlmodel import Session
from backend.db.database import engine
from backend.db.models import SimulationJob


def _update_job(job_id: str, status: str, result: dict = None, error: str = None, executive_summary: str = None):
    """Update job status in DB."""
    with Session(engine) as session:
        job = session.get(SimulationJob, job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found in database.")
            
        job.status     = status
        job.updated_at = datetime.utcnow()
        if result:
            job.result = json.dumps(result)
        if error:
            job.error = error
        if executive_summary:
            job.executive_summary = executive_summary
        
        session.add(job)
        session.commit()


@celery_app.task(bind=True, name="tasks.run_simulation")
def run_simulation_task(self, job_id: str, policy_name: str, runs: int, duration_months: int | None, seed: int = 42, policy_config: dict | None = None):
    _update_job(job_id, "running")
    try:
        result = run_simulation_job(policy_name, runs, duration_months, seed, policy_config=policy_config)
        
        # ────────────────────────────────────────────────────────────
        # Trigger the CEO Reasoning Chain automatically after math!
        # ────────────────────────────────────────────────────────────
        from backend.core.llm.reasoning_chain import run_reasoning_chain
        
        # Best effort LLM completion
        executive_summary = None
        try:
            reasoning_out = run_reasoning_chain(sim_result=result, policy_config=policy_config)
            # Dump the briefing sub-object directly as a JSON string to keep the DB clean
            if "briefing" in reasoning_out:
                executive_summary = json.dumps(reasoning_out["briefing"])
            elif "error" in reasoning_out:
                print(f"[LLM worker error] {reasoning_out['error']}")
        except Exception as chain_e:
            print(f"[LLM worker exception] {chain_e}")
            
        _update_job(job_id, "completed", result=result, executive_summary=executive_summary)
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
def compare_simulations_task(self, job_id: str, policy_a: str, policy_b: str, runs: int, duration_months: int | None, seed: int = 42):
    _update_job(job_id, "running")
    try:
        result = compare_simulation_jobs(policy_a, policy_b, runs, duration_months, seed)
        _update_job(job_id, "completed", result=result)
        return result
    except Exception as e:
        _update_job(job_id, "failed", error=str(e))
        raise
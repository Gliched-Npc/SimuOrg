# backend/workers/tasks.py

import json
from datetime import datetime, timezone

from sqlmodel import Session

from backend.db.database import engine
from backend.db.models import OrchestrateJob, SimulationJob
from backend.services.simulation_service import (
    compare_simulation_jobs,
    run_simulation_job,
    run_training_job,
)


def _update_job(
    job_id: str, status: str, result: dict = None, error: str = None, executive_summary: str = None
):
    """Update job status in DB."""
    with Session(engine) as session:
        job = session.get(SimulationJob, job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found in database.")

        job.status = status
        job.updated_at = datetime.now(timezone.utc)
        if result:
            job.result = json.dumps(result)
        if error:
            job.error = error
        if executive_summary:
            job.executive_summary = executive_summary

        session.add(job)
        session.commit()


def run_simulation_task(
    job_id: str,
    policy_name: str,
    runs: int,
    duration_months: int | None,
    seed: int = 42,
    policy_config: dict | None = None,
    session_id: str = "global",
):
    _update_job(job_id, "running")
    try:
        result = run_simulation_job(
            policy_name,
            runs,
            duration_months,
            seed,
            policy_config=policy_config,
            session_id=session_id,
        )

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


def run_training_task(job_id: str, quality_report: dict = None, session_id: str = "global"):
    _update_job(job_id, "running")
    try:
        result = run_training_job(quality_report, session_id=session_id)
        _update_job(job_id, "completed", result=result)
        return result
    except Exception as e:
        _update_job(job_id, "failed", error=str(e))
        raise


def compare_simulations_task(
    job_id: str,
    policy_a: str,
    policy_b: str,
    runs: int,
    duration_months: int | None,
    seed: int = 42,
    session_id: str = "global",
):
    _update_job(job_id, "running")
    try:
        result = compare_simulation_jobs(
            policy_a, policy_b, runs, duration_months, seed, session_id=session_id
        )
        _update_job(job_id, "completed", result=result)
        return result
    except Exception as e:
        _update_job(job_id, "failed", error=str(e))
        raise


def orchestrate_task(job_id: str, user_text: str, session_id: str = "global"):
    """
    Runs the full 3-agent orchestration pipeline in a background task:
      Agent 1 — Intent routing + parameter extraction
      Agent 2 — Monte Carlo simulation + reasoning chain
    Writes result to OrchestrateJob so the frontend can poll /orchestrate/status/{job_id}.
    """
    from datetime import datetime

    from backend.services.orchestrator import orchestrate_user_request

    def _set(status: str, result: dict = None, error: str = None):
        with Session(engine) as session:
            job = session.get(OrchestrateJob, job_id)
            if not job:
                return
            job.status = status
            job.updated_at = datetime.now(timezone.utc)
            if result is not None:
                job.result = json.dumps(result)
            if error is not None:
                job.error = error
            session.add(job)
            session.commit()

    _set("running")
    try:
        result = orchestrate_user_request(user_text, session_id=session_id)
        _set("completed", result=result)
        return result
    except Exception as e:
        _set("failed", error=str(e))
        raise

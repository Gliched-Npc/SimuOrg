# backend/api/llm_routes.py

import json
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from backend.api.deps import get_session_id
from backend.core.llm.context_builder import build_context
from backend.core.llm.intent_parser import build_config_from_llm_output, translate_policy
from backend.db.database import engine
from backend.db.models import OrchestrateJob, PolicyGenerationLog

router = APIRouter(prefix="/api/llm", tags=["LLM Services"])


# ── Policy Generation ──────────────────────────────────────────────────────────


class PolicyRequest(BaseModel):
    description: str


@router.post("/generate")
def generate_policy(
    request: PolicyRequest,
    session_id: str = Depends(get_session_id),
):
    """
    Translates a natural language policy description into a validated SimulationConfig.
    Logs the generation to the DB and returns a log_id the frontend must pass
    when calling POST /api/sim/run with policy_name="custom".
    """
    try:
        # 1. Load calibration data — strictly from DB (no local fallback)
        from backend.storage.storage import load_artifact

        calib_data = load_artifact("calibration", session_id=session_id) or {}

        # 2. Build context out of safe calibration anchors
        context = build_context(calib_data)

        # 3. Translate via multi-stage LLM (Groq → local Ollama fallback)
        raw_llm_json = translate_policy(request.description, context)

        # 4. Build config and clamp according to bounds
        config, justification = build_config_from_llm_output(
            raw_llm_json, calib_data, request.description
        )

        # 5. Log to DB — replaces the shared custom_policy.json disk file
        with Session(engine) as session:
            log = PolicyGenerationLog(
                user_prompt=request.description,
                generated_config=json.dumps(config.__dict__),
                justification=json.dumps(justification),
                session_id=session_id,
            )
            session.add(log)
            session.commit()
            session.refresh(log)
            log_id = log.log_id

        # 6. Return structured payload for the UI confirmation screen.
        #    log_id must be passed as policy_log_id when calling POST /api/sim/run.
        return {
            "log_id": log_id,
            "config": config.__dict__,
            "justification": justification,
            "confidence": calib_data.get("calib_quality", "unknown"),
            "calib_attrition_std": calib_data.get("calib_attrition_std", 0.0),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Orchestration (Async via Celery) ──────────────────────────────────────────


class OrchestrateRequest(BaseModel):
    user_text: str


@router.post("/orchestrate")
def orchestrate_endpoint(
    request: OrchestrateRequest,
    background_tasks: BackgroundTasks,
    session_id: str = Depends(get_session_id),
):
    """
    Kicks off the full 3-agent orchestration pipeline as an async Celery task.
    Returns a job_id immediately — the frontend must poll /orchestrate/status/{job_id}.

    Flow:
      1. Creates an OrchestrateJob record in DB (status=queued)
      2. Fires orchestrate_task.delay() to Celery worker
      3. Returns {job_id} so the frontend can start polling
    """
    from backend.storage.storage import load_artifact
    from backend.workers.tasks import orchestrate_task

    quality = load_artifact("quality", session_id=session_id)
    if quality and not quality.get("simulation_reliable", True):
        raise HTTPException(
            status_code=403,
            detail=(
                "Orchestration Denied: Your ML model is mathematically unreliable for projections "
                "(AUC < 0.65). This usually means your attrition data is too small or lacks meaningful patterns. "
                "Please review the Model Quality Report in the Upload dashboard and provide a stronger dataset."
            ),
        )

    with Session(engine) as session:
        job = OrchestrateJob(
            user_text=request.user_text,
            session_id=session_id,
        )
        session.add(job)
        session.commit()
        session.refresh(job)
        job_id = job.job_id

    background_tasks.add_task(orchestrate_task, job_id, request.user_text, session_id)

    return {"job_id": job_id, "status": "queued"}


@router.get("/orchestrate/status/{job_id}")
def orchestrate_status(job_id: str, session_id: str = Depends(get_session_id)):
    """
    Poll this until status == 'completed' or 'failed'.
    On completion, 'result' contains the full simulation + briefing payload.
    """
    with Session(engine) as session:
        job = session.get(OrchestrateJob, job_id)

    if job is None:
        raise HTTPException(status_code=404, detail=f"Orchestration job {job_id} not found.")

    # Bug #3 fix: prevent cross-user result leakage via guessed job UUIDs
    if job.session_id != session_id:
        raise HTTPException(status_code=403, detail="Access denied.")

    response = {
        "job_id": job.job_id,
        "status": job.status,
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat(),
    }

    if job.status == "completed" and job.result:
        response["result"] = json.loads(job.result)
    elif job.status == "failed":
        response["error"] = job.error

    return response


# ── Policy Config Retrieval ────────────────────────────────────────────────────


@router.get("/policy/{log_id}")
def get_policy_log(log_id: str, session_id: str = Depends(get_session_id)):
    """Retrieve a previously generated policy config by its log_id."""
    with Session(engine) as session:
        log = session.get(PolicyGenerationLog, log_id)
    # Bug #4 fix: only return log if it belongs to the caller's session
    if log is None or log.session_id != session_id:
        raise HTTPException(status_code=404, detail=f"Policy log {log_id} not found.")
    return {
        "log_id": log.log_id,
        "user_prompt": log.user_prompt,
        "generated_config": json.loads(log.generated_config),
        "justification": json.loads(log.justification),
        "created_at": log.created_at.isoformat(),
    }


# ── CEO Reasoning Chain (standalone, for already-completed sim jobs) ───────────


class ExplainRequest(BaseModel):
    job_id: str


@router.post("/explain")
def explain_simulation(request: ExplainRequest):
    """
    Runs chain-of-thought reasoning over a completed simulation job
    and returns a structured CEO executive briefing.
    Result is cached in simulation_job.executive_summary.
    """
    from backend.core.llm.reasoning_chain import run_reasoning_chain
    from backend.db.models import SimulationJob

    with Session(engine) as session:
        job = session.get(SimulationJob, request.job_id)

    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {request.job_id} not found.")

    if job.status != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Simulation is not complete yet (status: {job.status}). "
            "Wait for the job to finish before requesting an explanation.",
        )

    # Return cached summary if already generated (avoid re-calling LLM)
    if job.executive_summary:
        return {
            "job_id": request.job_id,
            "cached": True,
            "briefing": json.loads(job.executive_summary),
        }

    if not job.result:
        raise HTTPException(status_code=400, detail="Simulation result data is missing.")

    sim_result = json.loads(job.result)
    policy_config = json.loads(job.policy_config) if job.policy_config else None
    user_intent = None

    if job.policy_log_id:
        with Session(engine) as session:
            log = session.get(PolicyGenerationLog, job.policy_log_id)
            if log:
                user_intent = log.user_prompt

    try:
        briefing = run_reasoning_chain(sim_result, policy_config, user_intent)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reasoning chain failed: {str(e)}")

    with Session(engine) as session:
        job = session.get(SimulationJob, request.job_id)
        if job:
            job.executive_summary = json.dumps(briefing)
            job.updated_at = datetime.now(timezone.utc)
            session.add(job)
            session.commit()

    return {
        "job_id": request.job_id,
        "cached": False,
        "briefing": briefing,
    }

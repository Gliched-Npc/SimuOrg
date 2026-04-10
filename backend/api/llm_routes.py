# backend/api/llm_routes.py

import json
import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from backend.core.llm.context_builder import build_context
from backend.core.llm.intent_parser import translate_policy, build_config_from_llm_output
from backend.db.database import engine
from backend.db.models import PolicyGenerationLog
from datetime import datetime, timezone

from backend.services.orchestrator import orchestrate_user_request

router = APIRouter(prefix="/api/llm", tags=["LLM Services"])


class PolicyRequest(BaseModel):
    description: str


@router.post("/generate")
def generate_policy(request: PolicyRequest):
    """
    Translates a natural language policy description into a validated SimulationConfig.
    Logs the generation to the DB and returns a log_id the frontend must pass
    when calling POST /api/sim/run with policy_name="custom".
    """
    try:
        # 1. Load calibration data — prefer disk cache, fall back to DB
        calib_path = "backend/core/ml/exports/calibration.json"
        calib_data = {}
        if os.path.exists(calib_path):
            with open(calib_path, "r") as f:
                calib_data = json.load(f)
        else:
            from backend.storage.storage import load_artifact
            calib_data = load_artifact("calibration") or {}

        # 2. Build context out of safe calibration anchors
        context = build_context(calib_data)

        # 3. Translate via multi-stage LLM (Groq → local Ollama fallback)
        raw_llm_json = translate_policy(request.description, context)

        # 4. Build config and clamp according to bounds
        config, justification = build_config_from_llm_output(raw_llm_json, calib_data, request.description)

        # 5. Log to DB — replaces the shared custom_policy.json disk file
        with Session(engine) as session:
            log = PolicyGenerationLog(
                user_prompt=request.description,
                generated_config=json.dumps(config.__dict__),
                justification=json.dumps(justification),
            )
            session.add(log)
            session.commit()
            session.refresh(log)
            log_id = log.log_id

        # 6. Return structured payload for the UI confirmation screen.
        #    log_id must be passed as policy_log_id when calling POST /api/sim/run.
        return {
            "log_id":               log_id,
            "config":               config.__dict__,
            "justification":        justification,
            "confidence":           calib_data.get("calib_quality", "unknown"),
            "calib_attrition_std":  calib_data.get("calib_attrition_std", 0.0),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class OrchestrateRequest(BaseModel):
    user_text: str

@router.post("/orchestrate")
def orchestrate_endpoint(request: OrchestrateRequest):
    """
    Executes the full 3-Agent orchestration pipeline end-to-end:
    - Parses intent & extracts parameters via RAG
    - Runs the Monte Carlo simulation
    - Triggers the Reasoning Chain for executive briefing
    Returns a complete, massive JSON payload to front end.
    """
    try:
        return orchestrate_user_request(request.user_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/policy/{log_id}")
def get_policy_log(log_id: str):
    """Retrieve a previously generated policy config by its log_id."""
    with Session(engine) as session:
        log = session.get(PolicyGenerationLog, log_id)
    if log is None:
        raise HTTPException(status_code=404, detail=f"Policy log {log_id} not found.")
    return {
        "log_id":           log.log_id,
        "user_prompt":      log.user_prompt,
        "generated_config": json.loads(log.generated_config),
        "justification":    json.loads(log.justification),
        "created_at":       log.created_at.isoformat(),
    }


# ── CEO Reasoning Chain ────────────────────────────────────────────────────────

class ExplainRequest(BaseModel):
    job_id: str


@router.post("/explain")
def explain_simulation(request: ExplainRequest):
    """
    Runs a 4-step chain-of-thought reasoning over a completed simulation result
    and returns a structured CEO executive briefing.

    Steps:
      1. Interpret  — what happened and why?
      2. Compare    — better or worse than historical baseline?
      3. Risks      — top 3 risks
      4. Recommend  — concrete CEO actions

    The result is stored in simulation_job.executive_summary so it never needs
    to be regenerated for the same job.
    """
    from datetime import datetime
    from backend.db.models import SimulationJob
    from backend.core.llm.reasoning_chain import run_reasoning_chain

    # 1. Load the simulation job
    with Session(engine) as session:
        job = session.get(SimulationJob, request.job_id)

    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {request.job_id} not found.")

    if job.status != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Simulation is not complete yet (status: {job.status}). "
                   "Wait for the job to finish before requesting an explanation."
        )

    # 2. Return cached summary if already generated (avoid re-calling LLM)
    if job.executive_summary:
        return {
            "job_id":   request.job_id,
            "cached":   True,
            "briefing": json.loads(job.executive_summary),
        }

    # 3. Parse result and policy config
    if not job.result:
        raise HTTPException(status_code=400, detail="Simulation result data is missing.")

    sim_result    = json.loads(job.result)
    policy_config = json.loads(job.policy_config) if job.policy_config else None
    user_intent   = None

    # 3.5 Fetch original user intent if this was a custom policy run
    if job.policy_log_id:
        with Session(engine) as session:
            from backend.db.models import PolicyGenerationLog
            log = session.get(PolicyGenerationLog, job.policy_log_id)
            if log:
                user_intent = log.user_prompt

    # 4. Run the reasoning chain with full context
    try:
        briefing = run_reasoning_chain(sim_result, policy_config, user_intent)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reasoning chain failed: {str(e)}")

    # 5. Persist the briefing so it's never regenerated for this job
    with Session(engine) as session:
        job = session.get(SimulationJob, request.job_id)
        if job:
            job.executive_summary = json.dumps(briefing)
            job.updated_at        = datetime.now(timezone.utc)
            session.add(job)
            session.commit()

    return {
        "job_id":   request.job_id,
        "cached":   False,
        "briefing": briefing,
    }

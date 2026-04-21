# backend/api/sim_routes.py

import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from backend.core.simulation.policies import POLICIES

router = APIRouter(prefix="/api/sim", tags=["Simulation"])


class SimulationRequest(BaseModel):
    policy_name: str = "baseline"
    runs: int = Field(default=10, ge=1, le=50)
    duration_months: int | None = Field(default=None, ge=1, le=24)
    seed: int | None = Field(default=42, ge=0)
    policy_log_id: str | None = Field(default=None)  # required when policy_name="custom"


class CompareRequest(BaseModel):
    policy_a: str = "baseline"
    policy_b: str = "kpi_pressure"
    runs: int = Field(default=10, ge=1, le=50)
    duration_months: int | None = Field(default=None, ge=1, le=24)
    seed: int | None = Field(default=42, ge=0)


@router.get("/policies")
def list_policies():
    return {"policies": list(POLICIES.keys())}


@router.get("/test-data")
def get_test_data():
    """
    Return all employees with simulation_id='master' as a JSON array.
    Used by the Dashboard and Analytics pages for workforce visualisations.
    """
    from sqlmodel import Session, select

    from backend.db.database import engine
    from backend.db.models import Employee

    with Session(engine) as session:
        employees = session.exec(select(Employee).where(Employee.simulation_id == "master")).all()

    return [e.model_dump() for e in employees]


@router.post("/run")
async def run_simulation_endpoint(request: SimulationRequest, background_tasks: BackgroundTasks):
    import json

    from sqlmodel import Session, select

    from backend.db.database import engine
    from backend.db.models import Employee, PolicyGenerationLog, SimulationJob
    from backend.storage.storage import load_artifact
    from backend.workers.tasks import run_simulation_task

    if not load_artifact("quit_model"):
        raise HTTPException(status_code=400, detail="No trained model found.")

    quality = load_artifact("quality")
    if quality and not quality.get("simulation_reliable", True):
        raise HTTPException(
            status_code=403,
            detail=(
                "Simulation Denied: Your ML model is mathematically unreliable for projections "
                "(AUC < 0.65). This usually means your attrition data is too small or lacks meaningful patterns. "
                "Please review the Model Quality Report in the Upload dashboard and provide a stronger dataset."
            ),
        )

    with Session(engine) as session:
        if not session.exec(select(Employee)).all():
            raise HTTPException(status_code=400, detail="No employee data in database.")

    if request.policy_name != "custom" and request.policy_name not in POLICIES:
        raise HTTPException(status_code=400, detail=f"Unknown policy: {request.policy_name}")

    # Resolve custom policy config from DB
    resolved_policy_config: dict | None = None
    if request.policy_name == "custom":
        if not request.policy_log_id:
            raise HTTPException(
                status_code=400,
                detail="policy_log_id is required when policy_name is 'custom'. "
                "Generate a policy first via POST /api/llm/generate.",
            )
        with Session(engine) as session:
            log = session.get(PolicyGenerationLog, request.policy_log_id)
        if log is None:
            raise HTTPException(
                status_code=404, detail=f"policy_log_id '{request.policy_log_id}' not found."
            )
        resolved_policy_config = json.loads(log.generated_config)

    job_id = str(uuid.uuid4())
    with Session(engine) as session:
        session.add(
            SimulationJob(
                job_id=job_id,
                job_type="simulation",
                status="queued",
                policy_name=request.policy_name,
                runs=request.runs,
                duration_months=request.duration_months,
                seed=request.seed,
                policy_config=json.dumps(resolved_policy_config)
                if resolved_policy_config
                else None,
                policy_log_id=request.policy_log_id,
            )
        )
        session.commit()

    background_tasks.add_task(
        run_simulation_task,
        job_id,
        request.policy_name,
        request.runs,
        request.duration_months,
        request.seed,
        resolved_policy_config,
    )

    return {
        "job_id": job_id,
        "poll_url": f"/api/sim/status/{job_id}",
        "status": "queued",
        "message": "Simulation queued. Poll poll_url for status.",
    }


@router.get("/status/{job_id}")
def get_simulation_status(job_id: str):
    import json

    from sqlmodel import Session

    from backend.db.database import engine
    from backend.db.models import SimulationJob

    with Session(engine) as session:
        job = session.get(SimulationJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    result = json.loads(job.result) if job.result else None
    return {
        "job_id": job_id,
        "status": job.status,
        "error": job.error,
        "result": result,
    }


@router.post("/compare")
async def compare_policies(request: CompareRequest, background_tasks: BackgroundTasks):
    from sqlmodel import Session

    from backend.db.database import engine
    from backend.db.models import SimulationJob
    from backend.workers.tasks import compare_simulations_task

    if request.policy_a != "custom" and request.policy_a not in POLICIES:
        raise HTTPException(status_code=400, detail=f"Unknown policy: {request.policy_a}")
    if request.policy_b != "custom" and request.policy_b not in POLICIES:
        raise HTTPException(status_code=400, detail=f"Unknown policy: {request.policy_b}")

    from backend.storage.storage import load_artifact

    quality = load_artifact("quality")
    if quality and not quality.get("simulation_reliable", True):
        raise HTTPException(
            status_code=403,
            detail=(
                "Simulation Denied: Your ML model is mathematically unreliable for projections "
                "(AUC < 0.65). This usually means your attrition data is too small or lacks meaningful patterns. "
                "Please review the Model Quality Report in the Upload dashboard and provide a stronger dataset."
            ),
        )

    job_id = str(uuid.uuid4())
    with Session(engine) as session:
        session.add(
            SimulationJob(
                job_id=job_id,
                job_type="comparison",
                status="queued",
                policy_name=f"{request.policy_a}_vs_{request.policy_b}",
                runs=request.runs,
                duration_months=request.duration_months,
                seed=request.seed,
            )
        )
        session.commit()

    background_tasks.add_task(
        compare_simulations_task,
        job_id,
        request.policy_a,
        request.policy_b,
        request.runs,
        request.duration_months,
        request.seed,
    )

    return {
        "job_id": job_id,
        "poll_url": f"/api/sim/status/{job_id}",
        "status": "queued",
        "message": "Comparison queued. Poll poll_url for status.",
    }

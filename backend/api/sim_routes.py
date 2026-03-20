# backend/api/sim_routes.py

import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from backend.core.simulation.monte_carlo import run_monte_carlo
from backend.core.simulation.policies import SimulationConfig, get_policy, POLICIES
from backend.api.upload_routes import get_data_issues

router = APIRouter(prefix="/api/sim", tags=["Simulation"])


class SimulationRequest(BaseModel):
    policy_name: str = "baseline"
    runs: int = Field(default=10, ge=1, le=50)
    duration_months: int = Field(default=12, ge=1, le=24)


class CompareRequest(BaseModel):
    policy_a: str = "baseline"
    policy_b: str = "kpi_pressure"
    runs: int = Field(default=10, ge=1, le=50)
    duration_months: int = Field(default=12, ge=1, le=24)


@router.get("/policies")
def list_policies():
    return {"policies": list(POLICIES.keys())}


@router.post("/run")
async def run_simulation_endpoint(request: SimulationRequest):
    import os
    from sqlmodel import Session, select
    from backend.db.database import engine
    from backend.db.models import Employee

    if not os.path.exists("backend/core/ml/exports/quit_probability.pkl"):
        raise HTTPException(
            status_code=400,
            detail="No trained model found. Please upload a dataset first via POST /api/upload/dataset."
        )

    with Session(engine) as session:
        count = session.exec(select(Employee)).all()
    if not count:
        raise HTTPException(
            status_code=400,
            detail="No employee data in database. Please upload a dataset first via POST /api/upload/dataset."
        )

    if request.policy_name not in POLICIES:
        raise HTTPException(status_code=400, detail=f"Unknown policy: {request.policy_name}")

    config = get_policy(request.policy_name)
    config.duration_months = request.duration_months

    # Run in a thread pool so the event loop stays free for health-checks / other requests
    results = await asyncio.to_thread(run_monte_carlo, config, request.runs, request.policy_name)

    # Req #19: attach persistent data quality warnings if any
    data_issues = get_data_issues()
    if data_issues:
        results["data_warnings"] = data_issues

    return results


@router.post("/compare")
async def compare_policies(request: CompareRequest):
    if request.policy_a not in POLICIES:
        raise HTTPException(status_code=400, detail=f"Unknown policy: {request.policy_a}")
    if request.policy_b not in POLICIES:
        raise HTTPException(status_code=400, detail=f"Unknown policy: {request.policy_b}")

    config_a = get_policy(request.policy_a)
    config_a.duration_months = request.duration_months

    config_b = get_policy(request.policy_b)
    config_b.duration_months = request.duration_months

    # Run both MC simulations concurrently in the thread pool.
    # Previously sequential: total wait = T_a + T_b (~120s for 10-run compare).
    # Now concurrent:        total wait = max(T_a, T_b) (~60s).
    results_a, results_b = await asyncio.gather(
        asyncio.to_thread(run_monte_carlo, config_a, request.runs, request.policy_a),
        asyncio.to_thread(run_monte_carlo, config_b, request.runs, request.policy_b),
    )

    return {
        "policy_a": results_a,
        "policy_b": results_b,
        "data_warnings": get_data_issues() or None,
    }
# backend/api/sim_routes.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel,Field
from backend.simulation.monte_carlo import run_monte_carlo
from backend.simulation.policies import SimulationConfig, get_policy, POLICIES

router = APIRouter(prefix="/api/sim",tags=["Simulation"])


class SimulationRequest(BaseModel):
    policy_name: str = "baseline"
    runs: int = Field(default=10,ge=1,le=50)
    duration_months: int = Field(default=12,ge=1,le=24)


class CompareRequest(BaseModel):
    policy_a: str = "baseline"
    policy_b: str = "kpi_pressure"
    runs: int = Field(default=10, ge=1, le=50)
    duration_months: int = Field(default=12, ge=1, le=24)


@router.get("/policies")
def list_policies():
    return {"policies": list(POLICIES.keys())}


@router.post("/run")
def run_simulation_endpoint(request: SimulationRequest):
    if request.policy_name not in POLICIES:
        raise HTTPException(status_code=400, detail=f"Unknown policy: {request.policy_name}")
    config = get_policy(request.policy_name)
    config.duration_months = request.duration_months
    results = run_monte_carlo(config, runs=request.runs, policy_name=request.policy_name)
    return results

@router.post("/compare")
def compare_policies(request: CompareRequest):
    if request.policy_a not in POLICIES:
        raise HTTPException(status_code=400, detail=f"Unknown policy: {request.policy_a}")
    if request.policy_b not in POLICIES:
        raise HTTPException(status_code=400, detail=f"Unknown policy: {request.policy_b}")

    config_a = get_policy(request.policy_a)
    config_a.duration_months = request.duration_months

    config_b = get_policy(request.policy_b)
    config_b.duration_months = request.duration_months

    results_a = run_monte_carlo(config_a, runs=request.runs, policy_name=request.policy_a)
    results_b = run_monte_carlo(config_b, runs=request.runs, policy_name=request.policy_b)

    return {
        "policy_a": results_a,
        "policy_b": results_b,
    }
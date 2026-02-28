import os
from fastapi import APIRouter, HTTPException
from backend.ml import explain

router = APIRouter(prefix="/api/ml", tags=["Machine Learning"])

@router.get("/explain/{employee_id}")
def explain_employee_attrition(employee_id: int):
    # Ensure the model is trained first
    if not os.path.exists("backend/ml/exports/quit_probability.pkl"):
        raise HTTPException(
            status_code=400,
            detail="No trained model found. Please upload a dataset first."
        )

    explanation = explain.explain_employee(employee_id)
    if "error" in explanation:
        raise HTTPException(status_code=404, detail=explanation["error"])
        
    return explanation

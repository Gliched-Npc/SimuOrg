from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List
from backend.database import get_session
from backend.models import Employee

router = APIRouter()

@router.get("/test-data", response_model=List[Employee])
def get_sample_data(session: Session = Depends(get_session)):
    """
    Fetches the first 5 employees to prove the Database is connected.
    """
    statement = select(Employee).limit(10)
    employees = session.exec(statement).all()
    
    if not employees:
        raise HTTPException(status_code=404, detail="No employees found in DB")
    
    return employees
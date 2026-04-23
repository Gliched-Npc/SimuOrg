# backend/ml/burnout_estimator.py


import pandas as pd
from sqlmodel import Session, select

from backend.db.database import engine
from backend.db.models import Employee


def burnout_threshold(job_level: int, total_working_years: float) -> float:
    """
    Returns a burnout threshold between 0.0 and 1.0
    Higher job level and experience = higher tolerance
    """
    base_threshold = 0.3
    level_weight = 0.08
    experience_weight = 0.02

    threshold = base_threshold
    threshold += (job_level - 1) * level_weight
    threshold += min(total_working_years, 20) * experience_weight

    return round(min(threshold, 0.85), 3)


def load_data_from_db(session_id: str = "global"):
    with Session(engine) as session:
        employees = session.exec(select(Employee).where(Employee.session_id == session_id)).all()
    df = pd.DataFrame([e.model_dump() for e in employees])
    return df


def train_burnout_estimator(session_id: str = "global"):
    print("=== Loading data from database...")
    load_data_from_db(session_id=session_id)

    print("\n=== Sample Thresholds:")
    print(f"  Junior L1 (1yr)    : {burnout_threshold(1, 1)}")
    print(f"  Mid    L2 (5yr)    : {burnout_threshold(2, 5)}")
    print(f"  Senior L3 (10yr)   : {burnout_threshold(3, 10)}")
    print(f"  Manager L4 (15yr)  : {burnout_threshold(4, 15)}")
    print(f"  Director L5 (20yr) : {burnout_threshold(5, 20)}")

    print("[done] Packed for DB")
    # Persist to DB so artifacts survive server restarts
    from backend.storage.storage import save_artifact

    save_artifact("burnout", burnout_threshold, "pkl", session_id=session_id)


if __name__ == "__main__":
    train_burnout_estimator()

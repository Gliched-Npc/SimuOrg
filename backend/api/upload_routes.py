# backend/api/upload_routes.py

import io
import uuid
import pandas as pd
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from backend.db.database import init_db
from backend.schema import REQUIRED_COLUMNS, normalize_dataframe, build_schema_report
from backend.upload import clean_dataframe, ingest_from_dataframe
from backend.quality_checker import check_data_quality
from backend.workers.tasks import run_training_task
from backend.db.models import SimulationJob
from sqlmodel import Session
from backend.db.database import engine
 # needed to bust lazy-load cache

router = APIRouter(prefix="/api/upload", tags=["Upload"])


# ── Persistent data quality warnings (#19) ──
# Stored after upload so simulation endpoints can attach them to results.
_last_data_issues: list[dict] = []


def get_data_issues() -> list[dict]:
    """Return the quality issues from the most recent upload."""
    return _last_data_issues


def _read_and_normalize(file_bytes: bytes) -> tuple[pd.DataFrame, bool]:
    """Parse CSV bytes, normalize columns and return (df, overtime_was_present)."""
    df = pd.read_csv(io.BytesIO(file_bytes))
    df, overtime_was_present = normalize_dataframe(df)
    missing_required = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_required:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required columns: {missing_required}. "
                   f"These are the minimum columns needed to run a simulation.",
        )
    return df, overtime_was_present


# ── Req #17: Pre-ingest validation endpoint ──────────────────────────────────

@router.post("/validate")
async def validate_dataset(file: UploadFile = File(...)):
    """
    Run quality checks on the uploaded CSV WITHOUT ingesting into the database.
    Returns issues with severity tiers and a cleaning report so the client
    can decide to fix-and-reupload or proceed-anyway.
    """
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No file provided.")
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted.")

    contents = await file.read()
    try:
        df, overtime_was_present = _read_and_normalize(contents)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read CSV: {str(e)}")

    schema_report = build_schema_report(df, overtime_was_present)
    df, duplicates_removed, junk_removed, null_rates, cleaning_audit = clean_dataframe(df)
    quality_report = check_data_quality(df, duplicates_removed, junk_removed, null_rates, cleaning_audit)

    return {
        "status":          "validated",
        "rows":            len(df),
        "duplicates_removed": duplicates_removed,
        "junk_removed":    junk_removed,
        "schema_report":   schema_report,
        "trust_score":     quality_report["trust_score"],
        "issues":          quality_report["issues"],
        "cleaning_audit":  quality_report["cleaning_audit"],
        "message":         "Validation complete. Review issues, then POST to /api/upload/dataset to ingest.",
    }


# ── Main upload endpoint (unchanged contract, enriched response) ─────────────

@router.post("/dataset")
async def upload_dataset(file: UploadFile = File(...), background_tasks: BackgroundTasks = None):
    global _last_data_issues

    # 1. Validate file
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No file provided. Please select a CSV file to upload.")
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted.")

    # 2. Read CSV
    contents = await file.read()
    try:
        df, overtime_was_present = _read_and_normalize(contents)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read CSV: {str(e)}")

    # 3. Schema report + clean
    schema_report = build_schema_report(df, overtime_was_present)
    df, duplicates_removed, junk_removed, null_rates, cleaning_audit = clean_dataframe(df)
    quality_report = check_data_quality(df, duplicates_removed, junk_removed, null_rates, cleaning_audit)
    _last_data_issues = quality_report["issues"]  # persist for sim_routes (#19)

    # 4. Ingest into DB (fast — no ML yet)
    init_db()
    try:
        result = ingest_from_dataframe(df)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")

    # 5. Kick off training + calibration 
    job_id = str(uuid.uuid4())
    with Session(engine) as session:
        job = SimulationJob(
            job_id=job_id,
            job_type="training",
            status="queued",
        )
        session.add(job)
        session.commit()

    run_training_task.delay(job_id, quality_report)

    return {
        "status":       "ingested",
        "rows":         result["ingested"],
        "skipped":      result["skipped"],
        "job_id":       job_id,
        "poll_url":     f"/api/upload/status/{job_id}",
        "message":      "Dataset ingested. Training and calibration running in background. Poll poll_url for status.",
        "trust_score":    quality_report["trust_score"],
        "issues":         quality_report["issues"],
        "cleaning_audit": quality_report["cleaning_audit"],
        "schema_report":  schema_report,
    }


@router.get("/status/{job_id}")
def get_training_status(job_id: str):
    import json
    with Session(engine) as session:
        job = session.get(SimulationJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    result = json.loads(job.result) if job.result else None
    return {
        "job_id": job_id,
        "status": job.status,
        "error":  job.error,
        "result": result,
    }

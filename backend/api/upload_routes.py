# backend/api/upload_routes.py

import io
import json
import uuid

import pandas as pd
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlmodel import Session

from backend.api.deps import get_session_id
from backend.db.database import engine, init_db
from backend.db.models import SimulationJob
from backend.schema import REQUIRED_COLUMNS, normalize_dataframe
from backend.services.report_service import build_upload_report
from backend.upload import ingest_from_dataframe
from backend.workers.tasks import run_training_task

# needed to bust lazy-load cache

router = APIRouter(prefix="/api/upload", tags=["Upload"])


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
async def validate_dataset(
    file: UploadFile = File(...),
    session_id: str = Depends(get_session_id),
):
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

    report = build_upload_report(df, overtime_was_present)
    df = report["df"]
    schema_report = report["schema_report"]
    quality_report = report["quality_report"]
    duplicates_removed = report["duplicates_removed"]
    junk_removed = report["junk_removed"]

    return {
        "status": "validated",
        "rows": len(df),
        "duplicates_removed": duplicates_removed,
        "junk_removed": junk_removed,
        "schema_report": schema_report,
        "trust_score": quality_report["trust_score"],
        "issues": quality_report["issues"],
        "cleaning_audit": quality_report["cleaning_audit"],
        "message": "Validation complete. Review issues, then POST to /api/upload/dataset to ingest.",
    }


# ── Main upload endpoint (unchanged contract, enriched response) ─────────────


@router.post("/dataset")
async def upload_dataset(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
    session_id: str = Depends(get_session_id),
):
    # 1. Validate file
    if not file or not file.filename:
        raise HTTPException(
            status_code=400, detail="No file provided. Please select a CSV file to upload."
        )
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
    report = build_upload_report(df, overtime_was_present)
    df = report["df"]
    schema_report = report["schema_report"]
    quality_report = report["quality_report"]
    duplicates_removed = report["duplicates_removed"]
    junk_removed = report["junk_removed"]
    # issues stored in DB against job_id below

    # 4. Ingest into DB (fast — no ML yet)
    init_db()
    try:
        result = ingest_from_dataframe(df, session_id=session_id)
        with Session(engine) as session:
            from sqlalchemy import text

            session.exec(
                text("DELETE FROM simulation_job WHERE session_id = :sid"),
                params={"sid": session_id},
            )
            session.exec(
                text("DELETE FROM orchestrate_job WHERE session_id = :sid"),
                params={"sid": session_id},
            )
            session.exec(
                text("DELETE FROM policy_generation_log WHERE session_id = :sid"),
                params={"sid": session_id},
            )
            session.commit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")

    # 4.5 Save dataset metadata
    from datetime import datetime, timezone

    from backend.storage.storage import save_artifact

    save_artifact(
        "dataset_metadata",
        {
            "filename": file.filename,
            "rows": result["ingested"],
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        },
        "json",
        session_id=session_id,
    )

    # 5. Kick off training + calibration
    job_id = str(uuid.uuid4())
    with Session(engine) as session:
        job = SimulationJob(
            job_id=job_id,
            job_type="training",
            status="queued",
            data_issues=json.dumps(quality_report["issues"]),
            session_id=session_id,
        )
        session.add(job)
        session.commit()

    background_tasks.add_task(run_training_task, job_id, quality_report, session_id)

    return {
        "status": "ingested",
        "rows": result["ingested"],
        "skipped": result["skipped"],
        "duplicates_removed": duplicates_removed,
        "junk_removed": junk_removed,
        "job_id": job_id,
        "poll_url": f"/api/upload/status/{job_id}",
        "message": "Dataset ingested. Training and calibration running in background. Poll poll_url for status.",
        "trust_score": quality_report["trust_score"],
        "issues": quality_report["issues"],
        "cleaning_audit": quality_report["cleaning_audit"],
        "schema_report": schema_report,
    }


@router.get("/status/{job_id}")
def get_training_status(job_id: str, session_id: str = Depends(get_session_id)):
    import json

    with Session(engine) as session:
        job = session.get(SimulationJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    # Bug #3 fix: prevent cross-user result leakage via guessed job UUIDs
    if job.session_id != session_id:
        raise HTTPException(status_code=403, detail="Access denied.")
    result = json.loads(job.result) if job.result else None
    return {
        "job_id": job_id,
        "status": job.status,
        "error": job.error,
        "result": result,
    }


@router.get("/metadata")
def get_dataset_metadata(session_id: str = Depends(get_session_id)):
    from backend.storage.storage import load_artifact

    metadata = load_artifact("dataset_metadata", session_id=session_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="No dataset uploaded.")
    return metadata

# backend/api/upload_routes.py

import io
import uuid
import threading
import pandas as pd
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from backend.database import init_db
from backend.schema import REQUIRED_COLUMNS, normalize_dataframe, build_schema_report
from backend.upload import clean_dataframe, ingest_from_dataframe, validate_data_quality
from backend.ml.attrition_model import train_attrition_model
from backend.ml.burnout_estimator import train_burnout_estimator
from backend.ml.calibration import calibrate
import backend.simulation.agent as _agent_module  # needed to bust lazy-load cache

router = APIRouter(prefix="/api/upload", tags=["Upload"])

# In-memory job registry.
# Key: job_id (str UUID)
# Value: {status, result, error}
# Status: "training" → "calibrating" → "done" | "failed"
_JOBS: dict[str, dict] = {}
_JOBS_LOCK = threading.Lock()


def _background_train_and_calibrate(job_id: str):
    """Runs in a background thread after ingestion is complete."""
    def _set(status=None, **kw):
        with _JOBS_LOCK:
            if status:
                _JOBS[job_id]["status"] = status
            _JOBS[job_id].update(kw)

    try:
        _set(status="training")
        model_quality = train_attrition_model()
        train_burnout_estimator()
        _agent_module._quit_model_cache = None  # bust lazy-load cache

        _set(status="calibrating")
        cal = calibrate()

        _set(
            status="done",
            model={
                "auc_roc":        model_quality.get("auc_roc"),
                "cv_auc_mean":    model_quality.get("cv_auc_mean"),
                "features":       model_quality.get("features_used"),
                "signal":         model_quality.get("signal_strength"),
                "recommendation": model_quality.get("recommendation"),
            },
            calibration={
                "annual_attrition_rate": cal.get("annual_attrition_rate"),
                "monthly_natural_rate":  cal.get("monthly_natural_rate"),
                "quit_threshold":        cal.get("quit_threshold"),
                "calib_quality":         cal.get("calib_quality"),
                "calib_attrition_std":   cal.get("calib_attrition_std"),
            },
        )

    except Exception as exc:
        _set(status="failed", error=str(exc))


@router.post("/dataset")
async def upload_dataset(file: UploadFile = File(...), background_tasks: BackgroundTasks = None):
    # 1. Validate file
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No file provided. Please select a CSV file to upload.")
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted.")

    # 2. Read CSV
    contents = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read CSV: {str(e)}")

    # 3. Normalize
    df, overtime_was_present = normalize_dataframe(df)

    # 4. Validate required columns
    missing_required = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_required:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required columns: {missing_required}. "
                   f"These are the minimum columns needed to run a simulation."
        )

    # 5–6. Schema report + clean
    schema_report = build_schema_report(df, overtime_was_present)
    df, duplicates_removed = clean_dataframe(df)
    quality = validate_data_quality(df, duplicates_removed=duplicates_removed)

    # 7. Ingest into DB (fast — no ML yet)
    init_db()
    try:
        result = ingest_from_dataframe(df)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")

    # 8. Kick off training + calibration in a background thread.
    # This prevents the HTTP request from blocking for 90-120 seconds.
    # The client should poll GET /api/upload/status/{job_id} to track progress.
    job_id = str(uuid.uuid4())
    with _JOBS_LOCK:
        _JOBS[job_id] = {"status": "queued"}

    thread = threading.Thread(target=_background_train_and_calibrate, args=(job_id,), daemon=True)
    thread.start()

    return {
        "status":       "ingested",
        "rows":         result["ingested"],
        "skipped":      result["skipped"],
        "job_id":       job_id,
        "poll_url":     f"/api/upload/status/{job_id}",
        "message":      "Dataset ingested. Training and calibration running in background. Poll poll_url for status.",
        "warnings":     quality["warnings"] or None,
        "schema_report": schema_report,
    }


@router.get("/status/{job_id}")
def get_training_status(job_id: str):
    """
    Poll this endpoint after upload to track training + calibration progress.
    Status progression: queued → training → calibrating → done | failed
    """
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    return {"job_id": job_id, **job}


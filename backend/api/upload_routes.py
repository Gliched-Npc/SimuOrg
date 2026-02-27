# backend/api/upload_routes.py

import io
import pandas as pd
from fastapi import APIRouter, UploadFile, File, HTTPException
from backend.database import init_db
from backend.schema import REQUIRED_COLUMNS, normalize_dataframe, build_schema_report
from backend.upload import clean_dataframe, ingest_from_dataframe, validate_data_quality
from backend.ml.attrition_model import train_attrition_model
from backend.ml.burnout_estimator import train_burnout_estimator
from backend.ml.calibration import calibrate
import backend.simulation.agent as _agent_module  # needed to bust lazy-load cache

router = APIRouter(prefix="/api/upload", tags=["Upload"])


@router.post("/dataset")
async def upload_dataset(file: UploadFile = File(...)):
    # 1. Validate file provided and type
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

    # 3. Normalize — column names, attrition values, overtime encoding, defaults
    df, missing_optional, found_optional, overtime_was_present, travel_was_present = normalize_dataframe(df)

    # 4. Validate required columns (after normalization)
    missing_required = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_required:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required columns: {missing_required}. "
                   f"These are the minimum columns needed to run a simulation."
        )

    # 5. Build schema report
    schema_report = build_schema_report(df, missing_optional, found_optional, overtime_was_present, travel_was_present)

    # 6. Clean + validate data quality
    df = clean_dataframe(df)
    total_rows = len(df)
    quality = validate_data_quality(df)

    # 7. Ingest
    init_db()
    try:
        result = ingest_from_dataframe(df)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")

    # 8. Train + calibrate
    try:
        model_quality = train_attrition_model()
        train_burnout_estimator()
        cal = calibrate()
        # Bust the lazy-load cache so the next simulation uses the new model
        _agent_module._quit_model_cache = None
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Data ingested but model training failed: {str(e)}"
        )

    return {
        "status":  "success",
        "rows":    result["ingested"],
        "skipped": result["skipped"],
        "model": {
            "auc_roc":        model_quality.get("auc_roc"),
            "cv_auc_mean":    model_quality.get("cv_auc_mean"),
            "features":       model_quality.get("features_used"),
            "signal":         model_quality.get("signal_strength"),
            "recommendation": model_quality.get("recommendation"),
        },
        "calibration": {
            "annual_attrition_rate": cal.get("annual_attrition_rate"),
            "monthly_natural_rate":  cal.get("monthly_natural_rate"),
            "quit_threshold":        cal.get("quit_threshold"),
        },
        "warnings": quality["warnings"] or None,
    }

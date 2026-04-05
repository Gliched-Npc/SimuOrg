# backend/storage/storage.py
#
# Thin persistence layer for ML artifacts.
# PKL files  → base64-encoded TEXT in the ml_artifact table.
# JSON files → raw JSON string in the ml_artifact table.
#
# Disk paths are kept as a local cache — training writes to both disk AND DB.
# On startup, restore_artifacts_from_db() refills missing disk files from the DB.

import base64
import io
import json
import os
from datetime import datetime

import joblib

# Maps artifact name → disk path relative to the project root.
ARTIFACT_DISK_PATHS: dict[str, str] = {
    "quit_model":  "backend/core/ml/exports/quit_probability.pkl",
    "burnout":     "backend/core/ml/exports/burnout_threshold.pkl",
    "calibration": "backend/core/ml/exports/calibration.json",
    "quality":     "backend/core/ml/exports/quality_report.json",
}


# ── helpers ──────────────────────────────────────────────────────────────────

def _encode_pkl(obj) -> str:
    """Serialize any joblib-serializable object to a base64 string."""
    buf = io.BytesIO()
    joblib.dump(obj, buf)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _decode_pkl(b64: str):
    """Deserialize a base64 string back to the original Python object."""
    raw = base64.b64decode(b64.encode("utf-8"))
    return joblib.load(io.BytesIO(raw))


# ── public API ────────────────────────────────────────────────────────────────

def save_artifact(name: str, data, artifact_type: str) -> None:
    """
    Upsert an artifact row in the ml_artifact table.

    Parameters
    ----------
    name          : one of "quit_model" | "burnout" | "calibration" | "quality"
    data          : Python object — dict for JSON, any joblib-able obj for pkl
    artifact_type : "pkl" | "json"
    """
    from sqlmodel import Session
    from backend.db.database import engine
    from backend.db.models import MLArtifact

    encoded = _encode_pkl(data) if artifact_type == "pkl" else json.dumps(data)

    with Session(engine) as session:
        existing = session.get(MLArtifact, name)
        if existing:
            existing.data          = encoded
            existing.artifact_type = artifact_type
            existing.updated_at    = datetime.utcnow()
            session.add(existing)
        else:
            session.add(MLArtifact(
                name=name,
                artifact_type=artifact_type,
                data=encoded,
            ))
        session.commit()
    print(f"[storage] Artifact '{name}' ({artifact_type}) saved to DB.")


def load_artifact(name: str):
    """
    Load an artifact from the ml_artifact table.

    Returns
    -------
    dict if artifact_type == "json", deserialized object if "pkl", None if not found.
    """
    from sqlmodel import Session
    from backend.db.database import engine
    from backend.db.models import MLArtifact

    with Session(engine) as session:
        row = session.get(MLArtifact, name)

    if row is None:
        return None

    if row.artifact_type == "pkl":
        return _decode_pkl(row.data)
    return json.loads(row.data)


def restore_artifacts_from_db() -> None:
    """
    Called once at application startup (inside init_db / lifespan).

    For each known artifact, if the disk file is missing, load it from the DB
    and write it back to disk so the rest of the app can load it normally.
    Nothing changes if the disk file already exists.
    """
    from sqlmodel import Session
    from backend.db.database import engine
    from backend.db.models import MLArtifact

    os.makedirs("backend/core/ml/exports", exist_ok=True)

    with Session(engine) as session:
        for name, disk_path in ARTIFACT_DISK_PATHS.items():
            if os.path.exists(disk_path):
                continue  # disk cache is fresh — nothing to do

            row = session.get(MLArtifact, name)
            if row is None:
                # Not in DB yet — first-ever deployment, user hasn't trained yet.
                continue

            print(f"[storage] '{name}' missing from disk — restoring from DB...")

            if row.artifact_type == "pkl":
                obj = _decode_pkl(row.data)
                joblib.dump(obj, disk_path)
            else:
                data = json.loads(row.data)
                with open(disk_path, "w") as f:
                    json.dump(data, f, indent=2)

            print(f"[storage] '{name}' restored → {disk_path}")

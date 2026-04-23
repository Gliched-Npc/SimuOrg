# backend/storage/storage.py
#
# Thin persistence layer for ML artifacts.
# PKL files  → base64-encoded TEXT in the ml_artifact table.
# JSON files → raw JSON string in the ml_artifact table.
#
# Each artifact is scoped to a session_id so different users don't share models.

import base64
import io
import json
from datetime import datetime

import joblib

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


def save_artifact(name: str, data, artifact_type: str, session_id: str = "global") -> None:
    """
    Upsert an artifact row in the ml_artifact table, scoped to session_id.

    Parameters
    ----------
    name          : one of "quit_model" | "burnout" | "calibration" | "quality"
    data          : Python object — dict for JSON, any joblib-able obj for pkl
    artifact_type : "pkl" | "json"
    session_id    : browser session identifier (default "global")
    """
    from sqlmodel import Session, select

    from backend.db.database import engine
    from backend.db.models import MLArtifact

    encoded = _encode_pkl(data) if artifact_type == "pkl" else json.dumps(data)

    with Session(engine) as session:
        existing = session.exec(
            select(MLArtifact).where(MLArtifact.name == name, MLArtifact.session_id == session_id)
        ).first()
        if existing:
            existing.data = encoded
            existing.artifact_type = artifact_type
            existing.updated_at = datetime.utcnow()
            session.add(existing)
        else:
            session.add(
                MLArtifact(
                    name=name,
                    session_id=session_id,
                    artifact_type=artifact_type,
                    data=encoded,
                )
            )
        session.commit()
    print(f"[storage] Artifact '{name}' (session={session_id}, {artifact_type}) saved to DB.")


def load_artifact(name: str, session_id: str = "global"):
    """
    Load an artifact from the ml_artifact table, scoped to session_id.

    Returns
    -------
    dict if artifact_type == "json", deserialized object if "pkl", None if not found.
    """
    from sqlmodel import Session, select

    from backend.db.database import engine
    from backend.db.models import MLArtifact

    with Session(engine) as session:
        row = session.exec(
            select(MLArtifact).where(MLArtifact.name == name, MLArtifact.session_id == session_id)
        ).first()

    if row is None:
        return None

    if row.artifact_type == "pkl":
        return _decode_pkl(row.data)
    return json.loads(row.data)

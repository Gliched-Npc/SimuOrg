import sys
import os
import pytest

# Ensure `backend/` is on sys.path so imports like
# `from backend.core.ml.calibration import calibrate` resolve correctly.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))


# ── Global mocks applied to every test session ────────────────────────────────
# These prevent accidental DB or file I/O during any test run.

@pytest.fixture(autouse=True, scope="session")
def block_real_db():
    """Prevent any test from accidentally hitting the real database."""
    from unittest.mock import patch
    with patch("backend.db.database.engine", new=None):
        yield


@pytest.fixture(autouse=True)
def isolate_calibration_file(tmp_path, monkeypatch):
    """
    Redirect calibration.json reads/writes to a temp file per test.
    Prevents test pollution of real exports/calibration.json.
    """
    fake_cal = {
        "prob_scale":               1.0,
        "stress_amplification":     2.0,
        "monthly_natural_rate":     0.0145,
        "stress_threshold":         0.15,
        "new_hire_monthly_prob":    0.029,
        "stress_gain_rate":         0.01,
        "behavior_stress_gain_rate": 0.01,
        "motivation_recovery_rate": 0.005,
        "recovery_rate":            0.005,
        "avg_burnout_limit":        0.5,
        "annual_attrition_rate":    0.15,
        "calib_quality":            "stable",
        "calib_attrition_std":      0.01,
    }
    import json
    cal_path = tmp_path / "calibration.json"
    cal_path.write_text(json.dumps(fake_cal))

    # Patch the path constant used in time_engine and behavior_engine
    monkeypatch.setenv("CALIBRATION_PATH", str(cal_path))
    yield

"""
Tests for backend/core/ml/calibration.py

Critical audit bug covered:
- stress_amplification_override=0.0 was being swallowed by `if stress_amplification_override is not None`
  The fix is already in the code (uses `is not None`), this test locks it in permanently.
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

# ── Shared mock factory ────────────────────────────────────────────────────────


def _make_mock_employee(
    employee_id=1,
    job_satisfaction=3.0,
    work_life_balance=3.0,
    job_level=2,
    total_working_years=5,
    years_at_company=3,
    monthly_income=5000,
    attrition="No",
    department="Engineering",
    job_role="Engineer",
    performance_rating=3,
    stock_option_level=1,
    age=30,
    distance_from_home=10,
    percent_salary_hike=10,
    years_since_last_promotion=1,
    years_with_curr_manager=2,
    job_involvement=3,
    environment_satisfaction=3,
    num_companies_worked=2,
    marital_status="Single",
    overtime=0,
    manager_id=None,
):
    emp = MagicMock()
    emp.employee_id = employee_id
    emp.job_satisfaction = job_satisfaction
    emp.work_life_balance = work_life_balance
    emp.job_level = job_level
    emp.total_working_years = total_working_years
    emp.years_at_company = years_at_company
    emp.monthly_income = monthly_income
    emp.attrition = attrition
    emp.department = department
    emp.job_role = job_role
    emp.performance_rating = performance_rating
    emp.stock_option_level = stock_option_level
    emp.age = age
    emp.distance_from_home = distance_from_home
    emp.percent_salary_hike = percent_salary_hike
    emp.years_since_last_promotion = years_since_last_promotion
    emp.years_with_curr_manager = years_with_curr_manager
    emp.job_involvement = job_involvement
    emp.environment_satisfaction = environment_satisfaction
    emp.num_companies_worked = num_companies_worked
    emp.marital_status = marital_status
    emp.overtime = overtime
    emp.manager_id = manager_id
    return emp


def _make_mock_model():
    """Returns a mock sklearn-style model."""
    model = MagicMock()
    # predict_proba returns shape (N, 2) — column 1 is quit probability
    model.predict_proba.return_value = np.array([[0.8, 0.2]])
    return model


# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture
def full_calibration_patch(tmp_path):
    """
    Patches all external dependencies of calibrate() so the pure math is testable.
    Returns the mock objects so individual tests can adjust them.
    """

    employees = [
        _make_mock_employee(employee_id=i, attrition="Yes" if i % 5 == 0 else "No")
        for i in range(1, 51)  # 50 employees, 10 quitters → 20% attrition
    ]

    mock_model = _make_mock_model()
    mock_model.predict_proba.return_value = np.tile([0.8, 0.2], (50, 1))

    sim_result = {"summary": {"period_attrition_pct": 20.0}}

    patches = {
        "session": patch("backend.core.ml.calibration.Session"),
        "load_artifact": patch("backend.storage.storage.load_artifact"),
        "run_sim": patch(
            "backend.core.simulation.time_engine.run_simulation", return_value=sim_result
        ),
        "load_agents": patch(
            "backend.core.simulation.time_engine.load_agents_from_db", return_value=[]
        ),
        "build_graph": patch("backend.core.simulation.org_graph.build_org_graph"),
        "clear_graph": patch("backend.core.simulation.org_graph.clear_graph_cache"),
        "clear_cal": patch("backend.core.simulation.behavior_engine.clear_calibration_cache"),
        "clear_engine": patch("backend.core.simulation.time_engine.clear_engine_calibration_cache"),
        "clear_quit": patch("backend.core.simulation.agent.clear_quit_model_cache"),
        "save_artifact": patch("backend.storage.storage.save_artifact"),
        "eng_features": patch(
            "backend.core.ml.calibration.engineer_features",
            side_effect=lambda df, encoders=None: df,
        ),
        "burnout_fn": patch("backend.core.ml.calibration.burnout_threshold", return_value=0.5),
    }

    started = {k: p.start() for k, p in patches.items()}

    # Wire up session mock
    started[
        "session"
    ].return_value.__enter__.return_value.exec.return_value.all.return_value = employees

    # Wire up load_artifact mock
    started["load_artifact"].return_value = {
        "model": mock_model,
        "threshold": 0.5,
        "features": [],
        "label_encoders": {},
    }

    yield started

    for p in patches.values():
        p.stop()


# ── Tests ──────────────────────────────────────────────────────────────────────


class TestStressAmplificationOverride:
    """
    Critical audit: stress_amplification_override=0.0 was being swallowed.
    Old code: `if stress_amplification_override:` (0.0 is falsy → ignored)
    Fixed code: `if stress_amplification_override is not None:` (0.0 is kept)
    These tests permanently lock that fix.
    """

    def test_zero_override_is_not_swallowed(self, full_calibration_patch):
        """0.0 must survive into the output — this is the exact audit bug."""
        from backend.core.ml.calibration import calibrate

        result = calibrate(stress_amplification_override=0.0)

        assert result["stress_amplification"] == 0.0, (
            "stress_amplification_override=0.0 was swallowed. "
            "Check: `if stress_amplification_override is not None` not `if stress_amplification_override`"
        )

    def test_none_override_computes_from_data(self, full_calibration_patch):
        """None must trigger the data-driven calculation path, not return 0."""
        from backend.core.ml.calibration import calibrate

        result = calibrate(stress_amplification_override=None)

        assert result["stress_amplification"] > 0.0
        assert result["stress_amplification"] <= 5.0  # capped at 5.0 per inline comment

    def test_positive_override_respected(self, full_calibration_patch):
        """Any explicit positive float override must pass through unchanged."""
        from backend.core.ml.calibration import calibrate

        result = calibrate(stress_amplification_override=3.7)

        assert result["stress_amplification"] == 3.7


class TestCalibrationOutputSchema:
    """Verify the calibration dict always has all required keys."""

    REQUIRED_KEYS = [
        "quit_threshold",
        "stress_threshold",
        "motivation_threshold",
        "avg_quit_prob",
        "avg_burnout_limit",
        "annual_attrition_rate",
        "monthly_natural_rate",
        "stress_gain_rate",
        "behavior_stress_gain_rate",
        "recovery_rate",
        "prob_scale",
        "stress_amplification",
        "new_hire_monthly_prob",
        "calib_quality",
        "calib_attrition_std",
    ]

    def test_all_required_keys_present(self, full_calibration_patch):
        from backend.core.ml.calibration import calibrate

        result = calibrate()

        for key in self.REQUIRED_KEYS:
            assert key in result, f"Missing key in calibration output: '{key}'"

    def test_stress_gain_rate_within_bounds(self, full_calibration_patch):
        """stress_gain_rate is clamped to [0.0, 0.05] in the code."""
        from backend.core.ml.calibration import calibrate

        result = calibrate()

        assert 0.0 <= result["stress_gain_rate"] <= 0.05

    def test_behavior_stress_gain_rate_mirrors_stress_gain_rate(self, full_calibration_patch):
        """behavior_stress_gain_rate is an explicit alias — must always equal stress_gain_rate."""
        from backend.core.ml.calibration import calibrate

        result = calibrate()

        assert result["behavior_stress_gain_rate"] == result["stress_gain_rate"]

    def test_prob_scale_positive(self, full_calibration_patch):
        from backend.core.ml.calibration import calibrate

        result = calibrate()

        assert result["prob_scale"] > 0.0

    def test_calib_quality_valid_value(self, full_calibration_patch):
        from backend.core.ml.calibration import calibrate

        result = calibrate()

        assert result["calib_quality"] in ("stable", "noisy")


class TestNoEmployeesEdgeCase:
    def test_raises_on_empty_db(self):
        with patch("backend.core.ml.calibration.Session") as mock_session:
            mock_session.return_value.__enter__.return_value.exec.return_value.all.return_value = []

            from backend.core.ml.calibration import calibrate

            with pytest.raises(ValueError, match="No employees found"):
                calibrate()

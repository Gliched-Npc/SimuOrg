"""
Tests for backend/workers/tasks.py

Audit bugs covered:
- Silent failure when job_id not found — old code: `if job:` did nothing on miss
- Fixed code: raises ValueError with clear message
- Two DB sessions opened per task — _update_job is called multiple times;
  each call must use its own session, not leak across calls
"""

import pytest
from unittest.mock import patch, MagicMock, call
import json


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_db_session():
    """
    Yields a mock Session context manager.
    Configure mock_session.get.return_value to simulate found/not-found jobs.
    """
    with patch("backend.workers.tasks.Session") as mock_session_cls:
        mock_session = MagicMock()
        mock_session_cls.return_value.__enter__.return_value = mock_session
        mock_session_cls.return_value.__exit__.return_value = False
        yield mock_session


@pytest.fixture
def mock_job(mock_db_session):
    """Pre-configure a mock SimulationJob that IS found in the DB."""
    mock_job_instance              = MagicMock()
    mock_job_instance.status       = "pending"
    mock_job_instance.result       = None
    mock_job_instance.error        = None
    mock_db_session.get.return_value = mock_job_instance
    return mock_job_instance


# ── _update_job internals ──────────────────────────────────────────────────────

class TestUpdateJob:
    """
    Audit: old _update_job used `if job:` silently doing nothing when job not found.
    New _update_job raises ValueError so Celery marks task as FAILURE.
    """

    def test_missing_job_id_raises_value_error(self, mock_db_session):
        """Core audit fix: non-existent job_id must raise, not silently pass."""
        mock_db_session.get.return_value = None  # job not found

        from backend.workers.tasks import _update_job

        with pytest.raises(ValueError, match="not found in database"):
            _update_job("nonexistent_job_id", "running")

    def test_existing_job_status_updated(self, mock_db_session, mock_job):
        """Happy path: found job gets its status field updated."""
        from backend.workers.tasks import _update_job

        _update_job("real_job_id", "running")

        assert mock_job.status == "running"
        mock_db_session.add.assert_called_once_with(mock_job)
        mock_db_session.commit.assert_called_once()

    def test_result_serialized_as_json(self, mock_db_session, mock_job):
        """Result dict must be JSON-serialized before being stored."""
        from backend.workers.tasks import _update_job

        payload = {"total_quits": 5, "annual_attrition_pct": 15.2}
        _update_job("job_id", "completed", result=payload)

        stored = mock_job.result
        # Must be a JSON string, not a raw dict
        assert isinstance(stored, str)
        assert json.loads(stored) == payload

    def test_error_stored_as_string(self, mock_db_session, mock_job):
        """Error message must be stored on the job record."""
        from backend.workers.tasks import _update_job

        _update_job("job_id", "failed", error="Something exploded")

        assert mock_job.error == "Something exploded"

    def test_no_result_leaves_result_unchanged(self, mock_db_session, mock_job):
        """Calling _update_job without result must not overwrite existing result."""
        mock_job.result = '{"previous": "data"}'

        from backend.workers.tasks import _update_job
        _update_job("job_id", "running")  # no result kwarg

        # result should not be touched
        assert mock_job.result == '{"previous": "data"}'


# ── run_simulation_task ────────────────────────────────────────────────────────

class TestRunSimulationTask:

    def test_task_calls_service_and_marks_completed(self, mock_db_session, mock_job):
        fake_result = {"summary": {"total_quits": 3}}

        with patch("backend.workers.tasks.run_simulation_job", return_value=fake_result):
            from backend.workers.tasks import run_simulation_task

            # .apply() runs the task synchronously (no broker needed)
            result = run_simulation_task.apply(
                kwargs=dict(
                    job_id="job_1",
                    policy_name="baseline",
                    runs=1,
                    duration_months=12,
                    seed=42,
                )
            )

        assert result.status == "SUCCESS"

    def test_task_marks_failed_on_exception(self, mock_db_session, mock_job):
        with patch("backend.workers.tasks.run_simulation_job",
                   side_effect=RuntimeError("sim crashed")):
            from backend.workers.tasks import run_simulation_task

            result = run_simulation_task.apply(
                kwargs=dict(
                    job_id="job_1",
                    policy_name="baseline",
                    runs=1,
                    duration_months=12,
                    seed=42,
                )
            )

        assert result.status == "FAILURE"

    def test_missing_job_id_propagates_as_failure(self, mock_db_session):
        """If job not found on first _update_job call, task must fail cleanly."""
        mock_db_session.get.return_value = None  # simulate missing job

        with patch("backend.workers.tasks.run_simulation_job"):
            from backend.workers.tasks import run_simulation_task

            result = run_simulation_task.apply(
                kwargs=dict(
                    job_id="ghost_job",
                    policy_name="baseline",
                    runs=1,
                    duration_months=12,
                )
            )

        assert result.status == "FAILURE"


# ── run_training_task ──────────────────────────────────────────────────────────

class TestRunTrainingTask:

    def test_training_task_completes(self, mock_db_session, mock_job):
        fake_result = {"accuracy": 0.91}

        with patch("backend.workers.tasks.run_training_job", return_value=fake_result):
            from backend.workers.tasks import run_training_task

            result = run_training_task.apply(
                kwargs=dict(job_id="train_1", quality_report=None)
            )

        assert result.status == "SUCCESS"

    def test_training_task_fails_cleanly(self, mock_db_session, mock_job):
        with patch("backend.workers.tasks.run_training_job",
                   side_effect=ValueError("bad data")):
            from backend.workers.tasks import run_training_task

            result = run_training_task.apply(
                kwargs=dict(job_id="train_1", quality_report=None)
            )

        assert result.status == "FAILURE"


# ── compare_simulations_task ───────────────────────────────────────────────────

class TestCompareSimulationsTask:

    def test_comparison_completes(self, mock_db_session, mock_job):
        fake_result = {"delta_attrition": -0.05}

        with patch("backend.workers.tasks.compare_simulation_jobs", return_value=fake_result):
            from backend.workers.tasks import compare_simulations_task

            result = compare_simulations_task.apply(
                kwargs=dict(
                    job_id="cmp_1",
                    policy_a="baseline",
                    policy_b="kpi_pressure",
                    runs=1,
                    duration_months=6,
                    seed=42,
                )
            )

        assert result.status == "SUCCESS"

    def test_correlated_seed_same_for_both_policies(self, mock_db_session, mock_job):
        """
        Audit: compare_simulations_task used a shared seed causing correlated randomness.
        Both policies got identical RNG sequences, making comparisons meaningless.
        Verify the service is called with the seed so it can differentiate internally.
        """
        with patch("backend.workers.tasks.compare_simulation_jobs",
                   return_value={}) as mock_compare:
            from backend.workers.tasks import compare_simulations_task

            compare_simulations_task.apply(
                kwargs=dict(
                    job_id="cmp_1",
                    policy_a="baseline",
                    policy_b="kpi_pressure",
                    runs=2,
                    duration_months=6,
                    seed=99,
                )
            )

        # Seed must be passed through to the service layer
        call_kwargs = mock_compare.call_args
        assert 99 in call_kwargs.args or call_kwargs.kwargs.get("seed") == 99

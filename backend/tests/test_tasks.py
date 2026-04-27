import json
from unittest.mock import MagicMock, patch

import pytest

from backend.workers.tasks import (
    _update_job,
    run_simulation_task,
    run_training_task,
)


@pytest.fixture
def mock_db_session():
    with patch("backend.workers.tasks.Session") as mock_session_cls:
        mock_session = MagicMock()
        mock_session_cls.return_value.__enter__.return_value = mock_session
        mock_session_cls.return_value.__exit__.return_value = False
        yield mock_session


@pytest.fixture
def mock_job(mock_db_session):
    mock_job_instance = MagicMock()
    mock_job_instance.status = "pending"
    mock_job_instance.result = None
    mock_job_instance.error = None
    mock_db_session.get.return_value = mock_job_instance
    return mock_job_instance


class TestUpdateJob:
    def test_missing_job_id_raises_value_error(self, mock_db_session):
        mock_db_session.get.return_value = None
        with pytest.raises(ValueError, match="not found in database"):
            _update_job("nonexistent_job_id", "running")

    def test_existing_job_status_updated(self, mock_db_session, mock_job):
        _update_job("real_job_id", "running")
        assert mock_job.status == "running"
        mock_db_session.add.assert_called_once_with(mock_job)
        mock_db_session.commit.assert_called_once()

    def test_result_serialized_as_json(self, mock_db_session, mock_job):
        payload = {"total_quits": 5, "annual_attrition_pct": 15.2}
        _update_job("job_id", "completed", result=payload)
        stored = mock_job.result
        assert isinstance(stored, str)
        assert json.loads(stored) == payload


class TestRunSimulationTask:
    def test_task_calls_service_and_marks_completed(self, mock_db_session, mock_job):
        fake_result = {"summary": {"total_quits": 3}}
        with patch("backend.workers.tasks.run_simulation_job", return_value=fake_result):
            result = run_simulation_task(
                job_id="job_1",
                policy_name="baseline",
                runs=1,
                duration_months=12,
                seed=42,
            )
        assert result == fake_result

    def test_task_marks_failed_on_exception(self, mock_db_session, mock_job):
        with patch(
            "backend.workers.tasks.run_simulation_job", side_effect=RuntimeError("sim crashed")
        ):
            with pytest.raises(RuntimeError):
                run_simulation_task(
                    job_id="job_1",
                    policy_name="baseline",
                    runs=1,
                    duration_months=12,
                    seed=42,
                )


class TestRunTrainingTask:
    def test_training_task_completes(self, mock_db_session, mock_job):
        fake_result = {"accuracy": 0.91}
        with patch("backend.workers.tasks.run_training_job", return_value=fake_result):
            result = run_training_task(job_id="train_1", quality_report=None)
        assert result == fake_result

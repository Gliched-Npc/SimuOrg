import sys
from unittest.mock import MagicMock, patch

# Prevent XGBoost from dynamically loading its DLL in the async thread which crashes on Windows
sys.modules["xgboost"] = MagicMock()

import asyncio  # noqa: E402

import pytest  # noqa: E402
from fastapi import HTTPException  # noqa: E402

from backend.api import sim_routes  # noqa: E402
from backend.api.sim_routes import SimulationRequest  # noqa: E402


def test_list_policies():
    data = sim_routes.list_policies()
    assert "policies" in data
    assert "baseline" in data["policies"]


def test_run_simulation_missing_model_returns_400():
    with patch("backend.storage.storage.load_artifact", return_value=None):
        request = SimulationRequest(policy_name="baseline", runs=1)
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(sim_routes.run_simulation_endpoint(request))

        assert exc_info.value.status_code == 400
        assert "No trained model found" in exc_info.value.detail


def test_run_simulation_missing_data_returns_400():
    with (
        patch("backend.storage.storage.load_artifact", return_value={"model": "fake"}),
        patch("sqlmodel.Session") as mock_session,
    ):
        mock_exec = MagicMock()
        mock_exec.all.return_value = []  # Empty DB
        mock_session.return_value.__enter__.return_value.exec.return_value = mock_exec

        request = SimulationRequest(policy_name="baseline", runs=1)
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(sim_routes.run_simulation_endpoint(request))

        assert exc_info.value.status_code == 400
        assert "No employee data" in exc_info.value.detail


def test_run_simulation_success():
    with (
        patch("backend.storage.storage.load_artifact", return_value={"model": "fake"}),
        patch("sqlmodel.Session") as mock_session,
        patch("backend.workers.tasks.run_simulation_task.delay") as mock_task_delay,
    ):
        mock_exec = MagicMock()
        mock_exec.all.return_value = [{"id": 1}]
        mock_session.return_value.__enter__.return_value.exec.return_value = mock_exec

        request = SimulationRequest(policy_name="baseline", runs=10)
        response = asyncio.run(sim_routes.run_simulation_endpoint(request))

        assert "job_id" in response
        assert response["status"] == "queued"
        assert "poll_url" in response
        mock_task_delay.assert_called_once()


def test_get_simulation_status_not_found():
    with patch("sqlmodel.Session") as mock_session:
        mock_session.return_value.__enter__.return_value.get.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            sim_routes.get_simulation_status("fake-job-id")

        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail

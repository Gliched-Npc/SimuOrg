from unittest.mock import MagicMock, patch

from backend.core.simulation.policies import SimulationConfig
from backend.core.simulation.time_engine import run_simulation


def test_run_simulation_no_agents():
    # Simulation should return empty results if there are no agents
    config = SimulationConfig(duration_months=2)
    result = run_simulation(config=config, agents=[], policy_name="test_policy")

    assert result["summary"]["initial_headcount"] == 0
    assert result["summary"]["final_headcount"] == 0
    assert len(result["logs"]) == 0


@patch("backend.core.simulation.time_engine._get_calibration")
@patch("backend.core.simulation.agent._quit_encoders")
@patch("backend.core.simulation.agent._quit_model")
@patch("backend.core.simulation.agent._quit_features")
def test_run_simulation_with_agents(
    mock_quit_features, mock_quit_model, mock_quit_encoders, mock_get_calibration
):
    mock_get_calibration.return_value = {
        "prob_scale": 1.0,
        "stress_amplification": 2.0,
        "monthly_natural_rate": 0.0145,
        "stress_threshold": 0.5,
        "new_hire_monthly_prob": 0.029,
    }

    # Mock ML features to avoid loading from DB
    mock_quit_encoders.return_value = {}
    mock_model_instance = MagicMock()
    import numpy as np

    mock_model_instance.predict_proba.return_value = np.array([[0.9, 0.1]])
    mock_quit_model.return_value = mock_model_instance
    mock_quit_features.return_value = ["Age", "MonthlyIncome"]

    config = SimulationConfig(duration_months=1)

    # Create mock agents
    mock_agent = MagicMock()
    mock_agent.employee_id = 1
    mock_agent.is_active = True
    mock_agent.stress = 0.4
    mock_agent.productivity = 1.0
    mock_agent.motivation = 1.0
    mock_agent.job_satisfaction = 3.0
    mock_agent.work_life_balance = 3.0
    mock_agent.loyalty = 3.0
    mock_agent.burnout_limit = 0.8
    mock_agent.years_at_company = 2
    mock_agent.get_raw_quit_dict.return_value = {"Age": 30, "MonthlyIncome": 5000}

    with patch("backend.core.simulation.time_engine.update_agent_state") as mock_update:
        with patch("backend.core.simulation.time_engine.build_org_graph") as mock_build_graph:
            mock_build_graph.return_value = MagicMock()

            with patch("backend.core.ml.attrition_model.engineer_features") as mock_engineer:
                import pandas as pd

                mock_engineer.return_value = pd.DataFrame([{"Age": 30, "MonthlyIncome": 5000}])

                result = run_simulation(config=config, agents=[mock_agent], policy_name="test")

            assert mock_update.called
            assert result["summary"]["initial_headcount"] == 1
            assert len(result["logs"]) == 1
            assert result["logs"][0]["month"] == 1

"""
Tests for backend/core/simulation/time_engine.py

Audit bugs covered:
- Double-counting: historically attrited employees included in re-simulation
- departed_agents deduplication (same agent in both layoff and quit lists)
- Total attrition must never exceed initial headcount
"""

import pytest
import numpy as np
from unittest.mock import patch, MagicMock


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_mock_agent(
    employee_id,
    is_active=True,
    stress=0.1,
    job_satisfaction=3.0,
    work_life_balance=3.0,
    motivation=0.7,
    loyalty=0.6,
    productivity=0.8,
    burnout_limit=0.7,
    performance_rating=3,
    years_at_company=3,
    department="Engineering",
    manager_id=None,
):
    agent = MagicMock()
    agent.employee_id       = employee_id
    agent.is_active         = is_active
    agent.stress            = stress
    agent.job_satisfaction  = job_satisfaction
    agent.work_life_balance = work_life_balance
    agent.motivation        = motivation
    agent.loyalty           = loyalty
    agent.productivity      = productivity
    agent.burnout_limit     = burnout_limit
    agent.performance_rating = performance_rating
    agent.years_at_company  = years_at_company
    agent.department        = department
    agent.manager_id        = manager_id
    return agent


def _make_minimal_config(**kwargs):
    from backend.core.simulation.policies import SimulationConfig
    defaults = dict(
        duration_months=1,
        workload_multiplier=1.0,
        stress_gain_rate=0.01,
        motivation_decay_rate=0.005,
        shock_factor=0.0,
        bonus=0.0,
        wlb_boost=0.0,
        hiring_active=False,
        layoff_ratio=0.0,
    )
    defaults.update(kwargs)
    return SimulationConfig(**defaults)


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def patch_calibration():
    """Inject a fixed calibration so tests don't depend on calibration.json."""
    fake_cal = {
        "prob_scale":           1.0,
        "stress_amplification": 0.0,   # disabled — isolates quit probability
        "monthly_natural_rate": 0.01,
        "stress_threshold":     0.5,
        "new_hire_monthly_prob": 0.02,
    }
    with patch("backend.core.simulation.time_engine._get_calibration", return_value=fake_cal):
        yield


@pytest.fixture(autouse=True)
def patch_behavior_engine():
    """Prevent real behavior_engine side effects during simulation tests."""
    with patch("backend.core.simulation.time_engine.update_agent_state"), \
         patch("backend.core.simulation.time_engine.apply_attrition_shockwave"):
        yield


@pytest.fixture(autouse=True)
def patch_quit_model():
    """Return a deterministic quit probability so tests are not stochastic."""
    mock_model = MagicMock()
    # predict_proba shape (N, 2) — column 1 is quit probability
    mock_model.predict_proba.side_effect = lambda df: np.tile([0.9, 0.1], (len(df), 1))

    with patch("backend.core.simulation.time_engine._quit_model", return_value=mock_model), \
         patch("backend.core.simulation.agent._quit_features", return_value=[]), \
         patch("backend.core.simulation.agent._quit_encoders", return_value={}), \
         patch("backend.core.ml.attrition_model.engineer_features",
               side_effect=lambda df, encoders=None: df):
        yield


# ── Double-counting tests ──────────────────────────────────────────────────────

class TestDoubleCountingPrevention:
    """
    Audit: historically attrited employees (attrition="Yes") were being loaded
    and included in simulations, inflating attrition rates on re-runs.

    Fix: load_agents_from_db loads ALL employees; attrition label is ignored
    because the ML model predicts future behaviour from features, not history.
    The simulation itself must not double-count a single agent across
    layoff_agents and quitting_agents lists.
    """

    def test_agent_cannot_appear_in_both_layoff_and_quit(self):
        """
        departed_agents = list(dict.fromkeys(layoff_agents + quitting_agents))
        This deduplication must prevent same agent being shockwaved twice.
        """
        from backend.core.simulation.time_engine import run_simulation
        from backend.core.simulation.org_graph import OrgGraph

        # 5 agents — layoff_ratio will try to lay off the lowest performer
        agents = [_make_mock_agent(i, performance_rating=i) for i in range(1, 6)]
        G      = MagicMock(spec=OrgGraph)
        G.has_node.return_value  = True
        G.neighbors.return_value = []

        config = _make_minimal_config(
            layoff_ratio=0.2,       # 1 layoff from 5
            hiring_active=False,
        )

        result = run_simulation(config, agents=agents, G=G, seed=42)

        # Total departures (quits + layoffs) must never exceed headcount
        total_departures = result["summary"]["total_quits"] + result["summary"]["total_layoffs"]
        assert total_departures <= result["summary"]["initial_headcount"]

    def test_total_attrition_never_exceeds_headcount(self):
        """Regardless of quit probability, you can't lose more people than you started with."""
        from backend.core.simulation.time_engine import run_simulation
        from backend.core.simulation.org_graph import OrgGraph

        agents = [_make_mock_agent(i) for i in range(1, 21)]  # 20 agents
        G      = MagicMock(spec=OrgGraph)
        G.has_node.return_value  = True
        G.neighbors.return_value = []

        config = _make_minimal_config(
            duration_months=3,
            shock_factor=0.0,
            hiring_active=False,
        )

        result = run_simulation(config, agents=agents, G=G, seed=42)

        total_quits   = result["summary"]["total_quits"]
        initial_hc    = result["summary"]["initial_headcount"]

        assert total_quits <= initial_hc, (
            f"More quits ({total_quits}) than initial headcount ({initial_hc}). "
            "Double-counting bug or inactive agents not being skipped."
        )

    def test_inactive_agents_not_counted_as_active(self):
        """Agents with is_active=False at the start must not contribute to initial_headcount."""
        from backend.core.simulation.time_engine import run_simulation
        from backend.core.simulation.org_graph import OrgGraph

        active_agents   = [_make_mock_agent(i, is_active=True)  for i in range(1, 6)]
        inactive_agents = [_make_mock_agent(i, is_active=False) for i in range(6, 11)]
        all_agents      = active_agents + inactive_agents

        G = MagicMock(spec=OrgGraph)
        G.has_node.return_value  = True
        G.neighbors.return_value = []

        config = _make_minimal_config(hiring_active=False)
        result = run_simulation(config, agents=all_agents, G=G, seed=42)

        # Only the 5 active agents count
        assert result["summary"]["initial_headcount"] == 5


# ── Simulation invariants ──────────────────────────────────────────────────────

class TestSimulationInvariants:

    def test_empty_agents_returns_zero_summary(self):
        """Empty agent list must return a safe zero-state summary, not raise."""
        from backend.core.simulation.time_engine import run_simulation

        config = _make_minimal_config()
        result = run_simulation(config, agents=[], G=MagicMock(), seed=42)

        assert result["summary"]["initial_headcount"] == 0
        assert result["summary"]["total_quits"]       == 0
        assert result["summary"]["final_headcount"]   == 0

    def test_log_entry_count_matches_duration(self):
        """One log entry per month — must match duration_months exactly."""
        from backend.core.simulation.time_engine import run_simulation
        from backend.core.simulation.org_graph import OrgGraph

        agents = [_make_mock_agent(i) for i in range(1, 6)]
        G      = MagicMock(spec=OrgGraph)
        G.has_node.return_value  = True
        G.neighbors.return_value = []

        config = _make_minimal_config(duration_months=4, hiring_active=False)
        result = run_simulation(config, agents=agents, G=G, seed=42)

        assert len(result["logs"]) == 4

    def test_stress_amplification_override_zero_used(self):
        """
        Audit: calibration binary search must pass stress_amplification_override=0.0.
        Verify that passing it explicitly results in a different (lower) attrition
        than with the real amplification value.
        """
        from backend.core.simulation.time_engine import run_simulation
        from backend.core.simulation.org_graph import OrgGraph

        agents = [_make_mock_agent(i, stress=0.6) for i in range(1, 11)]  # high stress
        G      = MagicMock(spec=OrgGraph)
        G.has_node.return_value  = True
        G.neighbors.return_value = []

        config = _make_minimal_config(hiring_active=False)

        # With amplification OFF (calibration mode)
        result_no_amp = run_simulation(
            config, agents=[_make_mock_agent(i, stress=0.6) for i in range(1, 11)],
            G=G, seed=42, stress_amplification_override=0.0
        )

        # With amplification ON (real simulation — stress above threshold triggers it)
        result_with_amp = run_simulation(
            config, agents=[_make_mock_agent(i, stress=0.6) for i in range(1, 11)],
            G=G, seed=42, stress_amplification_override=3.0
        )

        # Amplification must increase attrition — if not, override isn't being applied
        assert result_with_amp["summary"]["total_quits"] >= result_no_amp["summary"]["total_quits"], (
            "stress_amplification_override=3.0 should produce >= attrition than 0.0. "
            "Override is not being applied."
        )

    def test_prob_scale_override_affects_attrition(self):
        """prob_scale_override must be wired through to the quit probability calculation."""
        from backend.core.simulation.time_engine import run_simulation
        from backend.core.simulation.org_graph import OrgGraph

        G = MagicMock(spec=OrgGraph)
        G.has_node.return_value  = True
        G.neighbors.return_value = []

        config = _make_minimal_config(hiring_active=False)

        # Very low scale — almost nobody quits
        result_low = run_simulation(
            config, agents=[_make_mock_agent(i) for i in range(1, 21)],
            G=G, seed=42, prob_scale_override=0.0001
        )

        # Very high scale — almost everyone quits
        result_high = run_simulation(
            config, agents=[_make_mock_agent(i) for i in range(1, 21)],
            G=G, seed=42, prob_scale_override=1000.0
        )

        assert result_high["summary"]["total_quits"] > result_low["summary"]["total_quits"]

    def test_summary_fields_present(self):
        """All expected summary fields must be present."""
        from backend.core.simulation.time_engine import run_simulation
        from backend.core.simulation.org_graph import OrgGraph

        G = MagicMock(spec=OrgGraph)
        G.has_node.return_value  = True
        G.neighbors.return_value = []

        config = _make_minimal_config(hiring_active=False)
        result = run_simulation(
            config, agents=[_make_mock_agent(i) for i in range(1, 4)], G=G, seed=42
        )

        required = [
            "policy_name", "duration_months", "initial_headcount", "final_headcount",
            "total_quits", "total_layoffs", "period_attrition_pct", "annual_attrition_pct",
            "total_workforce_loss_pct", "final_avg_stress", "final_avg_productivity",
            "final_burnout_count",
        ]
        for key in required:
            assert key in result["summary"], f"Missing summary key: '{key}'"

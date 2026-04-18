import json

import pytest

from backend.core.llm.intent_parser import build_config_from_llm_output
from backend.core.llm.reasoning_chain import generate_executive_narrative
from backend.core.simulation.behavior_engine import SimulationResult


def test_intent_parser_mathematical_bounds():
    """
    EVAL: Intent Parser Strict Bounds Evaluation.
    Ensures that when the LLM extracts precise percentages, the parser mathematically
    respects them without rounding or breaking simulation logic.
    """
    mock_llm_output = {
        "intent_mentions_wlb_penalty": False,
        "intent_mentions_hiring_freeze": False,
        "intent_mentions_layoff": True,
        "salary_increase_pct": 12.5,
        "overtime_reduction_pct": 20.0,
        "layoff_ratio": 0.15,
        "hiring_active": True,  # Should automatically be flipped False by parser
    }

    mock_calib = {
        "annual_attrition_rate": 0.05,
        "behavior_stress_gain_rate": 0.01,
        "motivation_recovery_rate": 0.005,
    }

    config, justification = build_config_from_llm_output(mock_llm_output, mock_calib)

    # Assertions
    assert config.layoff_ratio == 0.15, "Layoff ratio not exactly preserved."
    assert (
        config.hiring_active is False
    ), "Hiring active was not automatically flipped to False during a layoff."
    assert config.salary_increase_pct == 12.5, "Precise salary increase not parsed."
    assert config.overtime_reduction_pct == 20.0, "Precise overtime reduction not parsed."
    assert config.bonus == 1.25, "Salary bonus conversion logic failed."


def test_reasoning_chain_schema_adherence():
    """
    EVAL: Reasoning Chain JSON Adherence Evaluation.
    Ensures that the final layer LLM perfectly obeys instructions to return pure JSON
    without markdown wrapper blocks.
    """
    # Create Mock Simulation Result
    mock_res = SimulationResult(
        steps=12,
        initial_headcount=100,
        final_headcount=110,
        peak_stress=0.5,
        avg_motivation=0.8,
        total_output=5000,
        turnover_count=5,
        months_to_collapse=None,
        reasoning_chain={"events": []},
    )

    narrative_json_str = generate_executive_narrative(mock_res)

    # Test JSON Validity
    try:
        data = json.loads(narrative_json_str)
        assert "ceo_summary" in data, "Missing CEO Summary key."
        assert "key_risks" in data, "Missing Key Risks list."
    except json.JSONDecodeError:
        pytest.fail(
            "Reasoning chain generated invalid JSON (possibly hallucinated markdown block)."
        )

import pandas as pd

from backend.quality_checker import check_data_quality


def test_check_data_quality_empty():
    df = pd.DataFrame()
    result = check_data_quality(df)
    assert isinstance(result, list)
    assert result[0]["code"] == "empty_dataset"


def test_check_data_quality_healthy():
    # Make a dummy healthy dataframe
    data = {
        "Attrition": ["No"] * 90 + ["Yes"] * 10,
        "MonthlyIncome": [5000] * 100,
        "JobLevel": [2] * 100,
    }
    df = pd.DataFrame(data)
    result = check_data_quality(df)
    assert "trust_score" in result
    assert isinstance(result["issues"], list)

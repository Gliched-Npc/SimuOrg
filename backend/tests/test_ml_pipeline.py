from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from backend.core.ml.attrition_model import engineer_features, train_attrition_model
from backend.core.ml.burnout_estimator import burnout_threshold


class TestBurnoutEstimator:
    """Tests the simple linear burnout math."""

    def test_junior_employee(self):
        # Level 1, 1 year experience
        threshold = burnout_threshold(job_level=1, total_working_years=1)
        # 0.3 + (0 * 0.08) + (1 * 0.02) = 0.32
        assert threshold == 0.32

    def test_max_experience_ceiling(self):
        # Level 1, 30 years experience (should cap at 20 years -> 0.40)
        threshold = burnout_threshold(job_level=1, total_working_years=30)
        # 0.3 + 0 + (20 * 0.02) = 0.70
        assert threshold == 0.70

    def test_absolute_max_ceiling(self):
        # Level 8 (if possible), 25 years. 0.3 + 7*0.08 (0.56) + 20*0.02 (0.4) = 1.26 -> clipped to 0.85
        threshold = burnout_threshold(job_level=8, total_working_years=25)
        assert threshold == 0.85


class TestFeatureEngineering:
    """Verifies that the pandas dataframe transformations run properly and compute new columns."""

    @pytest.fixture
    def sample_data(self):
        # Provide base requirements
        return pd.DataFrame(
            [
                {
                    "employee_id": 1,
                    "years_since_last_promotion": 1,
                    "years_at_company": 3,
                    "job_satisfaction": 3,
                    "work_life_balance": 3,
                    "environment_satisfaction": 4,
                    "job_level": 2,
                    "total_working_years": 5,
                    "monthly_income": 4000,
                    "years_with_curr_manager": 2,
                    "department": "Engineering",
                },
                {
                    "employee_id": 2,
                    "years_since_last_promotion": 5,
                    "years_at_company": 5,
                    "job_satisfaction": 1,
                    "work_life_balance": 2,
                    "environment_satisfaction": 1,
                    "job_level": 1,
                    "total_working_years": 5,
                    "monthly_income": 2000,
                    "years_with_curr_manager": 5,
                    "department": "Sales",
                },
            ]
        )

    def test_engineer_features_adds_columns(self, sample_data):
        df_out = engineer_features(sample_data.copy(), encoders=None)

        # Check that new columns were added
        assert "stagnation_score" in df_out.columns
        assert "satisfaction_composite" in df_out.columns
        assert "career_velocity" in df_out.columns
        assert "loyalty_index" in df_out.columns
        assert "income_vs_level" in df_out.columns
        assert "tenure_stability" in df_out.columns
        assert "department_encoded" in df_out.columns

    def test_stagnation_calculation(self, sample_data):
        df_out = engineer_features(sample_data.copy(), encoders=None)

        # Emp 1: 1 / (3 + 1) = 0.25
        assert np.isclose(df_out.loc[0, "stagnation_score"], 0.25)
        # Emp 2: 5 / (5 + 1) = 0.8333
        assert np.isclose(df_out.loc[1, "stagnation_score"], 5 / 6)

    def test_label_encoding_is_consistent(self, sample_data):
        # We simulate training, caching the encoders, then inference
        from backend.core.ml.attrition_model import LABEL_ENCODERS

        df_train = engineer_features(sample_data.copy(), encoders=None)
        # Engineering should have created 'department_encoded' and stored the LabelEncoder
        assert "department_encoded" in LABEL_ENCODERS

        # Now run inference with encoders passed explicitly
        inference_data = pd.DataFrame([{"department": "Engineering"}])
        # Include minimum columns needed for mathematical functions to not crash
        inference_data["years_since_last_promotion"] = 0
        inference_data["years_at_company"] = 0
        inference_data["job_satisfaction"] = 3
        inference_data["work_life_balance"] = 3
        inference_data["environment_satisfaction"] = 3
        inference_data["job_level"] = 1
        inference_data["total_working_years"] = 1
        inference_data["monthly_income"] = 1000
        inference_data["years_with_curr_manager"] = 0

        df_inf = engineer_features(inference_data.copy(), encoders=LABEL_ENCODERS)

        # Engineering -> should map to the same integer as row 0 in train set
        assert df_inf.loc[0, "department_encoded"] == df_train.loc[0, "department_encoded"]

    def test_missing_optional_columns(self):
        # engineer_features shouldn't crash if 'department' is missing entirely
        # (This happens if user dataset didn't have optional features)
        minimal_data = pd.DataFrame(
            [
                {
                    "years_since_last_promotion": 1,
                    "years_at_company": 1,
                    "job_satisfaction": 3,
                    "work_life_balance": 3,
                    "environment_satisfaction": 4,
                    "job_level": 2,
                    "total_working_years": 5,
                    "monthly_income": 4000,
                    "years_with_curr_manager": 2,
                }
            ]
        )

        df_out = engineer_features(minimal_data, encoders=None)
        assert "stagnation_score" in df_out.columns
        assert "department_encoded" not in df_out.columns


class TestModelTrainingEdgeCases:
    """Verifies that the main training pipeline refuses to run on invalid data."""

    def test_raises_single_class(self):
        # Providing a dataset where NO ONE has quit ("No")
        # The model needs both classes to calculate probability.
        base_emp = {
            "attrition": "No",
            "years_since_last_promotion": 1,
            "years_at_company": 1,
            "job_satisfaction": 3,
            "work_life_balance": 3,
            "environment_satisfaction": 3,
            "job_level": 2,
            "total_working_years": 5,
            "monthly_income": 4000,
            "years_with_curr_manager": 2,
            "num_companies_worked": 1,
            "age": 30,
        }
        single_class_df = pd.DataFrame([base_emp for _ in range(10)])

        with patch(
            "backend.core.ml.attrition_model.load_data_from_db", return_value=single_class_df
        ):
            with pytest.raises(ValueError, match="single attrition class"):
                train_attrition_model()

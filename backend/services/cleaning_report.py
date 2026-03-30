# backend/services/cleaning_report.py

from backend.upload import clean_dataframe
import pandas as pd


def generate_cleaning_report(df: pd.DataFrame) -> tuple[pd.DataFrame, int, int, dict, list[str]]:
    """
    Run cleaning pipeline and return cleaning artifacts.
    Returns (cleaned_df, duplicates_removed, junk_removed, null_rates, cleaning_audit)
    """
    return clean_dataframe(df)

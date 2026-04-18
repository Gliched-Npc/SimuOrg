# backend/services/report_service.py

import pandas as pd

from backend.quality_checker import check_data_quality
from backend.schema import build_schema_report
from backend.services.cleaning_report import generate_cleaning_report


def build_upload_report(df: pd.DataFrame, overtime_was_present: bool) -> dict:
    """
    Run cleaning + quality check and return the full report dict.
    Used by both /validate and /dataset endpoints.
    """
    schema_report = build_schema_report(df, overtime_was_present)
    df_clean, duplicates_removed, junk_removed, null_rates, cleaning_audit = (
        generate_cleaning_report(df)
    )
    quality_report = check_data_quality(
        df_clean, duplicates_removed, junk_removed, null_rates, cleaning_audit
    )

    return {
        "df": df_clean,
        "schema_report": schema_report,
        "quality_report": quality_report,
        "duplicates_removed": duplicates_removed,
        "junk_removed": junk_removed,
    }

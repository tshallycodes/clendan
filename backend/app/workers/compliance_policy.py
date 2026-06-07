"""
Compliance Worker — policy model and parse helper.
Imported by compliance.py to keep the main file under 500 lines.
"""
from __future__ import annotations

from pydantic import BaseModel


class _WorkerConfig(BaseModel):
    report_above_minor: int = 1_000_000
    frameworks: str = "AML, KYC"
    aml_monitoring_enabled: bool = True
    ctr_threshold: int = 1_000_000                   # minor units ($10,000) — FinCEN statutory
    structuring_window_hours: int = 24
    structuring_transaction_count_min: int = 3
    structuring_cumulative_threshold: int = 900_000  # minor units ($9,000) — ~10% below CTR
    sar_auto_file_enabled: bool = False              # NEVER auto-file — human review required
    sar_review_queue_enabled: bool = True
    sanctions_refresh_frequency: str = "realtime"   # "realtime" | "daily" | "weekly"
    pep_screening_enabled: bool = True
    adverse_media_screening_enabled: bool = True
    kyc_refresh_standard_days: int = 1825            # 5 years (FATF Rec 10)
    kyc_refresh_high_risk_days: int = 365            # 1 year (FATF Rec 10)
    high_risk_jurisdiction_list_enabled: bool = True
    gdpr_data_retention_days: int = 2555             # 7 years
    gdpr_erasure_aml_hold_check: bool = True
    transaction_monitoring_lookback_days: int = 365
    fatf_occasional_transaction_threshold: int = 1_500_000  # minor units ($15,000)


def _parse_config(config_json: dict) -> _WorkerConfig:
    return _WorkerConfig(
        report_above_minor=config_json.get("report_above_minor", 1_000_000),
        frameworks=config_json.get("frameworks", "AML, KYC"),
        aml_monitoring_enabled=config_json.get("aml_monitoring_enabled", True),
        ctr_threshold=config_json.get("ctr_threshold", 1_000_000),
        structuring_window_hours=config_json.get("structuring_window_hours", 24),
        structuring_transaction_count_min=config_json.get(
            "structuring_transaction_count_min", 3
        ),
        structuring_cumulative_threshold=config_json.get(
            "structuring_cumulative_threshold", 900_000
        ),
        sar_auto_file_enabled=config_json.get("sar_auto_file_enabled", False),
        sar_review_queue_enabled=config_json.get("sar_review_queue_enabled", True),
        sanctions_refresh_frequency=config_json.get(
            "sanctions_refresh_frequency", "realtime"
        ),
        pep_screening_enabled=config_json.get("pep_screening_enabled", True),
        adverse_media_screening_enabled=config_json.get(
            "adverse_media_screening_enabled", True
        ),
        kyc_refresh_standard_days=config_json.get("kyc_refresh_standard_days", 1825),
        kyc_refresh_high_risk_days=config_json.get("kyc_refresh_high_risk_days", 365),
        high_risk_jurisdiction_list_enabled=config_json.get(
            "high_risk_jurisdiction_list_enabled", True
        ),
        gdpr_data_retention_days=config_json.get("gdpr_data_retention_days", 2555),
        gdpr_erasure_aml_hold_check=config_json.get("gdpr_erasure_aml_hold_check", True),
        transaction_monitoring_lookback_days=config_json.get(
            "transaction_monitoring_lookback_days", 365
        ),
        fatf_occasional_transaction_threshold=config_json.get(
            "fatf_occasional_transaction_threshold", 1_500_000
        ),
    )

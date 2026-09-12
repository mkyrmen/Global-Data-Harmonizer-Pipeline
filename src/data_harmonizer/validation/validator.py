"""Formal validation gate.

Replaces the legacy warning-only validator. Every check produces a
PASS/FAIL result; failing any *critical* check marks the pipeline FAILED,
which the runner surfaces as a non-zero exit code.

Checks:
  - dataset is non-empty
  - required canonical columns are present
  - country key is populated and resolved within threshold
  - no unresolved duplicate countries
  - per-column missing ratio within threshold
  - numeric data types for metric columns
  - value ranges (GDP ≥ 0, population ≥ 0, life expectancy 0–120,
    year 1900–2100)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from data_harmonizer.config import HarmonizationConfig
from data_harmonizer.logging_config import get_logger
from data_harmonizer.schemas import (
    CANONICAL_COLUMNS,
    ValidationCheck,
    ValidationReport,
)

logger = get_logger(__name__)

REQUIRED_COLUMNS = CANONICAL_COLUMNS
NUMERIC_COLUMNS = ["gdp", "population", "year", "life_expectancy"]


class ValidationError(Exception):
    """Raised for unexpected validation failures."""


@dataclass
class RangeRule:
    column: str
    minimum: float | None = None
    maximum: float | None = None
    label: str = ""


class Validator:
    def __init__(self, config: HarmonizationConfig | None = None):
        from data_harmonizer.config import default_config

        self.config = config or default_config()
        r = self.config.ranges
        self.range_rules = [
            RangeRule("gdp", r.gdp_min, None, "GDP"),
            RangeRule("population", r.population_min, None, "Population"),
            RangeRule("life_expectancy", r.life_expectancy_min, r.life_expectancy_max, "Life expectancy"),
            RangeRule("year", r.year_min, r.year_max, "Year"),
        ]

    def run(self, df: pd.DataFrame) -> ValidationReport:
        checks: list[ValidationCheck] = []
        self._check_non_empty(df, checks)
        self._check_required_columns(df, checks)
        self._check_country(df, checks)
        self._check_duplicates(df, checks)
        self._check_missing(df, checks)
        self._check_types(df, checks)
        self._check_ranges(df, checks)

        failed = any(not c.passed and c.severity == "critical" for c in checks)
        report = ValidationReport(status="FAIL" if failed else "PASS", checks=checks)
        logger.info("Validation result: %s (%s/%s checks passed)", report.status, report.check_summary()["passed"], len(checks))
        return report

    # ------------------------------------------------------------------
    def _check(self, checks: list[ValidationCheck], code: str, name: str, passed: bool, severity: str, actual: Any = None, limit: Any = None, message: str = ""):
        checks.append(
            ValidationCheck(code=code, name=name, passed=bool(passed), severity=severity, actual=actual, limit=limit, message=message)
        )

    def _check_non_empty(self, df: pd.DataFrame, checks: list[ValidationCheck]):
        self._check(
            checks,
            "NON_EMPTY",
            "Dataset is not empty",
            passed=len(df) > 0,
            severity="critical",
            actual=len(df),
            limit=1,
            message="Dataset contains no rows" if df.empty else "",
        )

    def _check_required_columns(self, df: pd.DataFrame, checks: list[ValidationCheck]):
        missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
        self._check(
            checks,
            "REQUIRED_COLUMNS",
            "All canonical columns present",
            passed=not missing,
            severity="critical",
            actual=missing or "none",
            limit=REQUIRED_COLUMNS,
            message=f"Missing canonical columns: {missing}" if missing else "",
        )

    def _check_country(self, df: pd.DataFrame, checks: list[ValidationCheck]):
        if "country_name" not in df.columns:
            self._check(checks, "COUNTRY_KEY", "Country key populated", passed=False, severity="critical", actual="n/a", limit=0, message="country_name column missing")
            return
        blank = int(df["country_name"].isna().sum())
        threshold = self.config.thresholds.maximum_unresolved_country_percentage
        pct = blank / len(df) * 100 if len(df) else 100.0
        self._check(
            checks,
            "COUNTRY_KEY",
            "Country key populated",
            passed=pct <= threshold,
            severity="critical",
            actual=round(pct, 2),
            limit=f"{threshold}%",
            message=f"{blank} row(s) have no resolved country",
        )

    def _check_duplicates(self, df: pd.DataFrame, checks: list[ValidationCheck]):
        if "country_name" in df.columns:
            dups = int(df.duplicated(subset=["country_name"]).sum())
            threshold = self.config.thresholds.maximum_duplicate_percentage
            pct = dups / len(df) * 100 if len(df) else 0.0
            self._check(
                checks,
                "NO_DUPLICATES",
                "No duplicate countries",
                passed=pct <= threshold,
                severity="critical",
                actual=dups,
                limit=f"{threshold}%",
                message=f"{dups} duplicate country key(s) remain" if dups else "",
            )

    def _check_missing(self, df: pd.DataFrame, checks: list[ValidationCheck]):
        threshold = self.config.thresholds.maximum_missing_percentage
        for col in REQUIRED_COLUMNS:
            if col not in df.columns:
                continue
            missing_pct = df[col].isna().sum() / len(df) * 100 if len(df) else 100.0
            self._check(
                checks,
                f"MISSING_{col.upper()}",
                f"Missing ratio OK ({col})",
                passed=missing_pct <= threshold,
                severity="critical",
                actual=round(missing_pct, 2),
                limit=f"{threshold}%",
                message=f"{col} has {missing_pct:.1f}% missing values" if missing_pct > 0 else "",
            )

    def _check_types(self, df: pd.DataFrame, checks: list[ValidationCheck]):
        for col in NUMERIC_COLUMNS:
            if col not in df.columns:
                continue
            is_numeric = pd.api.types.is_numeric_dtype(df[col])
            self._check(
                checks,
                f"DTYPE_{col.upper()}",
                f"Numeric dtype ({col})",
                passed=is_numeric,
                severity="critical",
                actual=str(df[col].dtype),
                limit="numeric",
                message=f"{col} has non-numeric dtype {df[col].dtype}" if not is_numeric else "",
            )

    def _check_ranges(self, df: pd.DataFrame, checks: list[ValidationCheck]):
        for rule in self.range_rules:
            if rule.column not in df.columns:
                continue
            col = df[rule.column]
            vals = pd.to_numeric(col, errors="coerce")
            invalid = pd.Series(False, index=df.index)
            if rule.minimum is not None:
                invalid |= vals < rule.minimum
            if rule.maximum is not None:
                invalid |= vals > rule.maximum
            bad = int((vals.notna() & invalid).sum())
            self._check(
                checks,
                f"RANGE_{rule.column.upper()}",
                f"Range valid ({rule.column})",
                passed=bad == 0,
                severity="critical",
                actual=bad,
                limit=f"[{rule.minimum if rule.minimum is not None else '-inf'}, {rule.maximum if rule.maximum is not None else 'inf'}]",
                message=f"{bad} out-of-range value(s) in {rule.column}" if bad else "",
            )
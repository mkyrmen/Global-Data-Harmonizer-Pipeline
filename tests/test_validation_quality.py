"""Validation gate and data-quality scoring tests."""

from __future__ import annotations

import pandas as pd

from data_harmonizer.config import default_config
from data_harmonizer.reporting.data_quality import score_dataset
from data_harmonizer.schemas import CANONICAL_COLUMNS
from data_harmonizer.validation.validator import Validator


def _clean_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "country_name": ["UNITED STATES", "GERMANY"],
            "iso_alpha2": ["US", "DE"],
            "iso_alpha3": ["USA", "DEU"],
            "gdp": [23.3, 4.2],
            "population": [331.0, 83.0],
            "year": [2023, 2023],
            "life_expectancy": [77.2, 81.0],
        }
    )


class TestValidator:
    def test_clean_data_passes(self):
        config = default_config()
        report = Validator(config).run(_clean_df())
        assert report.status == "PASS"
        assert all(c.passed for c in report.checks)

    def test_missing_ratio_above_threshold_fails(self):
        config = default_config()
        df = _clean_df()
        df["life_expectancy"] = [None, None]
        report = Validator(config).run(df)
        assert report.status == "FAIL"
        life_checks = [c for c in report.checks if c.code == "MISSING_LIFE_EXPECTANCY"]
        assert life_checks and not life_checks[0].passed

    def test_out_of_range_life_expectancy_fails(self):
        df = _clean_df()
        df["life_expectancy"] = [130.0, 81.0]
        report = Validator(default_config()).run(df)
        assert report.status == "FAIL"
        assert any(not c.passed and c.code == "RANGE_LIFE_EXPECTANCY" for c in report.checks)

    def test_duplicate_countries_fail(self):
        df = _clean_df()
        df.loc[1, "country_name"] = "UNITED STATES"
        report = Validator(default_config()).run(df)
        assert any(not c.passed and c.code == "NO_DUPLICATES" for c in report.checks)


class TestQualityScore:
    def test_perfect_data_scores_high(self):
        score = score_dataset(_clean_df())
        assert score.score >= 95.0

    def test_missing_and_duplicates_reduce_score(self):
        messy = _clean_df()
        messy.loc[0, "gdp"] = None
        messy.loc[0, "population"] = None
        messy.loc[0, "life_expectancy"] = None
        low = score_dataset(messy, duplicates_ratio=0.25, country_resolved_ratio=0.5)
        high = score_dataset(_clean_df(), duplicates_ratio=0.0, country_resolved_ratio=1.0)
        assert low.score < high.score

    def test_scores_are_bounded(self):
        empty = pd.DataFrame(columns=CANONICAL_COLUMNS)
        assert score_dataset(empty).score == 0.0
        assert 0.0 <= score_dataset(pd.DataFrame({"a": [1, 2]})).score <= 100.0
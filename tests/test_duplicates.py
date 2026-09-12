"""Missing-value, duplicate detection and conflict-resolution tests."""

from __future__ import annotations

import pandas as pd

from data_harmonizer.schemas import TransformationType
from data_harmonizer.transformations.duplicates import detect_duplicates, resolve_duplicates
from data_harmonizer.transformations.missing_values import impute_column


class TestMissingValues:
    def test_none_policy_preserves_null(self):
        series = pd.Series([1.0, None, 3.0])
        out, records = impute_column(series, policy="none")
        assert pd.isna(out.iloc[1])
        assert records == []

    def test_constant_imputation_is_audited(self):
        series = pd.Series([1.0, None, 3.0])
        out, records = impute_column(series, policy="constant", fill_value=2023, source_dataset="src", source_column="year")
        assert out.iloc[1] == 2023
        assert len(records) == 1
        assert records[0].transformation_type == TransformationType.MISSING_VALUE
        assert records[0].original_value is None
        assert records[0].transformed_value == 2023


class TestDuplicates:
    def test_detect_duplicate_groups(self):
        df = pd.DataFrame({"country_name": ["A", "A", "B", "C", "C", "C"], "v": [1, 1, 2, 3, 3, 3]})
        groups, rows = detect_duplicates(df, ["country_name"])
        assert groups == 2
        assert rows == 5

    def test_resolve_keeps_first_non_null(self):
        df = pd.DataFrame(
            {"country_name": ["India", "India", "Germany", "Germany"], "gdp": [3.7, 3.7, 4.2, None], "population": [None, 1400, 83, 83]}
        )
        out, _, groups, removed = resolve_duplicates(df, ["country_name"], ["gdp", "population"], policy="keep_first_non_null")
        assert removed == 2
        assert groups == 2
        india = out[out["country_name"] == "India"]
        assert india["population"].iloc[0] == 1400
        germany = out[out["country_name"] == "Germany"]
        assert germany["gdp"].iloc[0] == 4.2

    def test_conflicting_values_flagged(self):
        df = pd.DataFrame({"country_name": ["India", "India"], "gdp": [3.7, 3.9]})
        _, conflicts, _, removed = resolve_duplicates(df, ["country_name"], ["gdp"], policy="keep_first_non_null", source_dataset="merged")
        assert removed == 1
        assert len(conflicts) == 1
        assert conflicts[0].values == [3.7, 3.9]
        assert conflicts[0].selected_value == 3.7
        assert conflicts[0].policy == "keep_first_non_null"

    def test_keep_first_row_policy(self):
        df = pd.DataFrame({"country_name": ["A", "A"], "gdp": [1.0, 2.0]})
        out, _, _, removed = resolve_duplicates(df, ["country_name"], ["gdp"], policy="keep_first_row")
        assert removed == 1
        assert out["gdp"].iloc[0] == 1.0
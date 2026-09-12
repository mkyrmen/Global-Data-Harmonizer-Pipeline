"""Date, numeric and schema transformation tests."""

from __future__ import annotations

import pandas as pd

from data_harmonizer.transformations.dates import extract_year
from data_harmonizer.transformations.numerics import extract_numbers
from data_harmonizer.transformations.schema import detect_role_column


class TestDates:
    def test_messy_date_formats(self):
        series = pd.Series(["2023-01-01", "23/01/2023", "2023.01", "Jan 2023"], name="Year")
        years, records = extract_year(series, "src", "Year")
        assert years.tolist() == [2023, 2023, 2023, 2023]
        assert len(records) == 4
        assert all(r.transformed_value == 2023 for r in records)

    def test_unparseable_is_null_not_invented(self):
        series = pd.Series(["2023", "bogus", "n/a"], name="Year")
        years, _ = extract_year(series, "src", "Year", [])
        assert years.iloc[0] == 2023
        assert pd.isna(years.iloc[1]) and pd.isna(years.iloc[2])

    def test_four_digit_year_scraped_from_arbitrary_text(self):
        series = pd.Series(["reported 2023 fiscal", "FY2024"], name="Year")
        years, _ = extract_year(series, "src", "Year", [])
        assert years.tolist() == [2023, 2024]


class TestNumerics:
    def test_extract_string_embedded_number(self):
        series = pd.Series(["77.2 years", "81.0", "70.1 yrs", "n/a"], name="LE")
        nums, _ = extract_numbers(series, "src", "LE")
        assert nums.tolist()[:3] == [77.2, 81.0, 70.1]
        assert pd.isna(nums.iloc[3])

    def test_range_validation_rejects_impossible_values(self):
        series = pd.Series(["150", "70"], name="LE")
        nums, records = extract_numbers(series, "src", "LE", value_min=0.0, value_max=120.0)
        assert pd.isna(nums.iloc[0])
        assert nums.iloc[1] == 70.0
        assert any(r.transformation_type.value == "RANGE_VIOLATION" for r in records)

    def test_numeric_series_passthrough(self):
        series = pd.Series([23.3, 4.2], dtype=float, name="gdp")
        nums, _ = extract_numbers(series, "src", "gdp", value_min=0.0)
        assert nums.tolist() == [23.3, 4.2]


class TestSchema:
    def test_role_detection(self):
        df = pd.DataFrame({"Country Name": ["USA"], "GDP_2023": [23.3], "Life_Expectancy": ["77"]})
        assert detect_role_column(df, "country_name") == "Country Name"
        assert detect_role_column(df, "gdp") == "GDP_2023"
        assert detect_role_column(df, "life_expectancy") == "Life_Expectancy"

    def test_role_detection_case_insensitive(self):
        df = pd.DataFrame({"country": ["USA"], "population": [10]})
        assert detect_role_column(df, "country_name") == "country"
        assert detect_role_column(df, "population") == "population"
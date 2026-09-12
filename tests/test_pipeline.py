"""End-to-end pipeline tests, including golden-fixture regression."""

from __future__ import annotations

import pandas as pd

from data_harmonizer.ingestion.csv_loader import read_csv
from data_harmonizer.pipeline.harmonizer import Harmonizer
from data_harmonizer.schemas import CANONICAL_COLUMNS, PipelineStatus


def _assert_frames_equal(actual: pd.DataFrame, expected: pd.DataFrame):
    actual = actual.reindex(columns=expected.columns).sort_values("country_name").reset_index(drop=True)
    expected = expected.sort_values("country_name").reset_index(drop=True)
    pd.testing.assert_frame_equal(actual, expected, check_like=True, check_dtype=False, check_exact=False, atol=1e-6)


class TestFullPipeline:
    def test_demo_sources_produce_golden_output(self, source_a_df, source_b_df, golden_expected, harmonizer):
        from data_harmonizer.ingestion.csv_loader import LoadedSource

        a = LoadedSource("source_world_bank", path="source_world_bank.csv", df=source_a_df)
        b = LoadedSource("source_un", path="source_un.csv", df=source_b_df)
        final_df, result = harmonizer.harmonize_sources([a, b])

        assert result.status == PipelineStatus.COMPLETED
        assert result.validation.status == "PASS"
        assert list(final_df.columns) == CANONICAL_COLUMNS

        _assert_frames_equal(final_df, golden_expected)

    def test_quality_score_improves_across_pipeline(self, harmonizer):
        from data_harmonizer.ingestion.csv_loader import LoadedSource

        a = LoadedSource("a", path="a.csv", df=pd.read_csv("raw_data/source_world_bank.csv"))
        b = LoadedSource("b", path="b.csv", df=pd.read_csv("raw_data/source_un.csv"))
        _, result = harmonizer.harmonize_sources([a, b])
        assert result.quality_after.score > result.quality_before.score
        assert 0 <= result.quality_after.score <= 100

    def test_cross_source_metric_conflict_is_detected(self, harmonizer):
        a = pd.DataFrame({"Country Name": ["USA"], "GDP_2023": [3.7], "Population": [1400]})
        b = pd.DataFrame({"Nation": ["United States of America"], "GDP_2023": [3.9]})
        from data_harmonizer.ingestion.csv_loader import LoadedSource

        final_df, result = harmonizer.harmonize_sources(
            [LoadedSource("a", path="a.csv", df=a), LoadedSource("b", path="b.csv", df=b)]
        )
        conflicts = [c for c in result.conflicts if c.field == "gdp"]
        assert len(conflicts) == 1
        assert conflicts[0].values == [3.7, 3.9]
        assert final_df["gdp"].iloc[0] == 3.7
        assert final_df["country_name"].iloc[0] == "UNITED STATES"

    def test_csv_lines_and_reports(self, source_a_df, source_b_df, harmonizer, tmp_path):
        from data_harmonizer.ingestion.csv_loader import LoadedSource
        from data_harmonizer.reporting.report import write_reports

        a = LoadedSource("a", path="a.csv", df=source_a_df)
        b = LoadedSource("b", path="b.csv", df=source_b_df)
        final_df, result = harmonizer.harmonize_sources([a, b])
        assert len(result.transformations) > 0  # lineage is populated
        assert len(result.conflicts) == 0

        csv_path = tmp_path / "harmonized_data.csv"
        final_df.to_csv(csv_path, index=False)
        reloaded = read_csv(csv_path, name="reload")
        assert len(reloaded.df) == 4

        report_paths = write_reports(result, tmp_path / "reports")
        assert (tmp_path / "reports" / "quality_report.json").exists()
        assert (tmp_path / "reports" / "transformation_log.json").exists()
        assert (tmp_path / "reports" / "pipeline_summary.json").exists()
        assert len(report_paths) == 3


class TestSingleSource:
    def test_upload_with_canonical_columns(self, harmonizer):
        df = pd.DataFrame(
            {"Country": ["USA", "Germany"], "gdp": ["23.3", "4.2"], "Population": [331, 83], "Year": ["2023", "Jan 2023"], "Life_Expectancy": ["77.2 years", "81.0"]}
        )
        final_df, result = harmonizer.harmonize_dataframe(df, source_name="upload")
        assert result.validation.status == "PASS"
        assert set(final_df["country_name"]) == {"UNITED STATES", "GERMANY"}
        assert final_df["year"].notna().all()

    def test_imputation_policy_records_lineage(self):
        from data_harmonizer.config import HarmonizationConfig

        cfg = HarmonizationConfig(year_imputation="default", default_year=2023)
        harmonizer = Harmonizer(cfg)
        df = pd.DataFrame({"Country": ["USA"], "Year": ["missing"]})
        final_df, result = harmonizer.harmonize_dataframe(df, source_name="upload")
        assert final_df["year"].iloc[0] == 2023
        imputations = [r for r in result.transformations if r.transformation_type.value == "MISSING_VALUE"]
        assert len(imputations) == 1


def test_legacy_wrappers_still_work(source_a_df, source_b_df, harmonizer):
    a_df, _ = harmonizer.clean_source_a(source_a_df)
    b_df, _ = harmonizer.clean_source_b(source_b_df)
    assert a_df["iso_alpha3"].notna().all()
    assert b_df["life_expectancy"].notna().sum() == 3  # 'n/a' stays null
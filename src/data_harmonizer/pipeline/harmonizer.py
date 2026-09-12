"""The harmonization engine.

Preserves the legacy transformation chain:

    source A (World Bank style)      source B (UN style)
        │  title-case, dedup               │  fuzzy dates -> year
        │  rename to canonical             │  regex numbers -> float
        ▼                                  ▼
        └──────────►  merge on country ◄──┘
            │  case normalization (uppercase canonical entity)
            │  duplicate conflict detection + audited resolution
            │  audited missing-value policy
            ▼
        final canonical dataset + lineage + quality scores + validation

Improvements over the original: configurable country entity resolution
with ISO codes, audited dedup/conflicts instead of silent
``groupby().first()``, audited imputation instead of silent
``fillna(2023)``, formal validation, and a 0–100 quality score computed
from measured dataset characteristics.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from data_harmonizer.config import HarmonizationConfig, default_config
from data_harmonizer.ingestion.csv_loader import LoadedSource
from data_harmonizer.logging_config import get_logger, job_context
from data_harmonizer.reporting.data_quality import DatasetProfile, profile_dataset, score_dataset
from data_harmonizer.schemas import (
    CANONICAL_COLUMNS,
    HarmonizationResult,
    PipelineStatus,
    TransformationRecord,
    TransformationType,
    ValidationReport,
)
from data_harmonizer.transformations.country import CountryResolver
from data_harmonizer.transformations.dates import extract_year
from data_harmonizer.transformations.duplicates import resolve_duplicates
from data_harmonizer.transformations.missing_values import impute_column
from data_harmonizer.transformations.numerics import extract_numbers
from data_harmonizer.transformations.schema import (
    apply_full_row_dedup,
    detect_all_roles,
    ensure_columns,
    rename_columns,
)
from data_harmonizer.validation.validator import Validator

logger = get_logger(__name__)


@dataclass
class CleanedSource:
    """One fully cleaned source dataset ready to merge."""

    df: pd.DataFrame
    records: list[TransformationRecord] = field(default_factory=list)
    exact_duplicates_removed: int = 0
    raw_profile: DatasetProfile | None = None


class Harmonizer:
    """Orchestrates ingestion → profiling → cleaning → harmonization →
    validation for one or more source datasets."""

    def __init__(self, config: HarmonizationConfig | None = None):
        self.config = config or default_config()
        self.resolver = CountryResolver(str(self.config.paths.country_aliases_path))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def harmonize_sources(self, sources: list[LoadedSource]) -> tuple[pd.DataFrame, HarmonizationResult]:
        """Harmonize one or more loaded source datasets into a single
        canonical dataset. Returns ``(final_df, result)``."""
        pipeline_id = uuid.uuid4().hex[:12]
        started = time.perf_counter()
        with job_context(pipeline_id):
            logger.info("Pipeline %s started with %s source(s)", pipeline_id, len(sources))
            cleaned: list[CleanedSource] = []
            before_profiles: list[DatasetProfile] = []
            raw_rows = 0

            for source in sources:
                raw_rows += len(source.df)
                cs = self._clean_source(source)
                cleaned.append(cs)
                if cs.raw_profile is not None:
                    before_profiles.append(cs.raw_profile)

            # Merge all cleaned sources on the canonical key, detecting any
            # cross-source disagreement on shared metric columns.
            conflicts = []
            merged: pd.DataFrame | None = None
            for cs in cleaned:
                if merged is None:
                    merged = cs.df
                else:
                    merged, cross_conflicts = self._merge_source(merged, cs.df)
                    conflicts.extend(cross_conflicts)

            if merged is None:
                merged = pd.DataFrame()

            merged = self._resolve_merge_suffixes(merged)
            merged = ensure_columns(merged, CANONICAL_COLUMNS)
            merged = merged[CANONICAL_COLUMNS]

            total_records: list[TransformationRecord] = []
            for cs in cleaned:
                total_records.extend(cs.records)
            duplicates_removed_clean = sum(c.exact_duplicates_removed for c in cleaned)

            missing_before = int(merged.isna().sum().sum())

            # Audited duplicate / conflict resolution across merged sources.
            value_cols = [c for c in CANONICAL_COLUMNS if c not in ("country_name", "iso_alpha2", "iso_alpha3")]
            final_df, _, _, rows_removed = resolve_duplicates(
                merged,
                key_columns=["country_name"],
                value_columns=value_cols,
                policy=self.config.conflict_policy,
                source_dataset="merged",
                records=total_records,
                conflicts=conflicts,
            )
            total_removed = duplicates_removed_clean + rows_removed
            missing_after = int(final_df.isna().sum().sum())

            # Quality scoring: before = per-source profiles (row-weighted average),
            # after = scored on the actual final dataset.
            quality_before = self._average_profile_score(before_profiles) if before_profiles else score_dataset(merged)
            quality_after = score_dataset(
                final_df,
                conversion_records=[r for r in total_records if r.transformation_type == TransformationType.CONVERSION_ERROR],
                range_records=[r for r in total_records if r.transformation_type == TransformationType.RANGE_VIOLATION],
            )

            # Final case normalization of the entity label.
            final_df = self._uppercase_country(final_df)
            final_df = self._finalize_dtypes(final_df)

            validation: ValidationReport = Validator(self.config).run(final_df)

            # Printable final dataframe (sorted for deterministic output).
            if "country_name" in final_df.columns:
                final_df = final_df.sort_values("country_name").reset_index(drop=True)

            elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
            logger.info(
                "Pipeline %s completed: %s rows -> %s rows, quality %s -> %s (%.2fs)",
                pipeline_id,
                raw_rows,
                len(final_df),
                round(quality_before.score, 1) if quality_before else "?",
                round(quality_after.score, 1),
                elapsed_ms / 1000,
            )

            result = HarmonizationResult(
                pipeline_id=pipeline_id,
                status=PipelineStatus.COMPLETED,
                execution_time_ms=elapsed_ms,
                input_rows=raw_rows,
                output_rows=len(final_df),
                input_columns=list(dict.fromkeys(c for s in sources for c in s.columns)),
                output_columns=list(final_df.columns),
                duplicates_detected=total_removed,
                duplicates_removed=total_removed,
                missing_values_before=missing_before,
                missing_values_after=missing_after,
                conflicts=conflicts,
                transformations=total_records,
                quality_before=quality_before,
                quality_after=quality_after,
                validation=validation,
            )
            return final_df, result

    def harmonize_dataframe(self, df: pd.DataFrame, source_name: str = "uploaded") -> tuple[pd.DataFrame, HarmonizationResult]:
        """Harmonize a single in-memory dataset (single-source path used by
        the web application and the API)."""
        df = df.reset_index(drop=True)
        loaded = LoadedSource(name=source_name, path=source_name, df=df)
        cleaned = self._clean_source(loaded)

        final_df = ensure_columns(cleaned.df, CANONICAL_COLUMNS)
        final_df = final_df[CANONICAL_COLUMNS]

        value_cols = [c for c in CANONICAL_COLUMNS if c not in ("country_name", "iso_alpha2", "iso_alpha3")]
        final_df, conflicts, _, rows_removed = resolve_duplicates(
            final_df,
            key_columns=["country_name"],
            value_columns=value_cols,
            policy=self.config.conflict_policy,
            source_dataset=source_name,
            records=cleaned.records,
        )
        total_removed = cleaned.exact_duplicates_removed + rows_removed
        final_df = self._uppercase_country(final_df)
        final_df = self._finalize_dtypes(final_df)

        before = cleaned.raw_profile.quality_score if cleaned.raw_profile else score_dataset(final_df)
        after = score_dataset(
            final_df,
            conversion_records=[r for r in cleaned.records if r.transformation_type == TransformationType.CONVERSION_ERROR],
            range_records=[r for r in cleaned.records if r.transformation_type == TransformationType.RANGE_VIOLATION],
        )
        validation = Validator(self.config).run(final_df)

        pipeline_id = uuid.uuid4().hex[:12]
        result = HarmonizationResult(
            pipeline_id=pipeline_id,
            status=PipelineStatus.COMPLETED if validation.passed else PipelineStatus.FAILED,
            execution_time_ms=0.0,
            input_rows=len(df),
            output_rows=len(final_df),
            input_columns=list(df.columns),
            output_columns=list(final_df.columns),
            duplicates_detected=total_removed,
            duplicates_removed=total_removed,
            missing_values_before=int(df.isna().sum().sum()),
            missing_values_after=int(final_df.isna().sum().sum()),
            conflicts=conflicts,
            transformations=cleaned.records,
            quality_before=before,
            quality_after=after,
            validation=validation,
        )
        return final_df.sort_values("country_name").reset_index(drop=True), result

    # ------------------------------------------------------------------
    # Legacy-compatible per-source cleaners (preserved entry points)
    # ------------------------------------------------------------------
    def clean_source_a(self, df: pd.DataFrame) -> tuple[pd.DataFrame, list[TransformationRecord]]:
        """World-Bank-style source: case normalization + exact dedup + rename."""
        cs = self._clean_source(LoadedSource("world_bank", path="source_world_bank.csv", df=df))
        return cs.df, cs.records

    def clean_source_b(self, df: pd.DataFrame) -> tuple[pd.DataFrame, list[TransformationRecord]]:
        """UN-style source: messy dates + string-embedded numbers."""
        cs = self._clean_source(LoadedSource("un", path="source_un.csv", df=df))
        return cs.df, cs.records

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _clean_source(self, source: LoadedSource) -> CleanedSource:
        df = source.df.copy()
        records: list[TransformationRecord] = []
        roles = detect_all_roles(df)

        # Raw profile (for the scored "before" state).
        raw_profile = profile_dataset(df, source_dataset=source.name, resolver=self.resolver, country_col=roles["country_name"])

        country_col = roles["country_name"]
        if country_col is None:
            # Fall back to the column that looks most like identifiers.
            object_cols = [c for c in df.columns if df[c].dtype == object or df[c].nunique() >= len(df) * 0.8]
            country_col = max(object_cols, key=lambda c: df[c].nunique()) if object_cols else None

        # 1. Schema mapping: rename known raw columns to canonical names.
        mapping: dict[str, str] = {}
        if country_col is not None:
            mapping[country_col] = "country_name"
        for canonical, raw in roles.items():
            if canonical == "country_name":
                continue
            if raw is not None:
                mapping[raw] = canonical
        df, recs = rename_columns(df, mapping, source_dataset=source.name)
        records.extend(recs)

        # 2. Country entity resolution (+ ISO codes).
        if "country_name" in df.columns:
            resolved, recs = self.resolver.resolve_series(df["country_name"], source.name, country_col or "country_name")
            df = pd.concat([df.drop(columns=["country_name"]), resolved], axis=1)
            records.extend(recs)

        # 3. Numeric extraction + range validation for metric columns.
        for metric in ("gdp", "population", "life_expectancy"):
            if metric in df.columns:
                rng = self._range_for(metric)
                numeric, recs = extract_numbers(
                    df[metric],
                    source_dataset=source.name,
                    source_column=metric,
                    records=records,
                    value_min=rng[0],
                    value_max=rng[1],
                )
                df[metric] = numeric

        # 4. Year extraction + audited imputation policy.
        if "year" in df.columns:
            if not pd.api.types.is_numeric_dtype(df["year"]):
                years, recs = extract_year(df["year"], source.name, "year", records)
                df["year"] = years
            else:
                df["year"] = df["year"].astype("float64")
            if self.config.year_imputation == "default" and self.config.default_year is not None:
                df["year"], _ = impute_column(
                    df["year"],
                    policy="constant",
                    fill_value=float(self.config.default_year),
                    source_dataset=source.name,
                    source_column="year",
                    records=records,
                )
            if df["year"].notna().any():
                df["year"] = df["year"].astype("Int64")

        # 5. Imputation policy for other metrics (default: leave NULL).
        for metric in ("gdp", "population", "life_expectancy"):
            if metric in df.columns and self.config.missing_imputation != "none":
                df[metric], _ = impute_column(
                    df[metric],
                    policy=self.config.missing_imputation,
                    source_dataset=source.name,
                    source_column=metric,
                    records=records,
                )

        # 6. Exact-duplicate rows remove (legacy behaviour, now audited).
        dedup_df, removed = apply_full_row_dedup(df)
        if removed:
            for _ in range(removed):
                records.append(
                    TransformationRecord(
                        source_dataset=source.name,
                        source_column="*",
                        row_index=0,
                        original_value="duplicate row",
                        transformed_value=None,
                        transformation_type=TransformationType.DUPLICATE_RESOLUTION,
                        reason="Exact duplicate row removed",
                    )
                )

        df = ensure_columns(dedup_df, CANONICAL_COLUMNS)
        df = df[CANONICAL_COLUMNS].reset_index(drop=True)
        logger.info("Cleaned source='%s' rows=%s -> %s", source.name, len(source.df), len(df))
        return CleanedSource(df=df, records=records, exact_duplicates_removed=removed, raw_profile=raw_profile)

    def _range_for(self, metric: str) -> tuple[float | None, float | None]:
        ranges = self.config.ranges
        if metric == "gdp":
            return ranges.gdp_min, None
        if metric == "population":
            return ranges.population_min, None
        if metric == "life_expectancy":
            return ranges.life_expectancy_min, ranges.life_expectancy_max
        return None, None

    def _merge_source(self, left: pd.DataFrame, right: pd.DataFrame) -> tuple[pd.DataFrame, list]:
        """Outer-merge two cleaned sources on ``country_name`` and detect
        cross-source disagreements on shared metric columns."""
        from data_harmonizer.schemas import ConflictRecord

        merged = pd.merge(left, right, on="country_name", how="outer", suffixes=("", "_dup"))
        conflicts: list = []
        for col in CANONICAL_COLUMNS:
            dup = f"{col}_dup"
            if dup not in merged.columns:
                continue
            both = merged[col].notna() & merged[dup].notna()
            differs = both & (merged[col] != merged[dup])
            for idx in merged.index[differs]:
                conflicts.append(
                    ConflictRecord(
                        key_field="country_name",
                        key_value=merged.at[idx, "country_name"],
                        field=col,
                        values=[merged.at[idx, col], merged.at[idx, dup]],
                        selected_value=merged.at[idx, col],
                        policy="merge_source_priority",
                        reason="Sources disagreed on the same country metric; first source wins",
                    )
                )
                merged.loc[idx, dup] = None
        return merged, conflicts

    def _resolve_merge_suffixes(self, df: pd.DataFrame) -> pd.DataFrame:
        """Combine duplicated columns produced by the outer merge across all
        canonical fields (not just ISO codes) using first-non-null values."""
        for base in list(df.columns):
            dup = f"{base}_dup"
            if dup not in df.columns:
                continue
            if base in df.columns:
                df[base] = df[base].combine_first(df[dup])
            else:
                df[base] = df[dup]
            df = df.drop(columns=[dup])
        return df

    def _uppercase_country(self, df: pd.DataFrame) -> pd.DataFrame:
        if "country_name" in df.columns:
            df["country_name"] = df["country_name"].astype(str).str.upper().replace({"NAN": None})
        return df

    def _finalize_dtypes(self, df: pd.DataFrame) -> pd.DataFrame:
        for col in ("gdp", "population", "life_expectancy"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
        if "year" in df.columns:
            year = pd.to_numeric(df["year"], errors="coerce")
            if year.notna().all():
                df["year"] = year.astype("int64")
            else:
                df["year"] = year.astype("float64")
        return df

    def _average_profile_score(self, profiles: list[DatasetProfile]) -> Any:
        total_rows = sum(max(1, p.row_count) for p in profiles)
        weighted = sum(p.quality_score.score * max(1, p.row_count) for p in profiles) / total_rows
        dims = {
            "sources": [p.source_dataset for p in profiles],
            "individual_scores": [round(p.quality_score.score, 1) for p in profiles],
        }
        deductions: dict[str, float] = {}
        for p in profiles:
            for k, v in p.quality_score.deductions.items():
                deductions[k] = round(deductions.get(k, 0.0) + v * max(1, p.row_count) / total_rows, 2)
        from data_harmonizer.schemas import QualityScore

        return QualityScore(score=round(weighted, 2), deductions=deductions, dimensions=dims)
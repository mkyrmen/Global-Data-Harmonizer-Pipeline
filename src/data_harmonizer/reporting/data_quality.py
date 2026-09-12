"""Data-quality scoring engine.

Computes a 0–100 score from *measured* dataset characteristics only
(no arbitrary fake values):

    base 100
    − missing-value penalty        (weight 25, overall missing cell ratio)
    − duplicate penalty            (weight 10, duplicate row ratio)
    − unresolved-country penalty   (weight 20, unresolved label ratio)
    − conversion-error penalty     (weight 15, unparseable cell ratio)
    − range-violation penalty      (weight 15, out-of-range cell ratio)
    − schema penalty               (weight 15, missing country column)

Weights live in one place and are included in the report so the score is
fully explained and auditable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from data_harmonizer.logging_config import get_logger
from data_harmonizer.schemas import ColumnProfile, DatasetProfile, QualityScore

logger = get_logger(__name__)

WEIGHTS: dict[str, float] = {
    "missing": 25.0,
    "duplicates": 10.0,
    "unresolved_country": 20.0,
    "conversion": 15.0,
    "range": 15.0,
    "schema": 15.0,
}


@dataclass
class ScoreInput:
    total_cells: int = 0
    missing_cells: int = 0
    duplicates_ratio: float = 0.0
    unresolved_ratio: float = 0.0
    conversion_ratio: float = 0.0
    range_ratio: float = 0.0
    schema_ok: bool = True


def score_dataset(
    df: pd.DataFrame,
    country_resolved_ratio: float | None = None,
    duplicates_ratio: float = 0.0,
    conversion_records: list | None = None,
    range_records: list | None = None,
    denominator_rows: int | None = None,
    schema_missing_country: bool = False,
) -> QualityScore:
    """Compute the 0–100 data-quality score for a DataFrame."""
    if df.empty:
        return QualityScore(score=0.0, deductions={"empty": 100.0}, dimensions={})

    rows, cols = df.shape
    total_cells = rows * cols
    missing_cells = int(df.isna().sum().sum())
    missing_ratio = missing_cells / total_cells if total_cells else 0.0

    denom = denominator_rows if denominator_rows is not None else rows
    conversion_ratio = len(conversion_records or []) / max(1, denom)
    range_ratio = len(range_records or []) / max(1, denom)

    deductions: dict[str, float] = {}
    deductions["missing"] = round(min(missing_ratio, 1.0) * WEIGHTS["missing"], 2)
    deductions["duplicates"] = round(min(duplicates_ratio, 1.0) * WEIGHTS["duplicates"], 2)
    if country_resolved_ratio is not None:
        deductions["unresolved_country"] = round((1.0 - min(country_resolved_ratio, 1.0)) * WEIGHTS["unresolved_country"], 2)
    else:
        deductions["unresolved_country"] = 0.0
    deductions["conversion"] = round(min(conversion_ratio, 1.0) * WEIGHTS["conversion"], 2)
    deductions["range"] = round(min(range_ratio, 1.0) * WEIGHTS["range"], 2)
    deductions["schema"] = round(WEIGHTS["schema"], 2) if schema_missing_country else 0.0

    score = round(max(0.0, 100.0 - sum(deductions.values())), 2)

    dimensions = {
        "rows": rows,
        "columns": cols,
        "missing_cells": missing_cells,
        "missing_ratio": round(missing_ratio, 4),
        "duplicates_ratio": round(duplicates_ratio, 4),
        "country_resolved_ratio": round(country_resolved_ratio, 4) if country_resolved_ratio is not None else None,
        "conversion_errors": len(conversion_records or []),
        "range_violations": len(range_records or []),
    }
    return QualityScore(score=score, deductions=deductions, dimensions=dimensions)


def profile_columns(df: pd.DataFrame) -> list[ColumnProfile]:
    """Column-level statistics for a DataFrame."""
    profiles: list[ColumnProfile] = []
    for col in df.columns:
        series = df[col]
        non_null = int(series.notna().sum())
        missing = int(series.isna().sum())
        total = max(1, len(series))
        numeric = pd.to_numeric(series, errors="coerce") if not pd.api.types.is_numeric_dtype(series) else series
        profiles.append(
            ColumnProfile(
                name=str(col),
                data_type=str(series.dtype),
                non_null_count=non_null,
                missing_count=missing,
                missing_percentage=round(missing / total * 100, 2),
                unique_count=int(series.nunique(dropna=False)),
                min=float(numeric.min()) if numeric.notna().any() else None,
                max=float(numeric.max()) if numeric.notna().any() else None,
                mean=float(numeric.mean()) if numeric.notna().any() else None,
            )
        )
    return profiles


def profile_dataset(
    df: pd.DataFrame,
    source_dataset: str = "",
    resolver: Any = None,
    country_col: str | None = None,
) -> DatasetProfile:
    """Full dataset profile used to score the raw / 'before' state."""
    columns = profile_columns(df)
    issues: list[str] = []

    duplicates_ratio = 0.0
    if country_col is not None and country_col in df.columns:
        mask = df.duplicated(subset=[country_col], keep=False)
        dup_rows = int(mask.sum())
        duplicates_ratio = dup_rows / len(df) if len(df) else 0.0
        if dup_rows:
            issues.append(f"{dup_rows} duplicate key rows detected on '{country_col}'")
    else:
        issues.append("No country column detected — schema mapping required")

    if country_col is None or resolver is None:
        country_resolved_ratio = None
    else:
        labels = df[country_col].dropna()
        resolved = sum(1 for v in labels if resolver.resolve(v)[3])
        country_resolved_ratio = resolved / len(labels) if len(labels) else 0.0
        unresolved = len(labels) - resolved
        if unresolved:
            issues.append(f"{unresolved} country label(s) not resolved to a canonical entity")

    # Estimate conversion failures on object-typed columns.
    conversion_records = []
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            continue
        converted = pd.to_numeric(df[col].astype(str).replace({"nan": np.nan, "None": None, "": None}), errors="coerce")
        conversion_records.extend([1] * int((df[col].notna() & converted.isna()).sum()))
    conversion_ratio = len(conversion_records) / len(df) if len(df) else 0.0
    if conversion_ratio > 0:
        issues.append("Non-numeric strings present in metric columns")

    missing_count = int(df.isna().sum().sum())
    if missing_count:
        issues.append(f"{missing_count} missing cell(s) found")

    q = score_dataset(
        df,
        country_resolved_ratio=country_resolved_ratio,
        duplicates_ratio=duplicates_ratio,
        conversion_records=[1] * len(conversion_records),
        schema_missing_country=(country_col is None),
    )

    return DatasetProfile(
        source_dataset=source_dataset,
        row_count=len(df),
        column_count=len(df.columns),
        duplicate_rows=int(mask.sum()) if country_col and country_col in df.columns else 0,
        columns=columns,
        quality_score=q,
        issues=issues,
    )
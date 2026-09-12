"""Numeric normalization.

Preserves the legacy regex extraction logic (``"77.2 years"`` → ``77.2``,
``"70.1 yrs"`` → ``70.1``, ``"n/a"`` → ``NaN``) but improves it:

- the regex is precompiled and applied vectorized via ``str.extract``,
- already-numeric columns skip extraction entirely,
- value-range validation rejects impossible values (e.g. life expectancy
  outside 0–120) and records a RANGE_VIOLATION lineage event.
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

from data_harmonizer.logging_config import get_logger
from data_harmonizer.schemas import TransformationRecord, TransformationType

logger = get_logger(__name__)

_FIRST_NUMBER_RE = re.compile(r"[-+]?\d*\.\d+|\d+")


def extract_numbers(
    series: pd.Series,
    source_dataset: str = "",
    source_column: str = "",
    records: list[TransformationRecord] | None = None,
    value_min: float | None = None,
    value_max: float | None = None,
) -> tuple[pd.Series, list[TransformationRecord]]:
    """Extract the leading number from messy strings and validate its range.

    Returns ``(numeric_series, records)``. Out-of-range or unparseable
    values become ``NaN`` and produce a lineage record.
    """
    records = records if records is not None else []

    if pd.api.types.is_numeric_dtype(series):
        out = series.astype("float64")
    else:
        as_str = series.astype(str)
        extracted = as_str.str.extract(f"({_FIRST_NUMBER_RE.pattern})")[0]
        out = pd.to_numeric(extracted, errors="coerce")

    # Range validation
    valid_mask = pd.Series(True, index=out.index)
    if value_min is not None:
        valid_mask &= out >= value_min
    if value_max is not None:
        valid_mask &= out <= value_max

    for idx in series.index:
        original = series.at[idx]
        if pd.isna(original):
            continue
        value = out.at[idx]
        if pd.isna(value):
            records.append(
                TransformationRecord(
                    source_dataset=source_dataset,
                    source_column=source_column,
                    row_index=int(idx),
                    original_value=original,
                    transformed_value=None,
                    transformation_type=TransformationType.CONVERSION_ERROR,
                    reason=f"Value '{original}' could not be converted to a number",
                )
            )
            continue
        if not valid_mask.at[idx]:
            records.append(
                TransformationRecord(
                    source_dataset=source_dataset,
                    source_column=source_column,
                    row_index=int(idx),
                    original_value=original,
                    transformed_value=None,
                    transformation_type=TransformationType.RANGE_VIOLATION,
                    reason=f"Value {value} is outside the allowed range "
                    f"[{value_min if value_min is not None else '-inf'}, {value_max if value_max is not None else 'inf'}]",
                )
            )

    out.loc[~valid_mask] = np.nan
    if not pd.api.types.is_numeric_dtype(series):
        for idx in series.index:
            original = series.at[idx]
            if pd.isna(original):
                continue
            value = out.at[idx]
            if pd.notna(value) and str(original).strip() != _clean_already_numeric(value):
                records.append(
                    TransformationRecord(
                        source_dataset=source_dataset,
                        source_column=source_column,
                        row_index=int(idx),
                        original_value=original,
                        transformed_value=value,
                        transformation_type=TransformationType.NUMERIC_CLEANING,
                        reason="String-embedded number extracted to float",
                    )
                )

    return out.astype("float64"), records


def _clean_already_numeric(value: float) -> str:
    text = f"{value:g}"
    return text
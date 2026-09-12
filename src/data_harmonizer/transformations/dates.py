"""Date / year normalization.

Preserves the original fuzzy-parse capability (``2023-01-01``,
``23/01/2023``, ``2023.01`` and ``Jan 2023`` all become ``2023``) while
ensuring that *missing* years are either kept NULL or imputed through an
explicit, audited policy — never silently invented.
"""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

from data_harmonizer.logging_config import get_logger
from data_harmonizer.schemas import TransformationRecord, TransformationType

logger = get_logger(__name__)

_YEAR_RE = re.compile(r"(?<!\d)(?P<year>(?:19|20)\d{2})(?!\d)")


def _parse_years(series: pd.Series) -> pd.Series:
    """Vectorized pandas parsing -> float64 series of years (NaN = unparsed)."""
    values = series.astype(object)
    try:
        parsed = pd.to_datetime(values, errors="coerce", format="mixed")
    except (ValueError, TypeError):
        parsed = pd.to_datetime(values, errors="coerce")
    if parsed is None or len(parsed) == 0:
        return pd.Series([float("nan")] * len(values), index=values.index)
    years = pd.Series(parsed.dt.year, index=values.index).astype("float64")
    return years


def extract_year(
    series: pd.Series,
    source_dataset: str = "",
    source_column: str = "",
    records: list[TransformationRecord] | None = None,
) -> tuple[pd.Series, list[TransformationRecord]]:
    """Parse messy date strings into INTEGER years.

    Pipeline:
      1. pandas ``to_datetime`` fuzzy parsing (covers the demo formats),
      2. regex fallback that greps a 4-digit year out of anything else
         (e.g. ``"reported 2023 fiscal"``).

    Rows that still cannot be parsed become ``NaN`` (never fabricated
    here — imputation is handled separately with full audit).
    """
    records = records if records is not None else []
    raw = series.astype(object)

    year = _parse_years(raw)

    # Regex fallback for anything pandas could not parse.
    fallback_mask = year.isna() & raw.notna()
    if fallback_mask.any():
        extracted = raw[fallback_mask].map(lambda v: _match_year(str(v)))
        year.loc[fallback_mask] = pd.to_numeric(extracted, errors="coerce")

    # Pure numeric-looking years (e.g. '2023') are kept as-is.
    numeric_ok = year.isna() & raw.apply(_looks_like_year)
    if numeric_ok.any():
        year.loc[numeric_ok] = pd.to_numeric(raw[numeric_ok].astype(str).str.replace(",", ""), errors="coerce")

    year = year.astype("float64")

    for idx in raw.index:
        original = raw.at[idx]
        if pd.isna(original):
            continue
        parsed = year.at[idx]
        if pd.isna(parsed):
            logger.debug("Could not extract a year from '%s'", original)
            continue
        records.append(
            TransformationRecord(
                source_dataset=source_dataset,
                source_column=source_column,
                row_index=int(idx),
                original_value=original,
                transformed_value=int(parsed),
                transformation_type=TransformationType.DATE_NORMALIZATION,
                reason="Messy date string normalised to a 4-digit year",
            )
        )

    return year, records


def _match_year(value: str) -> str | None:
    match = _YEAR_RE.search(value)
    return match.group("year") if match else None


def _looks_like_year(value: Any) -> bool:
    if value is None:
        return False
    try:
        as_num = float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return False
    return 1900 <= as_num <= 2100 and abs(as_num - round(as_num)) < 1e-9
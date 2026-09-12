"""Schema mapping / role detection.

Centralizes the mapping between real-world column headers and the
canonical output schema, so column names appear once (in this module)
instead of being scattered across the pipeline.
"""

from __future__ import annotations

import pandas as pd

from data_harmonizer.schemas import TransformationRecord, TransformationType

#: Candidate raw column names for each canonical role, in priority order.
SCHEMA_ROLE_CANDIDATES: dict[str, list[str]] = {
    "country_name": [
        "Country Name",
        "Country",
        "country_name",
        "country",
        "Nation",
        "nation",
        "CountryName",
        "COUNTRY",
    ],
    "year": ["Year", "year", "YYYY", "Year_Reported", "report_year"],
    "gdp": ["GDP_2023", "GDP", "gdp", "GDP (Trillions USD)", "gdp_usd", "gdp_usd_trillions"],
    "population": ["Population", "population", "pop", "population_millions", "Pop"],
    "life_expectancy": [
        "Life_Expectancy",
        "Life Expectancy",
        "life_expectancy",
        "LifeExpectancy",
        "LE",
    ],
}


def detect_role_column(df: pd.DataFrame, role: str) -> str | None:
    """Find the column in ``df`` that best matches ``role``."""
    candidates = SCHEMA_ROLE_CANDIDATES.get(role, [])
    for candidate in candidates:
        for col in df.columns:
            if str(col).strip().lower() == str(candidate).strip().lower():
                return col
    # loose search: contains
    for candidate in candidates:
        needle = str(candidate).lower().replace("_", " ").strip()
        for col in df.columns:
            if needle in str(col).lower().replace("_", " "):
                return col
    return None


def detect_all_roles(df: pd.DataFrame) -> dict[str, str | None]:
    return {role: detect_role_column(df, role) for role in SCHEMA_ROLE_CANDIDATES}


def rename_columns(df: pd.DataFrame, mapping: dict[str, str], source_dataset: str = "") -> tuple[pd.DataFrame, list[TransformationRecord]]:
    """Rename raw columns to canonical names and emit SCHEMA_MAPPING records."""
    records: list[TransformationRecord] = []
    target = df.copy()
    for raw, canonical in mapping.items():
        if raw in target.columns and raw != canonical:
            target = target.rename(columns={raw: canonical})
            for idx in df.index:
                records.append(
                    TransformationRecord(
                        source_dataset=source_dataset,
                        source_column=raw,
                        row_index=int(idx),
                        original_value=df.at[idx, raw],
                        transformed_value=df.at[idx, raw],
                        transformation_type=TransformationType.SCHEMA_MAPPING,
                        reason=f"Column '{raw}' mapped to canonical '{canonical}'",
                    )
                )
    return target, records


def ensure_columns(df: pd.DataFrame, required: list[str]) -> pd.DataFrame:
    """Add any missing canonical columns as all-NULL so merge keys align."""
    for col in required:
        if col not in df.columns:
            df[col] = None
    return df


def apply_full_row_dedup(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Remove exact duplicate rows (legacy behaviour, audited by parent)."""
    before = len(df)
    out = df.drop_duplicates().reset_index(drop=True)
    return out, before - len(out)
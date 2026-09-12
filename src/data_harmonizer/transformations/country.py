"""Country normalization / entity resolution.

Resolves inconsistent country labels (``USA``, ``U.S.A.``, ``United
States of America``, ``America``) to a single canonical entity with ISO
alpha-2 and alpha-3 codes. The alias map is loaded from a configurable
JSON file (``config/country_aliases.json``) rather than hardcoded in code.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd

from data_harmonizer.logging_config import get_logger
from data_harmonizer.schemas import TransformationRecord, TransformationType

logger = get_logger(__name__)

_SPACE_RE = re.compile(r"\s+")


def normalize_label(value: Any) -> str:
    """Normalise a raw label for alias lookup: lowercase, remove
    punctuation/spacing noise while preserving word boundaries."""
    text = str(value).strip().lower()
    text = "".join(ch for ch in text if ch.isalnum() or ch.isspace())
    text = _SPACE_RE.sub(" ", text).strip()
    return text


class CountryResolver:
    """Resolves country labels to canonical entities using a JSON alias map."""

    def __init__(self, aliases_path: str | Path | None = None, aliases: dict[str, Any] | None = None):
        import json

        if aliases is not None:
            data = aliases
        elif aliases_path is not None:
            with open(Path(aliases_path), encoding="utf-8") as fh:
                data = json.load(fh)["canonical"]
        else:
            from data_harmonizer.config import load_country_aliases

            data = load_country_aliases()

        self._canonical: dict[str, dict[str, Any]] = {}
        self._lookup: dict[str, str] = {}  # normalized label -> canonical key

        for key, entry in data.items():
            canonical_name = str(key).upper()
            alpha2 = str(entry.get("iso_alpha2") or "").upper() or None
            alpha3 = str(entry.get("iso_alpha3") or "").upper() or None
            self._canonical[canonical_name] = {"iso_alpha2": alpha2, "iso_alpha3": alpha3}

            keys = [canonical_name]
            keys.extend(str(a) for a in entry.get("aliases", []))
            if alpha2:
                keys.append(alpha2)
            if alpha3:
                keys.append(alpha3)
            for k in keys:
                self._lookup.setdefault(normalize_label(k), canonical_name)

    # ------------------------------------------------------------------
    def resolve(self, value: Any) -> tuple[str, str | None, str | None, bool]:
        """Resolve a single label.

        Returns ``(canonical_name, iso_alpha2, iso_alpha3, resolved)``.
        Unresolved labels keep the normalised uppercase input and count
        against the data-quality score.
        """
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return "", None, None, False
        label = normalize_label(value)
        canonical = self._lookup.get(label)
        if canonical is not None:
            meta = self._canonical[canonical]
            return canonical, meta["iso_alpha2"], meta["iso_alpha3"], True
        return label.upper() if label else "", None, None, False

    # ------------------------------------------------------------------
    def resolve_series(self, series: pd.Series, source_dataset: str = "", source_column: str = "") -> tuple[pd.DataFrame, list[TransformationRecord]]:
        """Vectorized-ish resolution of a country column.

        Returns a DataFrame with ``country_name``, ``iso_alpha2``,
        ``iso_alpha3`` plus per-row lineage records for every change.
        """
        out = pd.DataFrame(index=series.index)
        names: list[str] = []
        a2: list[str | None] = []
        a3: list[str | None] = []
        records: list[TransformationRecord] = []

        for idx, value in series.items():
            name, alpha2, alpha3, resolved = self.resolve(value)
            names.append(name)
            a2.append(alpha2)
            a3.append(alpha3)
            original = series.at[idx]
            if resolved and str(original) != name:
                records.append(
                    TransformationRecord(
                        source_dataset=source_dataset,
                        source_column=source_column,
                        row_index=int(idx),
                        original_value=original,
                        transformed_value=name,
                        transformation_type=TransformationType.COUNTRY_NORMALIZATION,
                        reason=f"Alias '{original}' resolved to canonical entity '{name}'",
                    )
                )

        out["country_name"] = names
        out["iso_alpha2"] = a2
        out["iso_alpha3"] = a3
        return out, records
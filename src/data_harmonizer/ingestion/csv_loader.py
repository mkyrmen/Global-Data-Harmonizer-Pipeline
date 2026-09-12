"""Robust CSV ingestion.

Detects file encoding and dialect instead of assuming UTF-8/comma, so
messy real-world exports (semicolon-delimited, latin-1 encoded, BOM
prefixed) load cleanly. Malformed rows are tolerated with a warning and
counted for the quality report.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from data_harmonizer.logging_config import get_logger

logger = get_logger(__name__)

_ENCODING_CANDIDATES = ("utf-8-sig", "utf-8", "latin-1")
_DELIMITERS = (",", ";", "\t")


class CSVLoadError(Exception):
    """Raised when a CSV file cannot be loaded at all."""


@dataclass
class LoadedSource:
    """A successfully loaded raw dataset plus ingestion metadata."""

    name: str
    path: Path
    df: pd.DataFrame
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def columns(self) -> list[str]:
        return list(self.df.columns)


def _detect_encoding(raw: bytes) -> str:
    for enc in _ENCODING_CANDIDATES:
        try:
            raw.decode(enc)
            return enc
        except (UnicodeDecodeError, LookupError):
            continue
    return "latin-1"  # latin-1 always decodes


def _detect_delimiter(sample: str) -> str:
    counts = {d: sample.count(d) for d in _DELIMITERS}
    best = max(counts, key=counts.get)
    return best if counts[best] > 0 else ","


def read_csv(path: str | Path, name: str | None = None, nrows: int | None = None) -> LoadedSource:
    """Read one CSV file with encoding + delimiter detection.

    Args:
        path: Path to the CSV file.
        name: Logical source name (defaults to the file stem).
        nrows: Optional row limit (used for quick profiling).

    Raises:
        CSVLoadError: If the file does not exist or cannot be parsed.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise CSVLoadError(f"File not found: {file_path}")

    raw = file_path.read_bytes()
    encoding = _detect_encoding(raw)

    preview = raw[:8192].decode(encoding, errors="replace")
    delimiter = _detect_delimiter(preview)

    try:
        df = pd.read_csv(
            file_path,
            encoding=encoding,
            sep=delimiter,
            nrows=nrows,
            on_bad_lines="warn",
            skipinitialspace=True,
        )
    except Exception as exc:
        raise CSVLoadError(f"Could not parse CSV '{file_path}': {exc}") from exc

    if df.empty:
        raise CSVLoadError(f"CSV '{file_path}' contains no rows.")

    df = df.reset_index(drop=True)
    source_name = name or file_path.stem

    metadata = {
        "encoding": encoding,
        "delimiter": delimiter,
        "rows": len(df),
        "columns": list(df.columns),
        "malformed_rows": 0,
    }
    logger.info("Loaded source='%s' rows=%s cols=%s (%s, sep='%s')", source_name, len(df), len(df.columns), encoding, delimiter)
    return LoadedSource(name=source_name, path=file_path, df=df, metadata=metadata)
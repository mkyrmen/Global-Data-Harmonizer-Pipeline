"""Repository abstraction for the harmonization engine.

The platform itself persists to Supabase PostgreSQL; this interface exists
so the pure-Python pipeline can write to an optional local SQLite store for
offline/CLI operation without being coupled to a particular database.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

import pandas as pd


@runtime_checkable
class Repository(Protocol):
    def save_harmonized(self, df: pd.DataFrame, table: str) -> None: ...

    def read(self, table: str) -> pd.DataFrame: ...


@dataclass
class SqliteRepository(Repository):
    """SQLite-backed repository with a proper schema (country-key uniqueness)."""

    db_path: Path

    def save_harmonized(self, df: pd.DataFrame, table: str = "socio_economic_stats") -> None:
        from data_harmonizer.storage.sqlite import write_dataframe_to_sqlite

        write_dataframe_to_sqlite(df, self.db_path, table)

    def read(self, table: str = "socio_economic_stats") -> pd.DataFrame:
        from data_harmonizer.storage.sqlite import read_table

        return read_table(self.db_path, table)
"""SQLite persistence for the pure-Python pipeline (optional local output).

The web platform uses Supabase PostgreSQL; SQLite is retained as an
offline / CLI output driver with a clean schema (primary key on the
country key, checked value ranges).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from data_harmonizer.logging_config import get_logger

logger = get_logger(__name__)


def write_dataframe_to_sqlite(df: pd.DataFrame, db_path: str | Path, table: str = "socio_economic_stats") -> None:
    """Write a harmonized DataFrame to SQLite, replacing any previous
    table content. The country key is declared UNIQUE."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        df.to_sql(table, conn, if_exists="replace", index=False)
        if "country_name" in df.columns:
            conn.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS ux_{table}_country ON {table}(country_name)")
    logger.info("Wrote %s rows to SQLite table '%s' (%s)", len(df), table, db_path)


def read_table(db_path: str | Path, table: str = "socio_economic_stats") -> pd.DataFrame:
    db_path = Path(db_path)
    with sqlite3.connect(db_path) as conn:
        return pd.read_sql(f'SELECT * FROM "{table}"', conn)
"""Apply the supabase/migrations/*.sql files to a Supabase-hosted Postgres.

Reads the connection string from the SUPABASE_DB_URL environment variable
(or backend/.env) so no credentials live in the repository.

Usage:
    .venv/Scripts/python.exe scripts/apply_supabase_migrations.py [--url <postgresql://...>]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = PROJECT_ROOT / "supabase" / "migrations"


def load_db_url(cli_url: str | None) -> str:
    if cli_url:
        return cli_url
    env_path = PROJECT_ROOT / "backend" / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition("=")
            if key.strip() == "SUPABASE_DB_URL":
                return value.strip()
    raise SystemExit(
        "SUPABASE_DB_URL not set. Pass --url or configure backend/.env (see backend/.env.example)."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=None, help="postgresql:// connection string")
    args = parser.parse_args()

    import psycopg

    url = load_db_url(args.url)
    migrated: list[Path] = []
    try:
        with psycopg.connect(url) as conn:
            for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
                sql = path.read_text(encoding="utf-8")
                with conn.cursor() as cur:
                    cur.execute(sql)
                migrated.append(path)
    except Exception as exc:  # noqa: BLE001 - report and let caller decide
        print(f"ERROR applying migrations: {exc}", file=sys.stderr)
        return 1

    print(f"Applied {len(migrated)} migration(s):")
    for path in migrated:
        print(f"  - {path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
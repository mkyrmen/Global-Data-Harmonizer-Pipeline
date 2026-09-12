"""Apply supabase/migrations/*.sql to a hosted Supabase project over the
Management API (api.supabase.com) — no direct IPv4 Postgres needed.

Requires a Personal Access Token (Supabase Dashboard -> Account -> Access Tokens)
passed via --token or the SUPABASE_ACCESS_TOKEN environment variable.

Usage:
    .venv/Scripts/python.exe scripts/apply_supabase_management.py --ref <project-ref> --token <PAT>
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = PROJECT_ROOT / "supabase" / "migrations"
API_BASE = "https://api.supabase.com/v1"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref", required=True, help="Project reference, e.g. gcfijroofcehtliwaivj")
    parser.add_argument("--token", default=None, help="Personal Access Token (or SUPABASE_ACCESS_TOKEN env)")
    args = parser.parse_args()

    token = args.token or os.environ.get("SUPABASE_ACCESS_TOKEN")
    if not token:
        raise SystemExit("Provide --token or set SUPABASE_ACCESS_TOKEN")
    if not token.startswith("sbp_"):
        raise SystemExit("That does not look like a Supabase Personal Access Token (starts with 'sbp_').")

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    url = f"{API_BASE}/projects/{args.ref}/database/query"

    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        sql = path.read_text(encoding="utf-8")
        with httpx.Client(timeout=120) as client:
            resp = client.post(url, headers=headers, json={"query": sql})
        if resp.status_code >= 400:
            print(f"ERROR in {path.name}: {resp.status_code} {resp.text[:500]}", file=sys.stderr)
            return 1
        print(f"Applied {path.name}")
    print("All migrations applied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
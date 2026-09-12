"""Legacy wrapper — validate the most recent harmonized dataset (SQLite or CSV)."""

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from data_harmonizer.config import default_config
from data_harmonizer.storage.sqlite import read_table
from data_harmonizer.validation.validator import Validator


def load_latest(config) -> pd.DataFrame:
    paths = config.effective_paths()
    runs = sorted(paths.processed_data_dir.glob("*/harmonized_data.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    if runs:
        return pd.read_csv(runs[0])
    dbs = sorted(paths.processed_data_dir.glob("*/*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    if dbs:
        return read_table(dbs[0])
    raise FileNotFoundError("No harmonized output found under processed_data/. Run the pipeline first.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default=None, help="Path to a harmonized CSV to audit (otherwise find latest output).")
    args = parser.parse_args()

    config = default_config()
    df = pd.read_csv(args.csv) if args.csv else load_latest(config)

    report = Validator(config).run(df)
    print(f"[AUDIT] Data quality: {report.status}")
    for check in report.checks:
        mark = "[PASS]" if check.passed else "[FAIL]"
        print(f"  {mark} {check.name}: {'PASS' if check.passed else 'FAIL'} (actual={check.actual}, limit={check.limit})")
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
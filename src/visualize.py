"""Legacy wrapper — render the static summary chart from the latest harmonized output."""

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from data_harmonizer.config import default_config
from data_harmonizer.reporting.visualization import render_summary_plot


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default=None, help="Path to harmonized CSV (defaults to latest output).")
    args = parser.parse_args()

    config = default_config()
    if args.csv:
        df = pd.read_csv(args.csv)
    else:
        paths = config.effective_paths()
        runs = sorted(paths.processed_data_dir.glob("*/harmonized_data.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not runs:
            print("[ERROR] No harmonized output found. Run the pipeline first.", file=sys.stderr)
            return 1
        df = pd.read_csv(runs[0])

    out = config.effective_paths().processed("final_analytics_chart.png")
    render_summary_plot(df, out)
    print(f"Chart saved to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
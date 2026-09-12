"""Command-line pipeline runner.

Usage:
    python -m data_harmonizer.pipeline.runner [--input RAW [,RAW...]] [--out DIR]
        [--validate] [--sqlite] [--chart] [--config FILE] [--log-level LEVEL]

Exits with code 0 on success and code 1 when critical validation fails.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from data_harmonizer.config import HarmonizationConfig, default_config
from data_harmonizer.ingestion.csv_loader import CSVLoadError, read_csv
from data_harmonizer.logging_config import get_logger, setup_logging
from data_harmonizer.pipeline.harmonizer import Harmonizer
from data_harmonizer.reporting.report import write_reports, write_summary_md
from data_harmonizer.schemas import HarmonizationResult, PipelineStatus
from data_harmonizer.storage.sqlite import write_dataframe_to_sqlite

logger = get_logger(__name__)

DEFAULT_SOURCES = ["source_world_bank.csv", "source_un.csv"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="data-harmonize",
        description="Global Data Harmonizer — ingest, profile, clean, harmonize and validate multi-source datasets.",
    )
    parser.add_argument("--input", nargs="+", default=None, help="Input CSV files (defaults to the bundled demo sources).")
    parser.add_argument("--names", nargs="+", default=None, help="Logical source names (one per --input).")
    parser.add_argument("--out", default=None, help="Output directory (defaults to processed_data/<pipeline-id>).")
    parser.add_argument("--validate", action="store_true", help="Run the formal validation gate (fails with exit code 1).")
    parser.add_argument("--sqlite", action="store_true", help="Also persist the result to local SQLite.")
    parser.add_argument("--db", default=None, help="SQLite database path (only with --sqlite).")
    parser.add_argument("--chart", action="store_true", help="Render the static summary chart (PNG).")
    parser.add_argument("--config", default=None, help="Optional JSON config file overrides.")
    parser.add_argument("--log-level", default=None, help="Logging level (DEBUG/INFO/WARNING/ERROR).")
    parser.add_argument("--version", action="version", version="global-data-harmonizer 1.0.0")
    return parser


def load_config(args: argparse.Namespace) -> HarmonizationConfig:
    config = default_config()
    if args.config:
        import json

        with open(args.config, encoding="utf-8") as fh:
            overrides = json.load(fh)
        return config.__class__(**{**config.__dict__, **overrides})
    return config


def resolve_sources(args: argparse.Namespace, config: HarmonizationConfig):
    paths = config.paths
    if args.input:
        inputs = [Path(p) for p in args.input]
    else:
        inputs = [paths.raw(name) for name in DEFAULT_SOURCES]
    names = args.names or [p.stem for p in inputs]
    if len(names) != len(inputs):
        names = [p.stem for p in inputs]
    return inputs, names


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = load_config(args)
    paths = config.effective_paths()
    setup_logging(paths.logs_dir, level=args.log_level or config.log_level)

    try:
        inputs, names = resolve_sources(args, config)
        sources = [read_csv(p, name=n) for p, n in zip(inputs, names)]

        harmonizer = Harmonizer(config)
        final_df, result = harmonizer.harmonize_sources(sources)
    except CSVLoadError as exc:
        logger.error("Ingestion failed: %s", exc)
        print(f"[ERROR] {exc}")
        return 2
    except Exception as exc:
        logger.exception("Pipeline crashed")
        print(f"[ERROR] Pipeline crashed: {exc}")
        return 2

    output_dir = Path(args.out) if args.out else paths.processed(result.pipeline_id)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Primary output: canonical CSV
    csv_path = output_dir / "harmonized_data.csv"
    final_df.to_csv(csv_path, index=False)
    result.report_paths["data"] = str(csv_path)

    if args.sqlite:
        db_path = Path(args.db) if args.db else output_dir / "harmonized_data.db"
        write_dataframe_to_sqlite(final_df, db_path)
        result.report_paths["database"] = str(db_path)

    if args.chart:
        try:
            from data_harmonizer.reporting.visualization import render_summary_plot

            chart_path = output_dir / "final_analytics_chart.png"
            render_summary_plot(final_df, chart_path)
            result.report_paths["chart"] = str(chart_path)
        except ImportError:
            logger.warning("--chart requested but matplotlib/seaborn are not installed (pip install -e '.[reporting]')")

    report_paths = write_reports(result, output_dir)
    result.report_paths.update(report_paths)
    write_summary_md(result, output_dir)

    _print_summary(result, final_df)

    if args.validate and result.status == PipelineStatus.FAILED:
        return 1
    if result.status == PipelineStatus.FAILED:
        logger.warning("Pipeline finished but validation failed")
    return 0


def _print_summary(result: HarmonizationResult, df: pd.DataFrame) -> None:
    qb = result.quality_before.score if result.quality_before else float("nan")
    qa = result.quality_after.score if result.quality_after else float("nan")
    v = result.validation
    print("\n=== FINAL CLEANED & HARMONIZED DATASET ===")
    print("=" * 60)
    print(f"Pipeline : {result.pipeline_id}")
    print(f"Status   : {result.status.value}")
    print(f"Rows     : {result.input_rows} -> {result.output_rows}")
    print(f"Duplicates removed      : {result.duplicates_removed}")
    print(f"Conflicts detected      : {len(result.conflicts)}")
    print(f"Missing values (before -> after): {result.missing_values_before} -> {result.missing_values_after}")
    print(f"Quality score (before -> after) : {qb:.1f} -> {qa:.1f} / 100")
    print(f"Validation: {v.status if v else 'n/a'} ({v.check_summary()['passed']}/{len(v.checks)} checks passed)" if v else "")
    print("=" * 60)
    if df.empty:
        print("(no rows)")
        return
    with pd.option_context("display.max_columns", None, "display.width", 120):
        print(df.to_string(index=False))


if __name__ == "__main__":
    sys.exit(main())
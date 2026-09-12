"""Legacy wrapper — run the harmonization pipeline on the demo sources.

Delegates to the refactored ``data_harmonizer`` package.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from data_harmonizer.config import default_config
from data_harmonizer.ingestion.csv_loader import read_csv
from data_harmonizer.logging_config import setup_logging
from data_harmonizer.pipeline.harmonizer import Harmonizer
from data_harmonizer.reporting.report import write_reports, write_summary_md


def main() -> int:
    config = default_config()
    paths = config.effective_paths()
    setup_logging(paths.logs_dir, level=config.log_level)

    sources = [read_csv(paths.raw("source_world_bank.csv"), name="world_bank"), read_csv(paths.raw("source_un.csv"), name="un")]
    harmonizer = Harmonizer(config)
    final_df, result = harmonizer.harmonize_sources(sources)

    output_dir = paths.processed(result.pipeline_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    final_df.to_csv(output_dir / "harmonized_data.csv", index=False)
    write_reports(result, output_dir)
    write_summary_md(result, output_dir)

    print("\n=== FINAL CLEANED & HARMONIZED DATASET ===")
    print(final_df.to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
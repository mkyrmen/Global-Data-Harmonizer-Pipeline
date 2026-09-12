"""Machine-readable + human-readable report generation.

Every pipeline execution can emit:
  - quality_report.json       scores, validation checks, missing/dup stats
  - transformation_log.json   full transformation lineage + conflicts
  - pipeline_summary.json     end-to-end result with timings and metrics
  - pipeline_summary.md       human-readable recap
"""

from __future__ import annotations

import json
from pathlib import Path

from data_harmonizer.logging_config import get_logger
from data_harmonizer.schemas import HarmonizationResult

logger = get_logger(__name__)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, default=str)
    logger.info("Wrote report %s", path)


def write_reports(result: HarmonizationResult, output_dir: Path, job_id: str | None = None) -> dict[str, str]:
    """Write quality_report.json, transformation_log.json and
    pipeline_summary.json. Returns a mapping of logical name -> file path."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    report_paths: dict[str, str] = {}

    summary = result.model_dump(mode="json")
    summary["pipeline_id"] = result.pipeline_id
    summary["job_id"] = job_id
    summary_path = output_dir / "pipeline_summary.json"
    _write_json(summary_path, summary)
    report_paths["summary"] = str(summary_path)

    quality = {
        "pipeline_id": result.pipeline_id,
        "status": result.status.value,
        "quality_before": result.quality_before.model_dump(mode="json") if result.quality_before else None,
        "quality_after": result.quality_after.model_dump(mode="json") if result.quality_after else None,
        "validation": result.validation.model_dump(mode="json") if result.validation else None,
        "input_rows": result.input_rows,
        "output_rows": result.output_rows,
        "duplicates_detected": result.duplicates_detected,
        "duplicates_removed": result.duplicates_removed,
        "missing_values_before": result.missing_values_before,
        "missing_values_after": result.missing_values_after,
    }
    quality_path = output_dir / "quality_report.json"
    _write_json(quality_path, quality)
    report_paths["quality"] = str(quality_path)

    lineage = {
        "pipeline_id": result.pipeline_id,
        "transformations": [r.model_dump(mode="json") for r in result.transformations],
        "conflicts": [c.model_dump(mode="json") for c in result.conflicts],
    }
    log_path = output_dir / "transformation_log.json"
    _write_json(log_path, lineage)
    report_paths["lineage"] = str(log_path)

    return report_paths


def write_summary_md(result: HarmonizationResult, output_dir: Path) -> Path:
    """Write a short human-readable pipeline summary."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    qb = result.quality_before
    qa = result.quality_after
    v = result.validation

    lines = [
        f"# Pipeline Summary — {result.pipeline_id}",
        "",
        f"- **Status:** {result.status.value}",
        f"- **Execution time:** {result.execution_time_ms} ms",
        f"- **Rows:** {result.input_rows} → {result.output_rows}",
        f"- **Duplicates removed:** {result.duplicates_removed}",
        f"- **Conflicts detected:** {len(result.conflicts)}",
        f"- **Quality score:** {(qb.score if qb else 0):.1f} → {(qa.score if qa else 0):.1f} / 100",
        f"- **Validation:** {v.status if v else 'n/a'}",
        "",
        "## Validation checks",
        "",
    ]
    if v:
        lines += ["| Check | Severity | Result | Limit | Actual |", "| --- | --- | --- | --- | --- |"]
        lines += [
            f"| {c.name} | {c.severity} | {'PASS' if c.passed else 'FAIL'} | {c.limit} | {c.actual} |"
            for c in v.checks
        ]
    lines += ["", "## Deductions (quality score)", ""]
    if qa:
        lines += ["| Dimension | Points deducted |", "| --- | --- |", *[f"| {k} | {v} |" for k, v in qa.deductions.items()]]
    lines += [""]

    md_path = output_dir / "pipeline_summary.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Wrote report %s", md_path)
    return md_path
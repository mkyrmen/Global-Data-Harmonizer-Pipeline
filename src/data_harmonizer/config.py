"""Central configuration for the harmonization engine.

Every path is resolved relative to the project root (this repository),
so the engine is fully portable and never depends on a developer's
filesystem layout (no hardcoded absolute paths).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _env_path(env_name: str, default: Path) -> Path:
    override = os.environ.get(env_name)
    return Path(override).expanduser().resolve() if override else default


def _raw(*parts: str) -> Path:
    (PROJECT_ROOT / "raw_data").mkdir(parents=True, exist_ok=True)
    return PROJECT_ROOT / "raw_data" / Path(*parts)


@dataclass(frozen=True)
class ProjectPaths:
    """All filesystem locations used by the engine, project-relative."""

    root: Path = PROJECT_ROOT
    config_dir: Path = PROJECT_ROOT / "config"
    raw_data_dir: Path = PROJECT_ROOT / "raw_data"
    processed_data_dir: Path = PROJECT_ROOT / "processed_data"
    logs_dir: Path = PROJECT_ROOT / "logs"
    country_aliases_path: Path = PROJECT_ROOT / "config" / "country_aliases.json"

    def ensure_dirs(self) -> None:
        for d in (self.processed_data_dir, self.logs_dir, self.raw_data_dir):
            if d is not None:
                d.mkdir(parents=True, exist_ok=True)

    def raw(self, *parts: str) -> Path:
        return self.raw_data_dir.joinpath(*parts)

    def processed(self, *parts: str) -> Path:
        return self.processed_data_dir.joinpath(*parts)


@dataclass(frozen=True)
class ValidationThresholds:
    """Thresholds used by the validation gate. Exceeding a threshold for a
    critical check causes the pipeline to FAIL (non-zero exit code)."""

    maximum_missing_percentage: float = 30.0
    maximum_duplicate_percentage: float = 5.0
    maximum_unresolved_country_percentage: float = 10.0


@dataclass(frozen=True)
class NumericRanges:
    """Sensible value ranges for the canonical numeric fields."""

    gdp_min: float = 0.0
    population_min: float = 0.0
    life_expectancy_min: float = 0.0
    life_expectancy_max: float = 120.0
    year_min: int = 1900
    year_max: int = 2100


@dataclass(frozen=True)
class HarmonizationConfig:
    """Engine-wide configuration. Paths default to project-relative
    directories and can be overridden via environment variables for
    deployment-specific layouts."""

    paths: ProjectPaths = field(default_factory=ProjectPaths)
    thresholds: ValidationThresholds = field(default_factory=ValidationThresholds)
    ranges: NumericRanges = field(default_factory=NumericRanges)

    #: Conflict-resolution policy for duplicated records.
    #: "keep_first_non_null" merges duplicates by first non-null value per
    #: column (matches the legacy grouped aggregation) while auditing every
    #: conflict. "keep_first_row" keeps the first physical row and nulls the rest.
    conflict_policy: str = "keep_first_non_null"

    #: Missing-year policy: "none" preserves NULL, "default" applies
    #: `default_year` AND records a MISSING_VALUE lineage event.
    year_imputation: str = "none"
    default_year: int | None = None

    #: Imputation for other numeric columns ("none" preserves NULL).
    missing_imputation: str = "none"

    log_level: str = "INFO"

    def effective_paths(self) -> ProjectPaths:
        return ProjectPaths(
            root=PROJECT_ROOT,
            config_dir=_env_path("DH_CONFIG_DIR", self.paths.config_dir),
            raw_data_dir=_env_path("DH_RAW_DATA_DIR", self.paths.raw_data_dir),
            processed_data_dir=_env_path("DH_PROCESSED_DATA_DIR", self.paths.processed_data_dir),
            logs_dir=_env_path("DH_LOGS_DIR", self.paths.logs_dir),
            country_aliases_path=_env_path("DH_COUNTRY_ALIASES", self.paths.country_aliases_path),
        )


def default_config() -> HarmonizationConfig:
    return HarmonizationConfig()


def load_country_aliases(path: Path | None = None) -> dict[str, Any]:
    """Load the canonical country alias mapping from a JSON file."""
    p = path or ProjectPaths().country_aliases_path
    with open(p, encoding="utf-8") as fh:
        data = json.load(fh)
    canonical = data.get("canonical", data)
    return {str(k): dict(v) for k, v in canonical.items()}
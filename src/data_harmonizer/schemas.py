"""Typed schemas used across the harmonization engine.

The canonical output schema lives here once and is referenced everywhere
instead of repeating magic column names across the codebase.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Canonical output schema
# ---------------------------------------------------------------------------

CANONICAL_COLUMNS: list[str] = [
    "country_name",
    "iso_alpha2",
    "iso_alpha3",
    "gdp",
    "population",
    "year",
    "life_expectancy",
]

CANONICAL_METRIC_COLUMNS: list[str] = ["gdp", "population", "life_expectancy"]


class TransformationType(str, Enum):
    SCHEMA_MAPPING = "SCHEMA_MAPPING"
    COUNTRY_NORMALIZATION = "COUNTRY_NORMALIZATION"
    CASE_NORMALIZATION = "CASE_NORMALIZATION"
    DATE_NORMALIZATION = "DATE_NORMALIZATION"
    NUMERIC_CLEANING = "NUMERIC_CLEANING"
    MISSING_VALUE = "MISSING_VALUE"
    DUPLICATE_RESOLUTION = "DUPLICATE_RESOLUTION"
    CONVERSION_ERROR = "CONVERSION_ERROR"
    RANGE_VIOLATION = "RANGE_VIOLATION"


class TransformationRecord(BaseModel):
    """One traceable transformation applied to a single cell."""

    source_dataset: str
    source_column: str
    row_index: int
    original_value: Any = None
    transformed_value: Any = None
    transformation_type: TransformationType
    reason: str = ""


class ConflictRecord(BaseModel):
    """A detected disagreement between duplicated records."""

    key_field: str
    key_value: Any
    field: str
    values: list[Any]
    selected_value: Any
    policy: str
    reason: str = ""


class ColumnProfile(BaseModel):
    name: str
    data_type: str
    non_null_count: int
    missing_count: int
    missing_percentage: float
    unique_count: int
    min: Any = None
    max: Any = None
    mean: Any = None


class QualityScore(BaseModel):
    """A data-quality score computed from real dataset characteristics."""

    score: float
    deductions: dict[str, float] = Field(default_factory=dict)
    dimensions: dict[str, Any] = Field(default_factory=dict)


class DatasetProfile(BaseModel):
    source_dataset: str = ""
    row_count: int
    column_count: int
    duplicate_rows: int
    columns: list[ColumnProfile] = Field(default_factory=list)
    quality_score: QualityScore
    issues: list[str] = Field(default_factory=list)


class ValidationCheck(BaseModel):
    code: str
    name: str
    passed: bool
    severity: str  # "critical" | "warning"
    actual: Any = None
    limit: Any = None
    message: str = ""


class ValidationReport(BaseModel):
    status: str  # "PASS" | "FAIL"
    checks: list[ValidationCheck] = Field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.status == "PASS"

    def check_summary(self) -> dict[str, int]:
        return {"passed": sum(c.passed for c in self.checks), "failed": sum(not c.passed for c in self.checks)}


class PipelineStatus(str, Enum):
    COMPLETED = "completed"
    FAILED = "failed"


class HarmonizationResult(BaseModel):
    """Full, reportable result of one pipeline execution."""

    pipeline_id: str
    status: PipelineStatus
    execution_time_ms: float
    input_rows: int
    output_rows: int
    input_columns: list[str] = Field(default_factory=list)
    output_columns: list[str] = Field(default_factory=list)
    duplicates_detected: int = 0
    duplicates_removed: int = 0
    missing_values_before: int = 0
    missing_values_after: int = 0
    conflicts: list[ConflictRecord] = Field(default_factory=list)
    transformations: list[TransformationRecord] = Field(default_factory=list)
    quality_before: QualityScore | None = None
    quality_after: QualityScore | None = None
    validation: ValidationReport | None = None
    report_paths: dict[str, str] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
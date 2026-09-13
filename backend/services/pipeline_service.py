"""Runs the harmonization engine against sources stored in Supabase."""

from __future__ import annotations

import math
import tempfile
from datetime import UTC
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from backend.dependencies import RequestContext, ServiceError, supabase_client_for
from backend.services.storage_client import StorageClient
from data_harmonizer.config import HarmonizationConfig
from data_harmonizer.ingestion.csv_loader import LoadedSource, read_csv
from data_harmonizer.pipeline.harmonizer import Harmonizer
from data_harmonizer.reporting.report import write_reports
from data_harmonizer.schemas import HarmonizationResult, PipelineStatus

JOB_FIELDS = {
    "id", "owner_id", "workspace_id", "name", "config_json", "status",
    "error_message", "created_at", "started_at", "completed_at",
}


def _json_safe(value: Any) -> Any:
    """Recursively convert numpy/pandas scalars and NaN/inf to JSON-safe values."""
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if value is pd.NA or value is None:
        return None
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


class PipelineService:
    def __init__(self, ctx: RequestContext):
        self.ctx = ctx
        self._supabase = supabase_client_for(ctx)
        self._storage = StorageClient(self._supabase, ctx.user_id)

    # ------------------------------------------------------------------
    # uploads
    # ------------------------------------------------------------------
    def upload_source(self, filename: str, content: bytes, workspace_id: str | None) -> dict[str, Any]:
        df = self._parse_csv_bytes(filename, content)
        key = f"source_{filename}"
        storage_path = self._storage.upload_upload_file(content, key)

        preview = df.head(20).fillna("").to_dict(orient="records")
        columns = [str(c) for c in df.columns]
        row = (
            self._supabase.table("raw_sources")
            .insert(
                {
                    "owner_id": self.ctx.user_id,
                    "workspace_id": workspace_id,
                    "name": filename,
                    "storage_path": storage_path,
                    "row_count": len(df),
                    "column_names": columns,
                    "preview_json": preview,
                }
            )
            .execute()
        )
        return row.data[0]

    @staticmethod
    def _parse_csv_bytes(filename: str, content: bytes) -> pd.DataFrame:
        try:
            with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
                tmp.write(content)
                tmp_path = Path(tmp.name)
            try:
                return read_csv(tmp_path, name=filename).df
            finally:
                tmp_path.unlink(missing_ok=True)
        except Exception as exc:
            raise ServiceError(f"Could not parse uploaded file: {exc}", code="INVALID_CSV") from exc

    # ------------------------------------------------------------------
    # harmonization
    # ------------------------------------------------------------------
    def run_job(
        self,
        job_id: str,
        name: str,
        workspace_id: str | None,
        source_ids: list[str],
        config_json: dict[str, Any],
    ) -> dict[str, Any]:
        self._update_job(job_id, started_at=now_iso(), status="running")

        try:
            sources = self._load_sources(source_ids)
            config = self._config_from_dict(config_json)
            final_df, result = Harmonizer(config).harmonize_sources(sources)
            self._assert_pipeline_succeeded(result)

            report_files = self._persist_outputs(job_id, final_df, result)
            row = self._persist_dataset(job_id, workspace_id, final_df, result, report_files)
            summary = self._job_summary(result, final_df, report_files, str(row.id), job_id)
            self._update_job(job_id, status="succeeded", completed_at=now_iso())
            return summary
        except Exception as exc:
            self._update_job(job_id, status="failed", error_message=str(exc), completed_at=now_iso())
            raise ServiceError(f"Harmonization failed: {exc}", code="PIPELINE_FAILED") from exc

    def _load_sources(self, source_ids: list[str]) -> list[LoadedSource]:
        rows = (
            self._supabase.table("raw_sources")
            .select("id, name, storage_path")
            .in_("id", source_ids)
            .eq("owner_id", self.ctx.user_id)
            .order("created_at")
            .execute()
        )
        found = {r["id"]: r for r in rows.data}
        missing = [sid for sid in source_ids if sid not in found]
        if missing:
            raise ServiceError(f"Unknown source id(s): {missing}", code="SOURCE_NOT_FOUND", status_code=404)

        sources: list[LoadedSource] = []
        for meta in found.values():
            content = self._storage.download(meta["storage_path"])
            with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
                tmp.write(content)
                tmp_path = Path(tmp.name)
            try:
                df = read_csv(tmp_path, name=meta["name"]).df
            finally:
                tmp_path.unlink(missing_ok=True)
            sources.append(LoadedSource(meta["name"], path=tmp_path, df=df))
        return sources

    @staticmethod
    def _config_from_dict(data: dict[str, Any]) -> HarmonizationConfig:
        base = HarmonizationConfig()
        if not data:
            return base
        return HarmonizationConfig(
            conflict_policy=data.get("conflict_policy", base.conflict_policy),
            year_imputation=data.get("year_imputation", base.year_imputation),
            default_year=data.get("default_year", base.default_year),
            missing_imputation=data.get("missing_imputation", base.missing_imputation),
        )

    @staticmethod
    def _assert_pipeline_succeeded(result: HarmonizationResult) -> None:
        if result.status != PipelineStatus.COMPLETED:
            raise ServiceError("Pipeline status: " + result.status.value)
        if result.validation and result.validation.status == "FAIL":
            failed = [c.code for c in result.validation.checks if not c.passed]
            raise ServiceError(f"Validation failed: {failed}", code="VALIDATION_FAILED")

    def _persist_outputs(
        self, job_id: str, final_df: pd.DataFrame, result: HarmonizationResult
    ) -> dict[str, str]:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            csv_bytes = final_df.to_csv(index=False).encode("utf-8")
            csv_path = self._storage.upload_output_file(csv_bytes, f"{job_id}/harmonized_data.csv", "text/csv")
            report_files = write_reports(result, tmpdir_path)
            for path in report_files.values():
                file = Path(path)
                content_type = "application/json" if file.suffix == ".json" else "text/markdown"
                self._storage.upload_output_file(file.read_bytes(), f"{job_id}/{file.name}", content_type)
        return {label: f"outputs/{self.ctx.user_id}/{job_id}/{Path(p).name}" for label, p in report_files.items()} | {"csv": csv_path}

    def _persist_dataset(
        self,
        job_id: str,
        workspace_id: str | None,
        final_df: pd.DataFrame,
        result: HarmonizationResult,
        report_files: dict[str, str],
    ) -> Any:
        rows = _json_safe(final_df.to_dict(orient="records"))
        payload = {
            "job_id": job_id,
            "owner_id": self.ctx.user_id,
            "workspace_id": workspace_id,
            "row_count": len(final_df),
            "quality_before": result.quality_before.score if result.quality_before else None,
            "quality_after": result.quality_after.score if result.quality_after else None,
            "validation_status": result.validation.status if result.validation else None,
            "data_json": rows,
            "report_path": report_files.get("quality"),
            "csv_path": report_files.get("csv"),
        }
        inserted = self._supabase.table("harmonized_datasets").insert(payload).execute()
        return inserted.data[0]

    def _job_summary(
        self,
        result: HarmonizationResult,
        final_df: pd.DataFrame,
        report_files: dict[str, str],
        dataset_id: str,
        job_id: str,
    ) -> dict[str, Any]:
        return {
            "job_id": job_id,
            "pipeline_id": result.pipeline_id,
            "status": result.status.value,
            "input_rows": result.input_rows,
            "output_rows": result.output_rows,
            "duplicates_removed": result.duplicates_removed,
            "conflicts": [c.model_dump() for c in result.conflicts],
            "quality_before": result.quality_before.model_dump() if result.quality_before else None,
            "quality_after": result.quality_after.model_dump() if result.quality_after else None,
            "validation": result.validation.check_summary() if result.validation else None,
            "transformation_count": len(result.transformations),
            "columns": list(final_df.columns),
            "outputs": report_files,
            "dataset_id": dataset_id,
        }

    def _update_job(self, job_id: str, **fields: Any) -> None:
        payload = {k: v for k, v in fields.items() if k in JOB_FIELDS}
        if payload:
            self._supabase.table("harmonization_jobs").update(payload).eq("id", job_id).eq("owner_id", self.ctx.user_id).execute()


def now_iso() -> str:
    from datetime import datetime

    return datetime.now(UTC).isoformat()
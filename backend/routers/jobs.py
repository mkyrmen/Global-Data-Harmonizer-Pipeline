"""Jobs routes: run a harmonization job and list/inspect previous runs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from backend.dependencies import RequestContext, ServiceError, current_user, supabase_client_for
from backend.services.pipeline_service import PipelineService

router = APIRouter()

VALID_POLICIES = {"keep_first_non_null", "keep_first_row"}
VALID_IMPUTATIONS = {"none", "default"}
VALID_MISSING = {"none", "mean", "constant"}


class CreateJobBody(BaseModel):
    workspace_id: str | None = None
    name: str = Field(default="Harmonization run", min_length=1)
    source_ids: list[str] = Field(min_length=1)
    config: dict = Field(default_factory=dict)

    @field_validator("source_ids")
    @classmethod
    def unique_sources(cls, v: list[str]) -> list[str]:
        if len(set(v)) != len(v):
            raise ValueError("source_ids must be unique")
        return v


@router.post("/run")
def run_job(body: CreateJobBody, ctx: RequestContext = Depends(current_user)):
    client = supabase_client_for(ctx)
    job = (
        client.table("harmonization_jobs")
        .insert(
            {
                "owner_id": ctx.user_id,
                "workspace_id": body.workspace_id,
                "name": body.name,
                "config_json": body.config,
                "status": "queued",
            }
        )
        .execute()
    )
    job_row = job.data[0]
    client.table("job_sources") \
        .insert([{"job_id": job_row["id"], "source_id": sid, "sort_order": i} for i, sid in enumerate(body.source_ids)]) \
        .execute()
    try:
        return PipelineService(ctx).run_job(
            job_id=job_row["id"],
            name=body.name,
            workspace_id=body.workspace_id,
            source_ids=body.source_ids,
            config_json=body.config,
        )
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("")
def list_jobs(ctx: RequestContext = Depends(current_user)):
    client = supabase_client_for(ctx)
    jobs = client.table("harmonization_jobs").select("*").eq("owner_id", ctx.user_id).order("created_at", desc=True).execute().data
    dataset_ids: dict[str, list] = {}
    for j in jobs:
        ds = client.table("harmonized_datasets").select("id").eq("job_id", j["id"]).eq("owner_id", ctx.user_id).execute()
        dataset_ids[j["id"]] = [d["id"] for d in ds.data]
    return [{**j, "dataset_ids": dataset_ids.get(j["id"], [])} for j in jobs]


@router.get("/{job_id}")
def get_job(job_id: str, ctx: RequestContext = Depends(current_user)):
    client = supabase_client_for(ctx)
    job = client.table("harmonization_jobs").select("*").eq("id", job_id).eq("owner_id", ctx.user_id).maybe_single().execute()
    if not job.data:
        raise HTTPException(status_code=404, detail="Job not found")
    dataset = client.table("harmonized_datasets").select("*").eq("job_id", job_id).eq("owner_id", ctx.user_id).maybe_single().execute()
    return {**job.data[0], "dataset": dataset.data[0] if dataset.data else None}
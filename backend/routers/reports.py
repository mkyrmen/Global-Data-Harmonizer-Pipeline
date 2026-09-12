"""Artifact download routes (harmonized CSV + JSON reports)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from backend.dependencies import RequestContext, current_user, supabase_client_for
from backend.services.storage_client import StorageClient

router = APIRouter()

REPORT_ALIASES = {
    "quality": "quality_report.json",
    "quality_report": "quality_report.json",
    "lineage": "transformation_log.json",
    "transformation_log": "transformation_log.json",
    "summary": "pipeline_summary.json",
    "pipeline_summary": "pipeline_summary.json",
}


def _get_dataset(client, ctx: RequestContext, dataset_id: str) -> dict:
    row = client.table("harmonized_datasets").select("*").eq("id", dataset_id).eq("owner_id", ctx.user_id).maybe_single().execute()
    if not row:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return row.data


@router.get("/{dataset_id}/csv")
def download_csv(dataset_id: str, ctx: RequestContext = Depends(current_user)):
    client = supabase_client_for(ctx)
    dataset = _get_dataset(client, ctx, dataset_id)
    csv_path = dataset.get("csv_path")
    if not csv_path:
        raise HTTPException(status_code=404, detail="No CSV artifact stored for this dataset")
    content = StorageClient(client, ctx.user_id).download(csv_path)
    return Response(content=content, media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="harmonized_data.csv"'})


@router.get("/{dataset_id}/report")
def download_report(dataset_id: str, name: str = Query("quality", pattern="^[a-z_]+$"), ctx: RequestContext = Depends(current_user)):
    client = supabase_client_for(ctx)
    dataset = _get_dataset(client, ctx, dataset_id)
    filename = REPORT_ALIASES.get(name)
    if not filename:
        raise HTTPException(status_code=400, detail=f"Unknown report '{name}'. Use one of: {', '.join(REPORT_ALIASES)}")
    report_path = dataset.get("report_path")
    if not report_path:
        raise HTTPException(status_code=404, detail="No report artifact stored for this dataset")
    content = StorageClient(client, ctx.user_id).download(report_path)
    return Response(content=content, media_type="application/json", headers={"Content-Disposition": f'attachment; filename="{filename}"'})
"""Dataset (raw source) routes: upload, list, detail, delete."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from backend.dependencies import RequestContext, ServiceError, current_user, supabase_client_for
from backend.services.pipeline_service import PipelineService

router = APIRouter()


@router.post("/upload")
async def upload_source(
    file: UploadFile = File(...),
    workspace_id: str | None = Form(None),
    ctx: RequestContext = Depends(current_user),
):
    content = await file.read()
    try:
        return PipelineService(ctx).upload_source(file.filename or "upload.csv", content, workspace_id)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("")
def list_sources(ctx: RequestContext = Depends(current_user)):
    client = supabase_client_for(ctx)
    return client.table("raw_sources").select("*").eq("owner_id", ctx.user_id).order("created_at", desc=True).execute().data


@router.get("/{source_id}")
def get_source(source_id: str, ctx: RequestContext = Depends(current_user)):
    client = supabase_client_for(ctx)
    row = client.table("raw_sources").select("*").eq("id", source_id).eq("owner_id", ctx.user_id).maybe_single().execute()
    if not row.data:
        raise HTTPException(status_code=404, detail="Source not found")
    return row.data[0]


@router.delete("/{source_id}")
def delete_source(source_id: str, ctx: RequestContext = Depends(current_user)):
    client = supabase_client_for(ctx)
    row = client.table("raw_sources").select("*").eq("id", source_id).eq("owner_id", ctx.user_id).maybe_single().execute()
    if not row.data:
        raise HTTPException(status_code=404, detail="Source not found")
    from backend.services.storage_client import StorageClient

    StorageClient(client, ctx.user_id).remove(row.data[0]["storage_path"])
    client.table("raw_sources").delete().eq("id", source_id).eq("owner_id", ctx.user_id).execute()
    return {"deleted": source_id}
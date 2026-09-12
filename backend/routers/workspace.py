"""Workspace routes: list/create workspaces, toggle source inclusion."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.dependencies import RequestContext, current_user, supabase_client_for

router = APIRouter()


class CreateWorkspaceBody(BaseModel):
    name: str = Field(min_length=1)
    description: str = ""


class ToggleSourcesBody(BaseModel):
    sources: list[dict] = Field(default_factory=list)  # [{source_id, include}]


@router.get("")
def list_workspaces(ctx: RequestContext = Depends(current_user)):
    client = supabase_client_for(ctx)
    rows = client.table("workspaces").select("*").eq("owner_id", ctx.user_id).order("created_at").execute()
    return [_with_sources(client, r) for r in rows.data]


@router.post("")
def create_workspace(body: CreateWorkspaceBody, ctx: RequestContext = Depends(current_user)):
    client = supabase_client_for(ctx)
    row = client.table("workspaces").insert({"owner_id": ctx.user_id, "name": body.name, "description": body.description}).execute()
    return _with_sources(client, row.data[0])


@router.get("/{workspace_id}")
def get_workspace(workspace_id: str, ctx: RequestContext = Depends(current_user)):
    client = supabase_client_for(ctx)
    row = client.table("workspaces").select("*").eq("id", workspace_id).eq("owner_id", ctx.user_id).maybe_single().execute()
    if not row.data:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return _with_sources(client, row.data[0])


@router.patch("/{workspace_id}/sources")
def toggle_sources(workspace_id: str, body: ToggleSourcesBody, ctx: RequestContext = Depends(current_user)):
    client = supabase_client_for(ctx)
    owned = client.table("workspaces").select("id").eq("id", workspace_id).eq("owner_id", ctx.user_id).maybe_single().execute()
    if not owned.data:
        raise HTTPException(status_code=404, detail="Workspace not found")

    for entry in body.sources:
        client.table("workspace_sources") \
            .upsert(
                {"workspace_id": workspace_id, "source_id": entry["source_id"], "include": bool(entry.get("include", True))},
                on_conflict="workspace_id,source_id",
            ) \
            .execute()
    return get_workspace(workspace_id, ctx)


def _with_sources(client, workspace: dict) -> dict:
    links = client.table("workspace_sources").select("*").eq("workspace_id", workspace["id"]).order("sort_order").execute()
    source_ids = [l["source_id"] for l in links.data]
    sources = {s["id"]: s for s in _fetch_sources(client, workspace["owner_id"], source_ids)}
    return {
        **workspace,
        "sources": [
            {
                "id": l["source_id"],
                "include": l["include"],
                "sort_order": l["sort_order"],
                **_min_source(sources.get(l["source_id"])),
            }
            for l in links.data
        ],
    }


def _fetch_sources(client, owner_id: str, source_ids: list[str]):
    if not source_ids:
        return []
    rows = client.table("raw_sources").select("*").eq("owner_id", owner_id).in_("id", source_ids).execute()
    return rows.data


def _min_source(source: dict | None) -> dict:
    if not source:
        return {"name": "deleted source"}
    return {
        "name": source["name"],
        "row_count": source["row_count"],
        "column_names": source["column_names"],
        "preview_json": source["preview_json"],
        "created_at": source["created_at"],
    }
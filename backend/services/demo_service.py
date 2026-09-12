"""Demo workspace bootstrap: uploads the two bundled demo CSVs and wires a
workspace with them via the seed_demo_workspace Supabase function."""

from __future__ import annotations

from pathlib import Path

from backend.config import settings
from backend.dependencies import RequestContext, ServiceError, supabase_client_for
from backend.services.storage_client import StorageClient

DEMO_FILES = ("source_world_bank.csv", "source_un.csv")


class DemoService:
    """Builds the demo workspace with user-scoped inserts (no service role
    required), mirroring what the seed_demo_workspace RPC would do."""

    def __init__(self, ctx: RequestContext):
        self.ctx = ctx
        self._client = supabase_client_for(ctx)
        self._storage = StorageClient(self._client, ctx.user_id)

    def ensure_demo_workspace(self) -> dict:
        existing = (
            self._client.table("workspaces")
            .select("id, name")
            .eq("owner_id", self.ctx.user_id)
            .eq("name", "Demo Workspace")
            .execute()
        )
        if existing.data:
            return existing.data[0]

        demo_dir = Path(settings.demo_raw_dir)
        missing = [f for f in DEMO_FILES if not (demo_dir / f).exists()]
        if missing:
            raise ServiceError(f"Demo files missing from {demo_dir}: {missing}", code="DEMO_FILES_MISSING")

        workspace = self._client.table("workspaces").insert(
            {"owner_id": self.ctx.user_id, "name": "Demo Workspace", "description": "Harmonizes the two bundled demo sources."}
        ).execute().data[0]

        for i, name in enumerate(DEMO_FILES):
            content = (demo_dir / name).read_bytes()
            df = self._profile_csv(name, content)
            storage_path = self._storage.upload_upload_file(content, name)
            source = self._client.table("raw_sources").insert(
                {
                    "owner_id": self.ctx.user_id,
                    "workspace_id": workspace["id"],
                    "name": name,
                    "storage_path": storage_path,
                    "row_count": len(df),
                    "column_names": [str(c) for c in df.columns],
                    "preview_json": df.head(20).fillna("").to_dict(orient="records"),
                }
            ).execute().data[0]
            self._client.table("workspace_sources").insert(
                {"workspace_id": workspace["id"], "source_id": source["id"], "include": True, "sort_order": i}
            ).execute()

        return {"id": workspace["id"], "name": workspace["name"]}

    @staticmethod
    def _profile_csv(filename: str, content: bytes):
        import tempfile
        from pathlib import Path as _Path

        from backend.services.pipeline_service import PipelineService

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            tmp.write(content)
            tmp_path = _Path(tmp.name)
        try:
            return PipelineService._parse_csv_bytes(filename, tmp_path.read_bytes())
        finally:
            tmp_path.unlink(missing_ok=True)
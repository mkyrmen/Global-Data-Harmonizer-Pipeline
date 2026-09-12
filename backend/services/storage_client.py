"""Supabase Storage wrapper for uploads and harmonized outputs."""

from __future__ import annotations

from supabase import Client

UPLOADS_BUCKET = "uploads"
OUTPUTS_BUCKET = "outputs"


class StorageClient:
    def __init__(self, client: Client, user_id: str):
        self._client = client
        self._user_id = user_id

    def upload_upload_file(self, data: bytes, key: str, content_type: str = "text/csv") -> str:
        return self._upload(UPLOADS_BUCKET, data, key, content_type)

    def upload_output_file(self, data: bytes, key: str, content_type: str) -> str:
        return self._upload(OUTPUTS_BUCKET, data, key, content_type)

    def _upload(self, bucket: str, data: bytes, key: str, content_type: str) -> str:
        path = f"{self._user_id}/{key}"
        self._client.storage.from_(bucket).upload(path, data, {"content-type": content_type})
        return f"{bucket}/{path}"

    def download(self, storage_path: str) -> bytes:
        bucket, _, path = storage_path.partition("/")
        return self._client.storage.from_(bucket).download(path)

    def remove(self, storage_path: str) -> None:
        bucket, _, path = storage_path.partition("/")
        self._client.storage.from_(bucket).remove([path])
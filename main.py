"""Render/quickstart adapter.

Exposes the FastAPI app at the repo root so Render's Python FastAPI
auto-detection finds an entrypoint (``main:app``). The real app lives in
``backend/main.py``; ``render.yaml``'s startCommand always runs
``uvicorn backend.main:app`` regardless.
"""

from backend.main import app

__all__ = ["app"]
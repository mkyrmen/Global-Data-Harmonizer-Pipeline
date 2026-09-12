"""FastAPI application entry point.

Run locally with:
    uvicorn backend.main:app --reload
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import backend
from backend.config import settings
from backend.routers import auth, datasets, jobs, reports, workspace

VERSION = backend.version()


def create_app() -> FastAPI:
    app = FastAPI(title="Global Data Harmonizer API", version=VERSION, docs_url="/api/docs", openapi_url="/api/openapi.json")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
    app.include_router(workspace.router, prefix="/api/workspaces", tags=["workspaces"])
    app.include_router(datasets.router, prefix="/api/datasets", tags=["datasets"])
    app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
    app.include_router(reports.router, prefix="/api/reports", tags=["reports"])

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": VERSION, "supabase_configured": str(bool(settings.configured))}

    @app.get("/health")
    def health_root() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/")
    def root() -> dict[str, str]:
        return {"status": "ok", "service": "global-data-harmonizer-api", "docs": "/api/docs"}

    return app


app = create_app()
"""Environment-driven settings for the backend."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Load backend/.env (gitignored) so local runs work without exporting vars.
_load_dotenv_path = Path(__file__).resolve().parent / ".env"
if _load_dotenv_path.exists():
    load_dotenv(_load_dotenv_path)


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


@dataclass(frozen=True)
class Settings:
    supabase_url: str = field(default_factory=lambda: _env("SUPABASE_URL"))
    supabase_anon_key: str = field(default_factory=lambda: _env("SUPABASE_ANON_KEY"))
    supabase_jwt_secret: str = field(default_factory=lambda: _env("SUPABASE_JWT_SECRET"))

    cors_origins: list[str] = field(
        default_factory=lambda: [
            o.strip()
            for o in _env("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
            if o.strip()
        ]
    )

    demo_raw_dir: Path = field(default_factory=lambda: _env("DH_RAW_DATA_DIR") and Path(_env("DH_RAW_DATA_DIR")) or (_PROJECT_ROOT / "raw_data"))

    @property
    def configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_anon_key and self.supabase_jwt_secret)


settings = Settings()
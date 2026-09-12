"""Backend unit tests that do not require a live Supabase instance."""

from __future__ import annotations

import jwt
import pytest

from backend.config import Settings
from backend.dependencies import _decode_user_id
from backend.services.pipeline_service import PipelineService

SECRET = "super-secret-jwt-key-for-testing-only-0123456789abcdef"


class TestJwtSecurity:
    def _settings(self) -> Settings:
        return Settings(
            supabase_url="https://example.supabase.co", supabase_anon_key="anon", supabase_jwt_secret=SECRET
        )

    def test_valid_token_decodes_user_id(self):
        token = jwt.encode({"sub": "user-123", "aud": "authenticated", "exp": 9999999999}, SECRET, algorithm="HS256")
        assert _decode_user_id(token, self._settings()) == "user-123"

    def test_expired_token_rejected(self):
        token = jwt.encode({"sub": "user-123", "aud": "authenticated", "exp": 1}, SECRET, algorithm="HS256")
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            _decode_user_id(token, self._settings())
        assert exc.value.status_code == 401

    def test_wrong_secret_rejected(self):
        token = jwt.encode(
            {"sub": "user-123", "aud": "authenticated", "exp": 9999999999},
            "another-secret-that-is-also-at-least-32-bytes-long",
            algorithm="HS256",
        )
        from fastapi import HTTPException

        with pytest.raises(HTTPException):
            _decode_user_id(token, self._settings())

    def test_unconfigured_backend_rejected(self, monkeypatch):
        from fastapi import HTTPException

        for var in ("SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_JWT_SECRET"):
            monkeypatch.delenv(var, raising=False)
        cfg = Settings()
        assert not cfg.configured
        with pytest.raises(HTTPException) as exc:
            _decode_user_id("anything", cfg)
        assert exc.value.status_code == 500


class TestConfigMapping:
    def test_default_when_empty(self):
        cfg = PipelineService._config_from_dict({})
        assert cfg.year_imputation == "none"
        assert cfg.missing_imputation == "none"
        assert cfg.conflict_policy == "keep_first_non_null"

    def test_override_mapping(self):
        cfg = PipelineService._config_from_dict(
            {"year_imputation": "default", "default_year": 2024, "missing_imputation": "mean", "conflict_policy": "keep_first_row"}
        )
        assert cfg.year_imputation == "default"
        assert cfg.default_year == 2024
        assert cfg.missing_imputation == "mean"
        assert cfg.conflict_policy == "keep_first_row"
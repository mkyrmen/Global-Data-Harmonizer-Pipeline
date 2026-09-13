"""Backend unit tests that do not require a live Supabase instance."""

from __future__ import annotations

import base64
from datetime import UTC, datetime

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec

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


def _p256_keypair():
    private = ec.generate_private_key(ec.SECP256R1())
    numbers = private.public_key().public_numbers()
    b64u = lambda i: base64.urlsafe_b64encode(i.to_bytes(32, "big")).rstrip(b"=").decode()
    jwk = {
        "kty": "EC",
        "crv": "P-256",
        "kid": "test-kid-1",
        "x": b64u(numbers.x),
        "y": b64u(numbers.y),
    }
    return private, jwk


class TestJwtEs256:
    def _settings(self) -> Settings:
        return Settings(
            supabase_url="https://example.supabase.co", supabase_anon_key="anon", supabase_jwt_secret=SECRET
        )

    def _es256_token(self, private_key, sub: str = "user-es256", kid: str = "test-kid-1") -> str:
        now = int(datetime.now(UTC).timestamp())
        return jwt.encode(
            {"sub": sub, "aud": "authenticated", "role": "authenticated", "iat": now, "exp": now + 3600},
            private_key,
            algorithm="ES256",
            headers={"kid": kid},
        )

    def test_es256_token_verified_via_jwks(self, monkeypatch):
        private, jwk = _p256_keypair()
        import backend.dependencies as deps

        monkeypatch.setattr(deps, "_jwks_keys", lambda cfg, force=False: [jwk])
        token = self._es256_token(private)
        assert _decode_user_id(token, self._settings()) == "user-es256"

    def test_es256_wrong_key_rejected(self, monkeypatch):
        _, jwk = _p256_keypair()
        private_bad, _ = _p256_keypair()
        import backend.dependencies as deps

        monkeypatch.setattr(deps, "_jwks_keys", lambda cfg, force=False: [jwk])
        token = self._es256_token(private_bad)
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            _decode_user_id(token, self._settings())
        assert exc.value.status_code == 401

    def test_es256_candidate_refresh_on_miss(self, monkeypatch):
        private, jwk = _p256_keypair()
        import backend.dependencies as deps

        # First fetch (kid mismatch) returns empty JWKS; refresh supplies the key.
        def first_fetch(cfg, force=False):
            return [jwk] if force else [{"kty": "EC", "crv": "P-256", "kid": "old-kid", "x": jwk["x"], "y": jwk["y"]}]

        monkeypatch.setattr(deps, "_jwks_keys", first_fetch)
        token = self._es256_token(private, kid="test-kid-1")
        assert _decode_user_id(token, self._settings()) == "user-es256"


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
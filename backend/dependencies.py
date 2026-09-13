"""Shared FastAPI dependencies: current user + user-scoped Supabase client."""

from __future__ import annotations

import base64
import time
from dataclasses import dataclass
from typing import Any

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import ExpiredSignatureError, InvalidTokenError, decode, get_unverified_header

from backend.config import Settings, settings
from supabase import Client, ClientOptions, create_client

bearer_scheme = HTTPBearer(auto_error=False)

_JWKS_TTL_SECONDS = 300.0
_jwks_cache: dict[str, Any] = {"fetched_at": 0.0, "keys": []}

_EC_CURVES = {"P-256": ec.SECP256R1, "P-384": ec.SECP384R1, "P-521": ec.SECP521R1}


@dataclass(frozen=True)
class RequestContext:
    """Identity + token for the authenticated caller, used to build an
    RLS-scoped Supabase client for every service call."""

    user_id: str
    token: str


def _b64u_to_int(value: str) -> int:
    padding = "=" * (-len(value) % 4)
    return int.from_bytes(base64.urlsafe_b64decode(value + padding), "big")


def _jwk_to_pem(jwk: dict) -> str:
    """Convert an EC JWK into a PEM public-key string PyJWT can verify with."""
    curve_cls = _EC_CURVES.get(jwk.get("crv"))
    if curve_cls is None:
        raise InvalidTokenError(f"Unsupported JWK curve: {jwk.get('crv')}")
    public_numbers = ec.EllipticCurvePublicNumbers(
        _b64u_to_int(jwk["x"]), _b64u_to_int(jwk["y"]), curve_cls()
    )
    pem = public_numbers.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return pem.decode()


def _fetch_jwks_keys(cfg: Settings) -> list[dict]:
    url = f"{cfg.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
    response = httpx.get(url, headers={"apikey": cfg.supabase_anon_key}, timeout=10)
    response.raise_for_status()
    return response.json().get("keys", [])


def _jwks_keys(cfg: Settings, force: bool = False) -> list[dict]:
    now = time.monotonic()
    if (
        force
        or now - _jwks_cache["fetched_at"] > _JWKS_TTL_SECONDS
        or not _jwks_cache["keys"]
    ):
        _jwks_cache["keys"] = _fetch_jwks_keys(cfg)
        _jwks_cache["fetched_at"] = now
    return _jwks_cache["keys"]


def _decode_user_id(token: str, cfg: Settings) -> str:
    if not cfg.configured:
        raise HTTPException(status_code=500, detail="Backend is not configured with Supabase credentials.")
    try:
        header = get_unverified_header(token)
        if header.get("alg") == "ES256":
            return _decode_es256(token, header, cfg)
        if header.get("alg") == "HS256":
            claims = decode(
                token,
                cfg.supabase_jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
                options={"require": ["sub", "exp"]},
            )
            return str(claims["sub"])
    except ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="Token expired.") from exc
    except InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Invalid token.") from exc
    raise HTTPException(status_code=401, detail="Unsupported token algorithm.")


def _decode_es256(token: str, header: dict, cfg: Settings) -> str:
    kid = header.get("kid")
    keys = _jwks_keys(cfg)
    candidates = [k for k in keys if not k.get("kid") or k.get("kid") == kid] or keys
    for key in candidates:
        try:
            claims = decode(
                token,
                _jwk_to_pem(key),
                algorithms=["ES256"],
                audience="authenticated",
                options={"require": ["sub", "exp"]},
            )
            return str(claims["sub"])
        except ExpiredSignatureError:
            raise
        except InvalidTokenError:
            continue
    refresh_keys = _jwks_keys(cfg, force=True)
    for key in refresh_keys:
        try:
            claims = decode(
                token,
                _jwk_to_pem(key),
                algorithms=["ES256"],
                audience="authenticated",
                options={"require": ["sub", "exp"]},
            )
            return str(claims["sub"])
        except ExpiredSignatureError:
            raise
        except InvalidTokenError:
            continue
    raise InvalidTokenError("No matching JWKS key verified the token signature.")


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    cfg: Settings = Depends(lambda: settings),
) -> RequestContext:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing bearer token.")
    user_id = _decode_user_id(credentials.credentials, cfg)
    return RequestContext(user_id=user_id, token=credentials.credentials)


def supabase_client_for(ctx: RequestContext) -> Client:
    """Supabase client acting as the authenticated user (RLS enforced on every
    query via the user's own access token)."""
    return create_client(
        settings.supabase_url,
        settings.supabase_anon_key,
        options=ClientOptions(headers={"Authorization": f"Bearer {ctx.token}"}),
    )


def anon_client() -> Client:
    """Supabase client without a user context (used for sign-up/sign-in)."""
    return create_client(settings.supabase_url, settings.supabase_anon_key)


class ServiceError(Exception):
    """Raised by services; converted to HTTP 400 with a readable message."""

    def __init__(self, message: str, code: str = "SERVICE_ERROR", status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
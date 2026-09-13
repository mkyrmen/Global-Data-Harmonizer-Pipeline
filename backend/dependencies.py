"""Shared FastAPI dependencies: current user + user-scoped Supabase client."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import ExpiredSignatureError, InvalidTokenError, decode

from backend.config import Settings, settings
from supabase import Client, ClientOptions, create_client

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class RequestContext:
    """Identity + token for the authenticated caller, used to build an
    RLS-scoped Supabase client for every service call."""

    user_id: str
    token: str


def _decode_user_id(token: str, cfg: Settings) -> str:
    if not cfg.configured:
        raise HTTPException(status_code=500, detail="Backend is not configured with Supabase credentials.")
    try:
        claims = decode(
            token,
            cfg.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
            options={"require": ["sub", "exp"]},
        )
    except ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="Token expired.") from exc
    except InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Invalid token.") from exc
    return str(claims["sub"])


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
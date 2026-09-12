"""Auth routes: Signup, Signin and demo-workspace bootstrap."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.dependencies import RequestContext, ServiceError, current_user, supabase_client_for
from backend.services.demo_service import DemoService
from supabase import AuthApiError

router = APIRouter()


class Credentials(BaseModel):
    email: str = Field(min_length=3)
    password: str = Field(min_length=6)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    user_id: str
    email: str


def _session_payload(session) -> TokenResponse:
    user = session.user
    return TokenResponse(access_token=str(session.access_token), refresh_token=str(session.refresh_token), user_id=str(user.id), email=str(user.email))


@router.post("/register", response_model=TokenResponse)
def register(body: Credentials):
    from backend.dependencies import anon_client

    try:
        session = anon_client().auth.sign_up({"email": body.email, "password": body.password})
    except AuthApiError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    if not session.session:
        raise HTTPException(status_code=400, detail="Please confirm your email before signing in.")
    return _session_payload(session.session)


@router.post("/login", response_model=TokenResponse)
def login(body: Credentials):
    from backend.dependencies import anon_client

    try:
        session = anon_client().auth.sign_in_with_password({"email": body.email, "password": body.password})
    except AuthApiError as exc:
        raise HTTPException(status_code=401, detail=exc.message) from exc
    return _session_payload(session)


@router.get("/me")
def me(ctx: RequestContext = Depends(current_user)):
    client = supabase_client_for(ctx)
    row = client.table("profiles").select("*").eq("id", ctx.user_id).maybe_single().execute()
    if not row:
        raise HTTPException(status_code=404, detail="Profile not found")
    return {**row.data, "id": ctx.user_id}


@router.post("/demo")
def demo_workspace(ctx: RequestContext = Depends(current_user)):
    try:
        return DemoService(ctx).ensure_demo_workspace()
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except Exception as exc:  # surface readable 500 with code
        raise HTTPException(status_code=500, detail=f"Demo bootstrap failed: {exc}") from exc
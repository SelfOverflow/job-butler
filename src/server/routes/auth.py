"""Authentication endpoints for session login and logout (see slice 8)."""

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel

from src.server.auth import (
    COOKIE_NAME,
    create_session_token,
    login_limiter,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    password: str


class LoginResponse(BaseModel):
    status: str
    csrf_token: str


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request, response: Response) -> LoginResponse:
    settings = request.app.state.settings
    client_ip = request.client.host if request.client else "unknown"

    if not login_limiter.is_allowed(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Please wait a minute.",
        )

    if not settings.dashboard_password_hash or not verify_password(
        payload.password, settings.dashboard_password_hash
    ):
        login_limiter.record_attempt(client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    token, csrf = create_session_token(settings.session_secret, settings.session_expiry_hours)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=settings.session_expiry_hours * 3600,
        httponly=True,
        samesite="strict",
        secure=settings.app_env == "production",
    )
    return LoginResponse(status="authenticated", csrf_token=csrf)


@router.post("/logout")
def logout(response: Response) -> dict[str, str]:
    response.delete_cookie(key=COOKIE_NAME)
    return {"status": "logged_out"}


@router.get("/me")
def me() -> dict[str, bool]:
    return {"authenticated": True}

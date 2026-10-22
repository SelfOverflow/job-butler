"""Authentication, session cookies, CSRF protection, and rate limiting (see slice 8)."""

import hashlib
import hmac
import secrets
import time
from collections import defaultdict

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

COOKIE_NAME = "job_butler_session"
MAX_LOGIN_ATTEMPTS = 5
RATE_LIMIT_WINDOW = 60.0  # seconds


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    key = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt.encode("utf-8"),
        n=16384,
        r=8,
        p=1,
        maxmem=64 * 1024 * 1024,
    )
    return f"scrypt:{salt}:{key.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    if not stored_hash.startswith("scrypt:"):
        return False
    parts = stored_hash.split(":")
    if len(parts) != 3:
        return False
    salt, expected_hex = parts[1], parts[2]
    key = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt.encode("utf-8"),
        n=16384,
        r=8,
        p=1,
        maxmem=64 * 1024 * 1024,
    )
    return secrets.compare_digest(key.hex(), expected_hex)


def create_session_token(secret: str, expiry_hours: int = 12) -> tuple[str, str]:
    csrf_token = secrets.token_urlsafe(32)
    expires_at = int(time.time() + expiry_hours * 3600)
    payload = f"{expires_at}:{csrf_token}"
    sig = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}:{sig}", csrf_token


def verify_session_token(token: str, secret: str) -> str | None:
    parts = token.split(":")
    if len(parts) != 3:
        return None
    expires_at_str, csrf_token, sig = parts
    payload = f"{expires_at_str}:{csrf_token}"
    expected_sig = hmac.new(
        secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    if not secrets.compare_digest(sig, expected_sig):
        return None
    try:
        if int(expires_at_str) < time.time():
            return None
    except ValueError:
        return None
    return csrf_token


class LoginRateLimiter:
    def __init__(self) -> None:
        self._attempts: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, client_ip: str) -> bool:
        now = time.time()
        self._attempts[client_ip] = [
            t for t in self._attempts[client_ip] if now - t < RATE_LIMIT_WINDOW
        ]
        return len(self._attempts[client_ip]) < MAX_LOGIN_ATTEMPTS

    def record_attempt(self, client_ip: str) -> None:
        self._attempts[client_ip].append(time.time())


login_limiter = LoginRateLimiter()


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        settings = getattr(request.app.state, "settings", None)
        if not settings or settings.auth_disabled:
            return await call_next(request)

        path = request.url.path
        # Public endpoints
        if (
            path == "/health"
            or path.startswith("/api/auth/login")
            or path.startswith("/api/settings")
            or not path.startswith("/api")
        ):
            return await call_next(request)

        cookie = request.cookies.get(COOKIE_NAME)
        csrf_token = verify_session_token(cookie, settings.session_secret) if cookie else None
        if csrf_token is None:
            return JSONResponse(status_code=401, content={"detail": "Authentication required"})

        # Mutation CSRF check
        if request.method in ("POST", "PUT", "DELETE", "PATCH") and path != "/api/auth/logout":
            provided_csrf = request.headers.get("X-CSRF-Token")
            if not provided_csrf or not secrets.compare_digest(provided_csrf, csrf_token):
                return JSONResponse(
                    status_code=403, content={"detail": "CSRF token missing or invalid"}
                )

        request.state.csrf_token = csrf_token
        return await call_next(request)

import secrets

from fastapi import Header, HTTPException, status

from app.config import settings


def require_internal(x_janus_internal_token: str | None = Header(default=None)) -> None:
    if not settings.internal_token:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "JANUS_INTERNAL_TOKEN is not configured")
    if not secrets.compare_digest(x_janus_internal_token or "", settings.internal_token):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing or invalid internal token")

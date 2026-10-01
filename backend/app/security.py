import secrets

from fastapi import Header, HTTPException, status

from app.config import settings


def require_internal(x_janus_internal_token: str | None = Header(default=None)) -> None:
    if not settings.internal_token:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "JANUS_INTERNAL_TOKEN is not configured")
    supplied = (x_janus_internal_token or "").encode("utf-8", "surrogateescape")
    if not secrets.compare_digest(supplied, settings.internal_token.encode("utf-8")):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing or invalid internal token")

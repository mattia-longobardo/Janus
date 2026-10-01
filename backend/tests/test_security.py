import pytest
from fastapi import HTTPException

from app.config import settings
from app.security import require_internal


def test_non_ascii_token_is_rejected_not_crashing(monkeypatch):
    monkeypatch.setattr(settings, "internal_token", "s3cret")
    with pytest.raises(HTTPException) as exc:
        require_internal("tökén")
    assert exc.value.status_code == 401
    require_internal("s3cret")


def test_non_ascii_header_over_http_is_401(client):
    response = client.get("/api/devices", headers={"X-Janus-Internal-Token": "tökén".encode()})
    assert response.status_code == 401

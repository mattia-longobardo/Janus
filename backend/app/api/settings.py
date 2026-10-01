from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.general import TIMEZONE_KEY, current_tz
from app.models import Setting

router = APIRouter(prefix="/api/settings", tags=["settings"])
TIME_FORMAT_KEY = "general.time_format"


class SettingsPatch(BaseModel):
    timezone: str | None = None
    time_format: Literal["24h", "12h"] | None = None


def _setting(db: Session, key: str) -> Any:
    row = db.get(Setting, key)
    return row.value if row is not None else None


def _view(db: Session) -> dict[str, Any]:
    row = db.get(Setting, TIME_FORMAT_KEY)
    return {
        "timezone": current_tz(db).key,
        "time_format": row.value if row is not None and row.value in ("24h", "12h") else "24h",
        "sync_mode": settings.sync_mode,
        "network": {
            "subnet": settings.subnet,
            "gateway": settings.gateway,
            "quarantine_start": settings.quarantine_start,
            "quarantine_end": settings.quarantine_end,
            "pihole_url": settings.pihole_url,
            "sentinel_interface": settings.sentinel_interface,
            "sweep_interval_s": settings.sweep_interval_s,
        },
        "scan_window": {"start": settings.scan_window_start, "end": settings.scan_window_end},
        "status": {
            "pihole_down_since": _setting(db, "pihole.down_since"),
            "sentinel_down_since": _setting(db, "sentinel.down_since"),
            "last_sweep_at": _setting(db, "sentinel.heartbeat"),
            "maintenance_active": bool(_setting(db, "maintenance.active")),
        },
        "channels": {"gotify_url": settings.gotify_url, "email_sender": settings.smtp_sender},
    }


@router.get("")
def get_settings(db: Session = Depends(get_db)) -> dict[str, Any]:
    return _view(db)


@router.put("")
def put_settings(body: SettingsPatch, db: Session = Depends(get_db)) -> dict[str, Any]:
    if body.timezone is not None:
        try:
            ZoneInfo(body.timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"unknown timezone {body.timezone!r}") from exc
        db.merge(Setting(key=TIMEZONE_KEY, value=body.timezone))
    if body.time_format is not None:
        db.merge(Setting(key=TIME_FORMAT_KEY, value=body.time_format))
    db.commit()
    return _view(db)

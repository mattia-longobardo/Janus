from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.events import record_event
from app.models import NotificationRule
from app.notify.catalog import CATALOG, CHANNELS
from app.notify.store import NotifySettings, load_notify_settings, load_rules, save_notify_settings

router = APIRouter(prefix="/api/notifications", tags=["notifications"])
HHMM = r"^([01]\d|2[0-3]):[0-5]\d$"
EMAIL = r"^$|^[^@\s]+@[^@\s]+\.[^@\s]+$"


class SettingsIn(BaseModel):
    enabled: bool
    quiet_start: str | None = Field(default=None, pattern=HHMM)
    quiet_end: str | None = Field(default=None, pattern=HHMM)
    email_enabled: bool
    email_recipient: str = Field(default="", max_length=254, pattern=EMAIL)
    gotify_enabled: bool


class RuleIn(BaseModel):
    event_type: str
    email: bool
    gotify: bool


def _rules(db: Session) -> list[dict[str, Any]]:
    stored = load_rules(db)
    return [
        {"event_type": kind, "label": spec.label,
         "email": stored.get((kind, "email"), spec.email), "gotify": stored.get((kind, "gotify"), spec.gotify)}
        for kind, spec in CATALOG.items()
        if kind != "notify.test"
    ]


@router.get("")
def get_notifications(db: Session = Depends(get_db)) -> dict[str, Any]:
    return {"settings": asdict(load_notify_settings(db)), "rules": _rules(db)}


@router.put("/settings")
def put_settings(body: SettingsIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    ns = NotifySettings(**body.model_dump())
    save_notify_settings(db, ns)
    db.commit()
    return asdict(ns)


@router.put("/rules")
def put_rules(body: list[RuleIn], db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    for rule in body:
        if rule.event_type not in CATALOG or rule.event_type == "notify.test":
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"unknown event type {rule.event_type!r}")
    for rule in body:
        db.merge(NotificationRule(event_type=rule.event_type, channel="email", enabled=rule.email))
        db.merge(NotificationRule(event_type=rule.event_type, channel="gotify", enabled=rule.gotify))
    db.commit()
    return _rules(db)


@router.post("/test/{channel}", status_code=status.HTTP_202_ACCEPTED)
def test_channel(channel: str, db: Session = Depends(get_db)) -> dict[str, bool]:
    if channel not in CHANNELS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "unknown channel")
    record_event(db, "notify.test", None, {"channel": channel})
    db.commit()
    return {"queued": True}

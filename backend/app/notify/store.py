from dataclasses import asdict, dataclass, fields
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import NotificationRule, Setting
from app.notify.catalog import CATALOG

SETTINGS_KEY = "notify.settings"


@dataclass
class NotifySettings:
    enabled: bool = True
    quiet_start: str | None = "23:00"
    quiet_end: str | None = "07:00"
    email_enabled: bool = True
    email_recipient: str = ""
    gotify_enabled: bool = True

    def channel_enabled(self, channel: str) -> bool:
        return bool(getattr(self, f"{channel}_enabled", False))


def load_notify_settings(db: Session) -> NotifySettings:
    row = db.get(Setting, SETTINGS_KEY)
    stored: dict[str, Any] = row.value if row is not None and isinstance(row.value, dict) else {}
    names = {f.name for f in fields(NotifySettings)}
    ns = NotifySettings(**{key: value for key, value in stored.items() if key in names})
    if not ns.email_recipient:
        ns.email_recipient = settings.notify_email
    return ns


def save_notify_settings(db: Session, ns: NotifySettings) -> None:
    db.merge(Setting(key=SETTINGS_KEY, value=asdict(ns)))
    db.flush()


def load_rules(db: Session) -> dict[tuple[str, str], bool]:
    return {(rule.event_type, rule.channel): rule.enabled for rule in db.scalars(select(NotificationRule))}


def default_rule_rows() -> list[dict[str, Any]]:
    rows = []
    for event_type, spec in CATALOG.items():
        rows.append({"event_type": event_type, "channel": "email", "enabled": spec.email})
        rows.append({"event_type": event_type, "channel": "gotify", "enabled": spec.gotify})
    return rows

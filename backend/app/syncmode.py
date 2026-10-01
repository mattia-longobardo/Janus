from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Literal

from sqlalchemy.orm import Session

from app.config import settings
from app.events import record_event
from app.models import Setting

SyncMode = Literal["dry-run", "apply"]
SYNC_KEY = "sync.mode"
MODES: tuple[SyncMode, ...] = ("dry-run", "apply")


def load_sync_mode(db: Session) -> SyncMode:
    row = db.get(Setting, SYNC_KEY)
    if row is not None and row.value in MODES:
        return row.value
    return settings.sync_mode


def load_sync_mode_with(session_factory: Callable[[], AbstractContextManager[Session]]) -> SyncMode:
    with session_factory() as db:
        return load_sync_mode(db)


def set_sync_mode(db: Session, mode: SyncMode, actor: str) -> None:
    if mode not in MODES:
        raise ValueError(f"unknown sync mode {mode!r}")
    previous = load_sync_mode(db)
    db.merge(Setting(key=SYNC_KEY, value=mode))
    if previous != mode:
        record_event(db, "sync.mode", None, {"from": previous, "to": mode, "actor": actor})
    db.flush()

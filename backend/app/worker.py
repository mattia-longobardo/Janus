import logging
import time
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.events import record_event
from app.models import Setting
from app.pihole.client import PiholeClient, PiholeError
from app.pihole.reservations import HostDiff
from app.pihole.sync import apply_sync, plan_sync

log = logging.getLogger("janus.worker")
DOWN_KEY = "pihole.down_since"


def _mark_down(db: Session, error: str) -> None:
    state = db.get(Setting, DOWN_KEY)
    if state is None or state.value is None:
        db.merge(Setting(key=DOWN_KEY, value=datetime.now(UTC).isoformat()))
        record_event(db, "infra.down", None, {"service": "pihole", "error": error})


def _mark_up(db: Session) -> None:
    state = db.get(Setting, DOWN_KEY)
    if state is not None and state.value is not None:
        record_event(db, "infra.up", None, {"service": "pihole", "down_since": state.value})
        state.value = None


def reconcile_once(
    session_factory: Callable[[], AbstractContextManager[Session]],
    client_factory: Callable[[], AbstractContextManager],
    *,
    lease: str,
    apply: bool,
) -> HostDiff | None:
    with session_factory() as db:
        try:
            with client_factory() as client:
                diff = apply_sync(db, client, lease) if apply else plan_sync(db, client, lease)
        except PiholeError as exc:
            log.warning("reconcile failed: %s", exc)
            _mark_down(db, str(exc))
            db.commit()
            return None
        _mark_up(db)
        db.commit()
        if not diff.empty:
            log.info("reconcile %s: %s", "applied" if apply else "dry-run", diff.as_dict())
        return diff


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    heartbeat = Path(settings.heartbeat_path)
    apply = settings.sync_mode == "apply"
    log.info("worker started (mode=%s, interval=%ss)", settings.sync_mode, settings.reconcile_interval_s)
    while True:
        reconcile_once(
            SessionLocal,
            lambda: PiholeClient(settings.pihole_url, settings.pihole_password),
            lease=settings.reservation_lease,
            apply=apply,
        )
        heartbeat.touch()
        time.sleep(settings.reconcile_interval_s)


if __name__ == "__main__":
    main()

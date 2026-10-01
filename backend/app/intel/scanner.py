import logging
import subprocess
import time
import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.events import record_event
from app.general import current_tz
from app.intel.nmap import parse_nmap_xml
from app.intel.scanning import apply_scan, pick_next
from app.maintenance import active_windows, load_windows
from app.models import Device
from app.netconfig import load_netconfig
from app.notify.policy import in_quiet_hours, parse_hhmm
from app.notify.store import load_notify_settings

log = logging.getLogger("janus.scanner")
NMAP_ARGS = ["-sT", "-sV", "--version-light", "-T3", "--top-ports", "200", "-Pn"]
SessionFactory = Callable[[], AbstractContextManager[Session]]


class ScanError(RuntimeError):
    pass


def run_nmap(ip: str, *, timeout_s: int, runner: Callable[..., Any] = subprocess.run) -> str:
    cmd = ["nmap", *NMAP_ARGS, "--host-timeout", f"{timeout_s}s", "-oX", "-", ip]
    result = runner(cmd, capture_output=True, text=True, timeout=timeout_s + 60)
    if result.returncode != 0:
        raise ScanError((result.stderr or "").strip()[:300] or f"nmap exited with {result.returncode}")
    return result.stdout


def _choose(db: Session, now: datetime) -> Device | None:
    tz = current_tz(db)
    ns = load_notify_settings(db)
    windows = load_windows(db)
    end = now + timedelta(seconds=settings.scan_host_timeout_s + 60)
    quiet_start, quiet_end = parse_hhmm(ns.quiet_start), parse_hhmm(ns.quiet_end)
    cfg = load_netconfig(db)
    day_start, day_end = parse_hhmm(cfg.scan_window_start), parse_hhmm(cfg.scan_window_end)
    muted = any(active_windows(windows, moment, tz) for moment in (now, end))
    quiet = any(
        in_quiet_hours(moment.astimezone(tz).time(), quiet_start, quiet_end)
        or (day_start is not None and day_end is not None
            and in_quiet_hours(moment.astimezone(tz).time(), day_end, day_start))
        for moment in (now, end)
    )
    return pick_next(db, now, muted=muted, quiet=quiet)


def scan_once(
    session_factory: SessionFactory, now: datetime | None = None, runner: Callable[..., Any] = subprocess.run
) -> str | None:
    now = now or datetime.now(UTC)
    with session_factory() as db:
        device = _choose(db, now)
        if device is None:
            return None
        device_id: uuid.UUID = device.id
        mac, ip = device.mac, device.last_ip
    log.info("scanning %s (%s)", ip, mac)
    try:
        results = parse_nmap_xml(run_nmap(ip, timeout_s=settings.scan_host_timeout_s, runner=runner))
    except (ScanError, ValueError, subprocess.TimeoutExpired, OSError) as exc:
        log.warning("scan of %s failed: %s", ip, exc)
        with session_factory() as db:
            device = db.get(Device, device_id)
            if device is not None:
                device.last_scan_at, device.scan_requested_at = now, None
                record_event(db, "scan.failed", mac, {"device_id": str(device_id), "ip": ip, "error": str(exc)[:300]},
                             ts=now)
            db.commit()
        return mac
    try:
        with session_factory() as db:
            device = db.get(Device, device_id)
            if device is not None:
                apply_scan(db, device, results, now)
            db.commit()
    except Exception as exc:
        log.exception("saving the scan of %s failed", ip)
        with session_factory() as db:
            device = db.get(Device, device_id)
            if device is not None:
                device.last_scan_at, device.scan_requested_at = now, None
                record_event(db, "scan.failed", mac, {"device_id": str(device_id), "ip": ip, "error": str(exc)[:300]},
                             ts=now)
            db.commit()
    return mac


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    heartbeat = Path(settings.scanner_heartbeat_path)
    log.info("scanner started")
    while True:
        try:
            scan_once(SessionLocal)
        except Exception:
            log.exception("scan loop failed")
        heartbeat.touch()
        time.sleep(settings.scan_poll_s)


if __name__ == "__main__":
    main()

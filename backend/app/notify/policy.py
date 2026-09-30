from datetime import datetime, time
from typing import Any

from app.notify.catalog import CATALOG, CHANNELS
from app.notify.store import NotifySettings


def parse_hhmm(value: str | None) -> time | None:
    if not value:
        return None
    hours, minutes = value.split(":")
    return time(int(hours), int(minutes))


def in_quiet_hours(moment: time, start: time | None, end: time | None) -> bool:
    if start is None or end is None or start == end:
        return False
    if start < end:
        return start <= moment < end
    return moment >= start or moment < end


def channels_for(
    event_type: str,
    payload: dict[str, Any],
    rules: dict[tuple[str, str], bool],
    ns: NotifySettings,
    local_now: datetime,
    alerts_muted: bool,
    ready: set[str],
) -> list[str]:
    spec = CATALOG.get(event_type)
    if spec is None:
        return []
    if event_type == "notify.test":
        wanted = payload.get("channel")
        return [wanted] if wanted in ready else []
    if not ns.enabled:
        return []
    if not spec.always:
        if alerts_muted and spec.maintenance_muted:
            return []
        if in_quiet_hours(local_now.time(), parse_hhmm(ns.quiet_start), parse_hhmm(ns.quiet_end)):
            return []
    return [c for c in CHANNELS if c in ready and ns.channel_enabled(c) and rules.get((event_type, c), False)]

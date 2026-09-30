from typing import Protocol

from sqlalchemy.orm import Session

from app.events import record_event
from app.pihole.reservations import HostDiff, desired_hosts, diff_hosts


class HostStore(Protocol):
    def list_hosts(self) -> list[str]: ...
    def add_host(self, line: str) -> None: ...
    def remove_host(self, line: str) -> None: ...


def plan_sync(db: Session, client: HostStore, lease: str) -> HostDiff:
    return diff_hosts(desired_hosts(db, lease), client.list_hosts())


def apply_sync(db: Session, client: HostStore, lease: str) -> HostDiff:
    diff = plan_sync(db, client, lease)
    for raw in diff.to_remove:
        client.remove_host(raw)
    for host in diff.to_add:
        client.add_host(host.render())
    if not diff.empty:
        record_event(db, "sync.applied", None, {"added": [h.render() for h in diff.to_add], "removed": diff.to_remove})
    return diff

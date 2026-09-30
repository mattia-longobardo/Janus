from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Access, Device
from app.net.mac import normalize_mac

LAN_ONLY_TAG = "set:lanonly"


@dataclass(frozen=True, order=True)
class HostLine:
    mac: str
    ip: str
    hostname: str
    lan_only: bool = False
    lease: str = "24h"

    def render(self) -> str:
        parts = [self.mac.lower()]
        if self.lan_only:
            parts.append(LAN_ONLY_TAG)
        parts += [self.ip, self.hostname, self.lease]
        return ",".join(parts)

    @classmethod
    def parse(cls, line: str) -> "HostLine | None":
        parts = [p.strip() for p in line.split(",")]
        lan_only = LAN_ONLY_TAG in parts
        parts = [p for p in parts if p != LAN_ONLY_TAG]
        if len(parts) != 4:
            return None
        raw_mac, ip, hostname, lease = parts
        try:
            mac = normalize_mac(raw_mac)
        except ValueError:
            return None
        return cls(mac, ip, hostname, lan_only, lease)


@dataclass
class HostDiff:
    to_add: list[HostLine] = field(default_factory=list)
    to_remove: list[str] = field(default_factory=list)
    unmanaged: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        return not (self.to_add or self.to_remove)

    def as_dict(self) -> dict[str, Any]:
        return {
            "to_add": [h.render() for h in self.to_add],
            "to_remove": list(self.to_remove),
            "unmanaged": list(self.unmanaged),
            "failed": list(self.failed),
        }


def desired_hosts(db: Session, lease: str) -> set[HostLine]:
    rows = db.scalars(
        select(Device).where(
            Device.mac.is_not(None),
            Device.static_ip.is_not(None),
            Device.access.in_([Access.authorized, Access.lan_only]),
        )
    )
    return {
        HostLine(d.mac, d.static_ip, d.hostname, lan_only=d.access is Access.lan_only, lease=lease)
        for d in rows
    }


def diff_hosts(desired: set[HostLine], current_raw: list[str]) -> HostDiff:
    current: dict[HostLine, str] = {}
    diff = HostDiff()
    for raw in current_raw:
        parsed = HostLine.parse(raw)
        if parsed is None:
            diff.unmanaged.append(raw)
        else:
            current[parsed] = raw
    diff.to_add = sorted(desired - current.keys())
    diff.to_remove = sorted(raw for parsed, raw in current.items() if parsed not in desired)
    return diff

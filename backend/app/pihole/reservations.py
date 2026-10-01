from dataclasses import dataclass, field
from ipaddress import IPv4Address
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Access, Device, Setting
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


WRITTEN_KEY = "pihole.written_macs"


def written_macs(db: Session) -> set[str] | None:
    row = db.get(Setting, WRITTEN_KEY)
    return set(row.value) if row is not None and isinstance(row.value, list) else None


def remember_written(db: Session, macs: set[str]) -> None:
    db.merge(Setting(key=WRITTEN_KEY, value=sorted(macs)))


def managed_macs(db: Session, current_raw: list[str] | None = None, lease: str | None = None) -> set[str]:
    """MACs Janus manages: every device it knows plus every MAC it has ever written to Pi-hole, so the
    reservation of a deleted device is removed too. Before anything is recorded, lines in Janus' exact
    format (lower-case MAC, configured lease) are recognised as Janus' own."""
    known = set(db.scalars(select(Device.mac).where(Device.mac.is_not(None))))
    written = written_macs(db)
    if written is None:
        written = set()
        for raw in current_raw or []:
            parsed = HostLine.parse(raw)
            if parsed is not None and parsed.render() == raw and (lease is None or parsed.lease == lease):
                written.add(parsed.mac)
        remember_written(db, written)
    return known | written


def diff_hosts(desired: set[HostLine], current_raw: list[str], managed: set[str] | None = None) -> HostDiff:
    """Lines Janus does not manage (MAC neither known nor written by Janus) are reported, never removed.

    An addition that would give Pi-hole two reservations with the same IP or MAC is refused and reported in
    `failed`: dnsmasq rejects such a configuration and stops answering DNS."""
    current: dict[HostLine, str] = {}
    diff = HostDiff()
    for raw in current_raw:
        parsed = HostLine.parse(raw)
        if parsed is None or (managed is not None and parsed.mac not in managed):
            diff.unmanaged.append(raw)
        else:
            current[parsed] = raw
    diff.to_remove = sorted(raw for parsed, raw in current.items() if parsed not in desired)
    kept = [raw for parsed, raw in current.items() if parsed in desired] + diff.unmanaged
    taken_ips: dict[str, str] = {}
    taken_macs: dict[str, str] = {}
    for raw in kept:
        mac, ip = _identity(raw)
        if ip:
            taken_ips[ip] = raw
        if mac:
            taken_macs[mac] = raw
    for host in sorted(desired - current.keys()):
        clash = taken_ips.get(host.ip) or taken_macs.get(host.mac)
        if clash is not None:
            diff.failed.append(f"{host.render()}: would duplicate {clash} in Pi-hole, skipped")
            continue
        diff.to_add.append(host)
        taken_ips[host.ip] = taken_macs[host.mac] = host.render()
    return diff


def _identity(raw: str) -> tuple[str | None, str | None]:
    """MAC and IPv4 address of any dhcp-host style line, whatever its other fields."""
    mac = ip = None
    for part in (p.strip() for p in raw.split(",")):
        if mac is None:
            try:
                mac = normalize_mac(part)
                continue
            except ValueError:
                pass
        if ip is None:
            try:
                ip = str(IPv4Address(part))
            except ValueError:
                pass
    return mac, ip

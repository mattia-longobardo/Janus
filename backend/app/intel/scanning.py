from datetime import datetime, timedelta
from ipaddress import AddressValueError, IPv4Address, IPv4Network

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.events import record_event
from app.intel.nmap import PortResult, classify
from app.models import Access, Device, Event, Group, Service
from app.netconfig import load_netconfig

APPROVED = (Access.authorized, Access.lan_only)


def on_lan(ip: str | None, subnet: str) -> bool:
    try:
        return ip is not None and IPv4Address(ip) in IPv4Network(subnet, strict=False)
    except (AddressValueError, ValueError):
        return False


def pick_next(db: Session, now: datetime, *, muted: bool, quiet: bool) -> Device | None:
    subnet = load_netconfig(db).subnet
    requested = db.scalars(
        select(Device).where(Device.scan_requested_at.is_not(None), Device.last_ip.is_not(None))
        .order_by(Device.scan_requested_at)
    )
    for device in requested:
        if on_lan(device.last_ip, subnet):
            return device
    if muted or quiet:
        return None
    candidates = db.execute(
        select(Device, Group.scan_interval_hours)
        .join(Group, Device.group_id == Group.id)
        .where(Group.scan_enabled.is_(True), Device.access.in_(APPROVED), Device.online.is_(True),
               Device.last_ip.is_not(None), Device.mac.is_not(None))
        .order_by(Device.last_scan_at.asc().nulls_first())
    ).all()
    for device, hours in candidates:
        if not on_lan(device.last_ip, subnet):
            continue
        if device.last_scan_at is None or now - device.last_scan_at >= timedelta(hours=hours):
            return device
    return None


def apply_scan(db: Session, device: Device, results: list[PortResult], now: datetime) -> list[Event]:
    baseline_done = device.last_scan_at is not None
    existing = {(row.port, row.proto): row for row in db.scalars(select(Service).where(Service.mac == device.mac))}
    events: list[Event] = []
    risky: list[dict] = []
    seen = set()
    for result in results:
        key = (result.port, result.proto)
        seen.add(key)
        risk, reason = classify(result.port, result.service)
        row = existing.get(key)
        newly_open = row is None or row.state != "open"
        if row is None:
            row = Service(mac=device.mac, port=result.port, proto=result.proto, first_seen=now)
            db.add(row)
        row.state = "open"
        row.service = result.service[:64] if result.service else None
        row.version = result.version[:255] if result.version else None
        row.risk, row.risk_reason, row.last_seen = risk, reason, now
        base = {"device_id": str(device.id), "name": device.name, "port": result.port, "proto": result.proto,
                "service": result.service}
        if row.muted:
            continue
        if newly_open and baseline_done:
            events.append(record_event(db, "security.new_port", device.mac, {**base, "version": result.version}, ts=now))
        if newly_open and risk != "none":
            risky.append({"port": result.port, "proto": result.proto, "service": row.service, "risk": risk,
                          "reason": reason})
    if risky:
        level = "high" if any(item["risk"] == "high" for item in risky) else "warning"
        events.append(record_event(db, "security.risky_service", device.mac, {
            "device_id": str(device.id), "name": device.name, "risk": level,
            "ports": sorted(risky, key=lambda item: (item["port"], item["proto"])),
        }, ts=now))
    for key, row in existing.items():
        if key not in seen and row.state == "open":
            row.state = "closed"
    device.last_scan_at = now
    device.scan_requested_at = None
    record_event(db, "scan.completed", device.mac, {"device_id": str(device.id), "open_ports": len(results)}, ts=now)
    db.flush()
    return events

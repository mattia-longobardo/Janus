from datetime import datetime, timedelta
from ipaddress import AddressValueError, IPv4Address

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.events import record_event
from app.models import Access, Device, Event, Sighting
from app.net.ipplan import NetworkPlan
from app.net.mac import is_private_mac
from app.net.names import hostname_for
from app.sentinel.observe import Observation

SIGHTING_GAP = timedelta(minutes=10)
CONFLICT_WINDOW = timedelta(minutes=2)
REPEAT_GAP = timedelta(hours=1)
APPROVED = (Access.authorized, Access.lan_only)


def _address(ip: str | None) -> IPv4Address | None:
    try:
        return IPv4Address(ip) if ip else None
    except (AddressValueError, ValueError):
        return None


def _recent(db: Session, kind: str, since: datetime, *, mac: str | None = None, ip: str | None = None) -> bool:
    query = select(Event.id).where(Event.type == kind, Event.ts >= since)
    if mac is not None:
        query = query.where(Event.mac == mac)
    if ip is not None:
        query = query.where(Event.payload["ip"].astext == ip)
    return db.scalar(query.limit(1)) is not None


def _new_device(db: Session, obs: Observation, plan: NetworkPlan, now: datetime) -> Device:
    taken = set(db.scalars(select(Device.hostname)))
    private = is_private_mac(obs.mac)
    if _address(obs.ip) == plan.gateway:
        device = Device(mac=obs.mac, name="Gateway", hostname=hostname_for("gateway", taken), access=Access.authorized,
                        private_mac=private, first_seen=now)
        db.add(device)
        db.flush()
        record_event(db, "device.gateway", obs.mac, {"device_id": str(device.id), "ip": obs.ip}, ts=now)
        return device

    name = (obs.hostname or f"Unknown {obs.mac[-8:]}")[:64]
    device = Device(mac=obs.mac, name=name, hostname=hostname_for(name, taken), access=Access.pending,
                    private_mac=private, first_seen=now, dhcp_hostname=obs.hostname)
    db.add(device)
    db.flush()
    record_event(db, "device.new", obs.mac, {
        "device_id": str(device.id), "ip": obs.ip, "hostname": obs.hostname, "private_mac": private, "source": obs.source,
    }, ts=now)
    if private and obs.hostname:
        twin = db.scalar(select(Device).where(
            Device.dhcp_hostname == obs.hostname, Device.mac != obs.mac, Device.access.in_(APPROVED)
        ))
        if twin is not None:
            record_event(db, "device.private_mac", obs.mac, {
                "device_id": str(device.id), "previous_mac": twin.mac, "previous_name": twin.name,
            }, ts=now)
    return device


def _check_conflict(db: Session, device: Device, ip: str, now: datetime) -> None:
    rival = db.scalar(select(Device).where(
        Device.last_ip == ip, Device.id != device.id, Device.online.is_(True), Device.last_seen >= now - CONFLICT_WINDOW
    ))
    if rival is None or _recent(db, "ip.conflict", now - REPEAT_GAP, ip=ip):
        return
    record_event(db, "ip.conflict", device.mac, {"ip": ip, "macs": sorted([device.mac, rival.mac])}, ts=now)


def _check_mismatch(db: Session, device: Device, ip: str, plan: NetworkPlan, now: datetime) -> None:
    address = _address(ip)
    if (
        device.access not in APPROVED
        or device.static_ip is None
        or ip == device.static_ip
        or address is None
        or address in plan.quarantine
        or _recent(db, "device.ip_mismatch", now - REPEAT_GAP, mac=device.mac)
    ):
        return
    record_event(db, "device.ip_mismatch", device.mac, {
        "device_id": str(device.id), "name": device.name, "ip": ip, "expected": device.static_ip,
    }, ts=now)


def record_observation(db: Session, obs: Observation, plan: NetworkPlan, now: datetime) -> Device:
    device = db.scalar(select(Device).where(Device.mac == obs.mac))
    if device is None:
        device = _new_device(db, obs, plan, now)
        previous_ip, previous_seen = None, None
    else:
        previous_ip, previous_seen = device.last_ip, device.last_seen

    if obs.source == "dhcp" or (obs.ip and obs.ip != previous_ip) or previous_seen is None or now - previous_seen >= SIGHTING_GAP:
        db.add(Sighting(mac=obs.mac, ip=obs.ip, source=obs.source, payload=obs.payload(), ts=now))

    device.online = True
    device.last_seen = now
    if device.first_seen is None:
        device.first_seen = now
    if obs.hostname:
        device.dhcp_hostname = obs.hostname
    if obs.ip:
        device.last_ip = obs.ip
        db.flush()
        _check_conflict(db, device, obs.ip, now)
        _check_mismatch(db, device, obs.ip, plan, now)
    db.flush()
    return device

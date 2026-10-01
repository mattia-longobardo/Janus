from datetime import datetime, timedelta
from ipaddress import AddressValueError, IPv4Address

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.events import record_event
from app.models import Access, Device, Event, Setting, Sighting
from app.net.ipplan import NetworkPlan
from app.net.mac import is_private_mac
from app.net.names import hostname_for
from app.sentinel.observe import Observation

GATEWAY_KEY = "gateway.mac"
SIGHTING_GAP = timedelta(minutes=10)
RICH_GAP = timedelta(hours=6)
RICH_SOURCES = {"mdns", "netbios", "ssdp"}
CONFLICT_WINDOW = timedelta(minutes=2)
REPEAT_GAP = timedelta(hours=1)
MISMATCH_GAP = timedelta(hours=24)
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
    if _address(obs.ip) == plan.gateway and db.get(Setting, GATEWAY_KEY) is None:
        db.add(Setting(key=GATEWAY_KEY, value=obs.mac))
        device = Device(mac=obs.mac, name="Gateway", hostname=hostname_for("gateway", taken), access=Access.authorized,
                        private_mac=private, first_seen=now)
        db.add(device)
        db.flush()
        record_event(db, "device.gateway", obs.mac, {"device_id": str(device.id), "ip": obs.ip}, ts=now)
        return device

    name = (obs.hostname or f"Unknown {obs.mac[-8:]}")[:64]
    device = Device(mac=obs.mac, name=name, hostname=hostname_for(name, taken), access=Access.pending,
                    private_mac=private, first_seen=now,
                    dhcp_hostname=obs.hostname if obs.source == "dhcp" else None)
    db.add(device)
    db.flush()
    record_event(db, "device.new", obs.mac, {
        "device_id": str(device.id), "ip": obs.ip, "hostname": obs.hostname, "private_mac": private, "source": obs.source,
    }, ts=now)
    if private and obs.hostname and obs.source == "dhcp":
        twin = db.scalar(select(Device).where(
            Device.dhcp_hostname == obs.hostname, Device.mac != obs.mac, Device.access.in_(APPROVED)
        ))
        if twin is not None:
            record_event(db, "device.private_mac", obs.mac, {
                "device_id": str(device.id), "previous_mac": twin.mac, "previous_name": twin.name,
            }, ts=now)
    return device


def _check_conflict(db: Session, device: Device, ip: str, previous_ip: str | None, previous_seen: datetime | None,
                    now: datetime) -> None:
    """A conflict needs both MACs to keep answering for the IP: this device was already on it, and the rival
    has been seen there since. A device simply taking over an address (DHCP handover) is not a conflict."""
    if previous_ip != ip or previous_seen is None:
        return
    rival = db.scalar(select(Device).where(
        Device.last_ip == ip, Device.id != device.id, Device.online.is_(True),
        Device.last_seen >= now - CONFLICT_WINDOW, Device.last_seen > previous_seen,
    ))
    if rival is None or _recent(db, "ip.conflict", now - REPEAT_GAP, ip=ip):
        return
    record_event(db, "ip.conflict", device.mac, {"ip": ip, "macs": sorted([device.mac, rival.mac])}, ts=now)


def _check_mismatch(db: Session, device: Device, ip: str, previous_ip: str | None, plan: NetworkPlan,
                    now: datetime) -> None:
    address = _address(ip)
    if (
        device.access not in APPROVED
        or device.static_ip is None
        or ip == device.static_ip
        or ip != previous_ip
        or address is None
        or address in plan.quarantine
        or _recent(db, "device.ip_mismatch", now - MISMATCH_GAP, mac=device.mac, ip=ip)
    ):
        return
    record_event(db, "device.ip_mismatch", device.mac, {
        "device_id": str(device.id), "name": device.name, "ip": ip, "expected": device.static_ip,
    }, ts=now)


def _needs_sighting(db: Session, obs: Observation, previous_ip: str | None, previous_seen: datetime | None,
                    now: datetime) -> bool:
    if obs.source == "dhcp":
        return True
    if obs.source in RICH_SOURCES:
        recent = db.scalars(select(Sighting).where(
            Sighting.mac == obs.mac, Sighting.source == obs.source, Sighting.ts > now - RICH_GAP
        ).order_by(Sighting.ts.desc()).limit(50)).all()
        if not recent or any(row.ip != obs.ip for row in recent[:1]):
            return True
        known: dict[str, set[str]] = {}
        for row in recent:
            for key, value in (row.payload or {}).items():
                known.setdefault(key, set()).update(value if isinstance(value, list) else [value])
        for key, value in obs.payload().items():
            values = value if isinstance(value, list) else [value]
            if not set(values) <= known.get(key, set()):
                return True
        return False
    return bool(obs.ip and obs.ip != previous_ip) or previous_seen is None or now - previous_seen >= SIGHTING_GAP


def record_observation(db: Session, obs: Observation, plan: NetworkPlan, now: datetime) -> Device:
    device = db.scalar(select(Device).where(Device.mac == obs.mac))
    if device is None:
        device = _new_device(db, obs, plan, now)
        previous_ip, previous_seen = None, None
    else:
        previous_ip, previous_seen = device.last_ip, device.last_seen

    if _needs_sighting(db, obs, previous_ip, previous_seen, now):
        db.add(Sighting(mac=obs.mac, ip=obs.ip, source=obs.source, payload=obs.payload(), ts=now))

    device.online = True
    device.last_seen = now
    if device.first_seen is None:
        device.first_seen = now
    if obs.hostname and obs.source == "dhcp":
        device.dhcp_hostname = obs.hostname
    address = _address(obs.ip)
    if obs.ip and address is not None and address in plan.subnet:
        device.last_ip = obs.ip
        db.flush()
        _check_conflict(db, device, obs.ip, previous_ip, previous_seen, now)
        _check_mismatch(db, device, obs.ip, previous_ip, plan, now)
    db.flush()
    return device

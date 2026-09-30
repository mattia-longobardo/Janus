from ipaddress import IPv4Address

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.events import record_event
from app.models import Access, Device, Group
from app.net.ipplan import NetworkPlan, check_assignment, next_free
from app.net.names import hostname_for

APPROVABLE = {Access.authorized, Access.lan_only}


class ApprovalError(ValueError):
    pass


def approve_device(
    db: Session,
    device: Device,
    *,
    plan: NetworkPlan,
    name: str,
    group: Group,
    access: Access | None = None,
    static_ip: str | None = None,
) -> Device:
    if device.mac is None:
        raise ApprovalError("a device without a MAC cannot be approved")
    access = access or group.default_access
    if access not in APPROVABLE:
        raise ApprovalError("access must be authorized or lan_only")
    taken = {
        IPv4Address(ip)
        for ip in db.scalars(select(Device.static_ip).where(Device.static_ip.is_not(None), Device.id != device.id))
    }
    if static_ip:
        ip = check_assignment(plan, static_ip, group.ip_range(), taken)
    else:
        ip = next_free(plan, group.ip_range(), taken)
        if ip is None:
            raise ApprovalError(f"no free IP left in group {group.name}")

    previous = device.access
    others = set(db.scalars(select(Device.hostname).where(Device.id != device.id)))
    device.name = name
    device.hostname = hostname_for(name, others)
    device.group = group
    device.static_ip = str(ip)
    device.access = access
    record_event(db, "device.approved", device.mac, {
        "device_id": str(device.id), "name": name, "group": group.name, "ip": str(ip),
        "access": access.value, "previous_access": previous.value,
    })
    return device


def block_device(db: Session, device: Device) -> Device:
    previous = device.access
    device.access = Access.blocked
    record_event(db, "device.blocked", device.mac, {
        "device_id": str(device.id), "name": device.name, "previous_access": previous.value,
    })
    return device

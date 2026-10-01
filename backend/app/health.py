from collections import defaultdict
from ipaddress import AddressValueError, IPv4Address, IPv4Network

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Access, Device, Service
from app.netconfig import load_netconfig

APPROVED = {Access.authorized, Access.lan_only}
RANK = {"ok": 0, "warning": 1, "critical": 2}


def _in_subnet(ip: str | None, subnet) -> bool:
    try:
        return ip is not None and IPv4Address(ip) in subnet
    except (AddressValueError, ValueError):
        return False


def annotate(db: Session, devices: list[Device]) -> list[Device]:
    """Attach `issues` (kind, severity, message) and the worst `health` to each device."""
    subnet = IPv4Network(load_netconfig(db).subnet, strict=False)
    macs = [d.mac for d in devices if d.mac]
    risky: dict[str, list[Service]] = defaultdict(list)
    if macs:
        for row in db.scalars(select(Service).where(
            Service.mac.in_(macs), Service.state == "open", Service.risk != "none", Service.muted.is_(False)
        ).order_by(Service.port)):
            risky[row.mac].append(row)
    holders: dict[str, list[Device]] = defaultdict(list)
    for d in db.scalars(select(Device).where(Device.online.is_(True), Device.last_ip.is_not(None))):
        if _in_subnet(d.last_ip, subnet):
            holders[d.last_ip].append(d)

    for d in devices:
        issues: list[dict[str, str]] = []
        current = d.last_ip if _in_subnet(d.last_ip, subnet) else None
        if d.access in APPROVED and d.online and d.static_ip and current and current != d.static_ip:
            issues.append({"kind": "ip_mismatch", "severity": "critical",
                           "message": f"Using {current} instead of its reserved address {d.static_ip}"})
        if d.online and current and any(other.id != d.id for other in holders.get(current, [])):
            names = ", ".join(sorted(o.name for o in holders[current] if o.id != d.id))
            issues.append({"kind": "ip_conflict", "severity": "critical",
                           "message": f"{current} is also used by {names}"})
        for s in risky.get(d.mac or "", []):
            label = f"{s.port}/{s.proto}" + (f" ({s.service})" if s.service else "")
            issues.append({"kind": "risk", "severity": "critical" if s.risk == "high" else "warning",
                           "message": f"{'High' if s.risk == 'high' else 'Moderate'} risk on port {label}"
                                      + (f": {s.risk_reason}" if s.risk_reason else "")})
        d.issues = issues
        d.health = max((i["severity"] for i in issues), key=RANK.__getitem__, default="ok")
    return devices

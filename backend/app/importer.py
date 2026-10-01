import csv
import io
from dataclasses import asdict, dataclass, field
from ipaddress import IPv4Address

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.events import record_event
from app.models import Access, Device, Group
from app.net.ipplan import (
    AssignmentError,
    IpRange,
    NetworkPlan,
    check_assignment,
    check_group_range,
    infer_group_range,
)
from app.net.mac import is_private_mac, normalize_mac
from app.net.names import hostname_for

REQUIRED = ("Name", "MAC Address", "LAN IP", "Category")
MAX_NAME = 64
PALETTE = ["#6FB7FF", "#B69CF0", "#E58FB8", "#5CC8A8", "#7FD1C4", "#A6D86A", "#E0A84E", "#D9C27A", "#F0765C", "#9AA3A8"]


@dataclass
class ImportReport:
    groups_created: list[str] = field(default_factory=list)
    devices_created: int = 0
    devices_updated: int = 0
    skipped: list[str] = field(default_factory=list)


def _assignable(plan: NetworkPlan, raw_ip: str) -> IPv4Address | None:
    whole = IpRange(plan.subnet.network_address, plan.subnet.broadcast_address)
    try:
        return check_assignment(plan, raw_ip, whole, set())
    except AssignmentError:
        return None


def _create_groups(db: Session, rows: list[dict[str, str]], plan: NetworkPlan, report: ImportReport) -> dict[str, Group]:
    groups = {g.name: g for g in db.scalars(select(Group))}
    ranges = [g.ip_range() for g in groups.values()]
    by_category: dict[str, list[IPv4Address]] = {}
    for row in rows:
        ip = _assignable(plan, row["LAN IP"])
        if ip is not None:
            by_category.setdefault(row["Category"].strip(), []).append(ip)
    for category, ips in sorted(by_category.items(), key=lambda kv: min(kv[1])):
        if not category or category in groups:
            continue
        if len(category) > MAX_NAME:
            report.skipped.append(f"group {category!r}: name longer than {MAX_NAME} characters")
            continue
        rng = infer_group_range(plan, ips)
        try:
            check_group_range(plan, rng, ranges)
        except AssignmentError as exc:
            report.skipped.append(f"group {category!r}: {exc}")
            continue
        group = Group(
            name=category,
            color=PALETTE[len(groups) % len(PALETTE)],
            icon="device",
            range_start=str(rng.start),
            range_end=str(rng.end),
            default_access=Access.authorized,
        )
        db.add(group)
        groups[category] = group
        ranges.append(rng)
        report.groups_created.append(category)
    db.flush()
    return groups


def import_csv(db: Session, text: str, plan: NetworkPlan) -> ImportReport:
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    missing = [c for c in REQUIRED if c not in (reader.fieldnames or [])]
    if missing:
        raise ValueError(f"missing columns: {', '.join(missing)}")
    rows = [{key: (value or "").strip() for key, value in row.items() if key} for row in reader]
    report = ImportReport()
    groups = _create_groups(db, rows, plan, report)

    devices = list(db.scalars(select(Device)))
    by_mac = {d.mac: d for d in devices if d.mac}
    by_name_without_mac = {d.name: d for d in devices if d.mac is None}
    taken = {IPv4Address(d.static_ip) for d in devices if d.static_ip}
    hostnames = {d.hostname for d in devices}
    seen_macs: set[str] = set()

    for line_no, row in enumerate(rows, start=2):
        name = row["Name"].strip()
        category = row["Category"].strip()
        raw_mac = row["MAC Address"].strip()
        if not name:
            report.skipped.append(f"line {line_no}: empty name")
            continue
        if len(name) > MAX_NAME:
            report.skipped.append(f"line {line_no} {name[:20]}…: name longer than {MAX_NAME} characters")
            continue
        group = groups.get(category)
        if group is None:
            report.skipped.append(f"line {line_no} {name}: group {category!r} is not available")
            continue
        mac = None
        if raw_mac:
            try:
                mac = normalize_mac(raw_mac)
            except ValueError as exc:
                report.skipped.append(f"line {line_no} {name}: {exc}")
                continue
            if mac in seen_macs:
                report.skipped.append(f"line {line_no} {name}: duplicate MAC {mac}")
                continue
            seen_macs.add(mac)

        device = by_mac.get(mac) if mac else by_name_without_mac.get(name)
        own_ip = IPv4Address(device.static_ip) if device is not None and device.static_ip else None
        try:
            ip = check_assignment(plan, row["LAN IP"], group.ip_range(), taken - {own_ip})
        except AssignmentError as exc:
            report.skipped.append(f"line {line_no} {name}: {exc}")
            continue

        if device is None:
            device = Device(
                mac=mac,
                name=name,
                hostname=hostname_for(name, hostnames),
                group=group,
                static_ip=str(ip),
                access=group.default_access,
                private_mac=bool(mac) and is_private_mac(mac),
            )
            db.add(device)
            hostnames.add(device.hostname)
            report.devices_created += 1
        else:
            if own_ip is not None:
                taken.discard(own_ip)
            if device.name != name:
                hostnames.discard(device.hostname)
                device.name = name
                device.hostname = hostname_for(name, hostnames)
                hostnames.add(device.hostname)
            device.group = group
            device.static_ip = str(ip)
            report.devices_updated += 1
        taken.add(ip)

    record_event(db, "import.csv", None, asdict(report))
    db.flush()
    return report

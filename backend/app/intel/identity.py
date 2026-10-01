from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.intel.oui import OuiRegistry, default_registry
from app.intel.rules import Fact, facts_from_sighting, facts_from_vendor
from app.models import Device, DeviceFact, Setting, Sighting

CURSOR_KEY = "identity.cursor"
RICH_SOURCES = ("dhcp", "mdns", "netbios", "ssdp")


def upsert_fact(db: Session, mac: str, fact: Fact, observed_at: datetime) -> None:
    if fact.field == "services":
        current = db.scalar(select(DeviceFact.value).where(
            DeviceFact.mac == mac, DeviceFact.field == "services", DeviceFact.source == fact.source
        ))
        if current:
            merged = sorted(set(current.split(", ")) | set(fact.value.split(", ")))
            fact = Fact(fact.field, ", ".join(merged), fact.source, fact.confidence)
    statement = insert(DeviceFact).values(
        mac=mac, field=fact.field, value=fact.value[:255], source=fact.source, confidence=fact.confidence,
        observed_at=observed_at,
    )
    db.execute(statement.on_conflict_do_update(
        constraint="uq_device_facts_mac_field_source",
        set_={"value": statement.excluded.value, "confidence": statement.excluded.confidence,
              "observed_at": statement.excluded.observed_at},
        where=DeviceFact.observed_at <= statement.excluded.observed_at,
    ))


def enrich_once(db: Session, registry: OuiRegistry, *, batch: int = 500) -> int:
    cursor = db.get(Setting, CURSOR_KEY)
    start = int(cursor.value) if cursor is not None and cursor.value is not None else 0
    sightings = db.scalars(select(Sighting).where(Sighting.id > start, Sighting.source.in_(RICH_SOURCES))
                           .order_by(Sighting.id).limit(batch)).all()
    for sighting in sightings:
        for fact in facts_from_sighting(sighting.source, sighting.payload or {}):
            upsert_fact(db, sighting.mac, fact, sighting.ts)
    if sightings:
        db.merge(Setting(key=CURSOR_KEY, value=sightings[-1].id))

    missing = db.scalars(select(Device).where(
        Device.mac.is_not(None), Device.vendor.is_(None), Device.private_mac.is_(False)
    ))
    for device in missing:
        vendor = registry.vendor(device.mac)
        if vendor:
            device.vendor = vendor[:128]
            for fact in facts_from_vendor(vendor):
                upsert_fact(db, device.mac, fact, device.last_seen or device.created_at)
    db.flush()
    return len(sightings)


def identity_once(
    session_factory: Callable[[], AbstractContextManager[Session]], registry: OuiRegistry | None = None
) -> int:
    with session_factory() as db:
        count = enrich_once(db, registry or default_registry())
        db.commit()
        return count

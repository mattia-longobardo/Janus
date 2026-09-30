import enum
import uuid
from datetime import datetime, time
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, Integer, String, Time, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.net.ipplan import IpRange


class Access(enum.StrEnum):
    authorized = "authorized"
    lan_only = "lan_only"
    pending = "pending"
    blocked = "blocked"


ACCESS_TYPE = Enum(Access, name="access")


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    color: Mapped[str] = mapped_column(String(9))
    icon: Mapped[str] = mapped_column(String(32))
    range_start: Mapped[str] = mapped_column(String(15))
    range_end: Mapped[str] = mapped_column(String(15))
    default_access: Mapped[Access] = mapped_column(ACCESS_TYPE)
    offline_alert_hours: Mapped[int | None] = mapped_column(Integer)

    devices: Mapped[list["Device"]] = relationship(back_populates="group")

    def ip_range(self) -> IpRange:
        return IpRange.parse(self.range_start, self.range_end)


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    mac: Mapped[str | None] = mapped_column(String(17), unique=True)
    name: Mapped[str] = mapped_column(String(64))
    hostname: Mapped[str] = mapped_column(String(63), unique=True)
    group_id: Mapped[int | None] = mapped_column(ForeignKey("groups.id"))
    static_ip: Mapped[str | None] = mapped_column(String(15), unique=True)
    access: Mapped[Access] = mapped_column(ACCESS_TYPE)
    vendor: Mapped[str | None] = mapped_column(String(128))
    private_mac: Mapped[bool] = mapped_column(Boolean, default=False)
    online: Mapped[bool] = mapped_column(Boolean, default=False)
    last_ip: Mapped[str | None] = mapped_column(String(15))
    dhcp_hostname: Mapped[str | None] = mapped_column(String(255))
    first_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    group: Mapped[Group | None] = relationship(back_populates="devices")


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    type: Mapped[str] = mapped_column(String(64), index=True)
    mac: Mapped[str | None] = mapped_column(String(17), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[Any] = mapped_column(JSONB, nullable=True)


class Sighting(Base):
    __tablename__ = "sightings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    mac: Mapped[str] = mapped_column(String(17), index=True)
    ip: Mapped[str | None] = mapped_column(String(15))
    source: Mapped[str] = mapped_column(String(8))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class MaintenanceWindow(Base):
    __tablename__ = "maintenance_windows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    start_time: Mapped[time] = mapped_column(Time)
    duration_min: Mapped[int] = mapped_column(Integer)
    days: Mapped[int] = mapped_column(Integer)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    mute_alerts: Mapped[bool] = mapped_column(Boolean, default=True)
    pause_isolation: Mapped[bool] = mapped_column(Boolean, default=True)


class NotificationRule(Base):
    __tablename__ = "notification_rules"

    event_type: Mapped[str] = mapped_column(String(64), primary_key=True)
    channel: Mapped[str] = mapped_column(String(16), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

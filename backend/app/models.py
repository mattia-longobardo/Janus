import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


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


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    mac: Mapped[str | None] = mapped_column(String(17), unique=True)
    name: Mapped[str] = mapped_column(String(64))
    hostname: Mapped[str] = mapped_column(String(63), unique=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"))
    static_ip: Mapped[str | None] = mapped_column(String(15), unique=True)
    access: Mapped[Access] = mapped_column(ACCESS_TYPE)
    vendor: Mapped[str | None] = mapped_column(String(128))
    private_mac: Mapped[bool] = mapped_column(Boolean, default=False)
    online: Mapped[bool] = mapped_column(Boolean, default=False)
    first_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    group: Mapped[Group] = relationship(back_populates="devices")


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

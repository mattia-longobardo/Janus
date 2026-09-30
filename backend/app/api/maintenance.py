from datetime import time

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import MaintenanceWindow

router = APIRouter(prefix="/api/maintenance-windows", tags=["maintenance"])
HHMM = r"^([01]\d|2[0-3]):[0-5]\d$"
REQUIRED = ("name", "start_time", "duration_min", "days", "enabled", "mute_alerts", "pause_isolation")


class WindowIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    start_time: str = Field(pattern=HHMM)
    duration_min: int = Field(ge=1, le=720)
    days: int = Field(ge=1, le=127)
    enabled: bool = True
    mute_alerts: bool = True
    pause_isolation: bool = True


class WindowPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    start_time: str | None = Field(default=None, pattern=HHMM)
    duration_min: int | None = Field(default=None, ge=1, le=720)
    days: int | None = Field(default=None, ge=1, le=127)
    enabled: bool | None = None
    mute_alerts: bool | None = None
    pause_isolation: bool | None = None

    @model_validator(mode="after")
    def _no_nulls(self) -> "WindowPatch":
        for name in REQUIRED:
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


def _out(row: MaintenanceWindow) -> dict:
    return {"id": row.id, "name": row.name, "start_time": row.start_time.strftime("%H:%M"),
            "duration_min": row.duration_min, "days": row.days, "enabled": row.enabled,
            "mute_alerts": row.mute_alerts, "pause_isolation": row.pause_isolation}


def _time(value: str) -> time:
    hours, minutes = value.split(":")
    return time(int(hours), int(minutes))


@router.get("")
def list_windows(db: Session = Depends(get_db)) -> list[dict]:
    return [_out(row) for row in db.scalars(select(MaintenanceWindow).order_by(MaintenanceWindow.start_time))]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_window(body: WindowIn, db: Session = Depends(get_db)) -> dict:
    row = MaintenanceWindow(**{**body.model_dump(), "start_time": _time(body.start_time)})
    db.add(row)
    db.commit()
    return _out(row)


@router.patch("/{window_id}")
def update_window(window_id: int, body: WindowPatch, db: Session = Depends(get_db)) -> dict:
    row = db.get(MaintenanceWindow, window_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "maintenance window not found")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(row, key, _time(value) if key == "start_time" else value)
    db.commit()
    return _out(row)


@router.delete("/{window_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_window(window_id: int, db: Session = Depends(get_db)) -> Response:
    row = db.get(MaintenanceWindow, window_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "maintenance window not found")
    db.delete(row)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

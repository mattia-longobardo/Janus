import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Device, Link, Setting

router = APIRouter(prefix="/api/map", tags=["map"])
LAYOUT_KEY = "map.layout_version"
LAYOUT_VERSION = 2


class PositionIn(BaseModel):
    device_id: uuid.UUID
    x: float = Field(allow_inf_nan=False, ge=-1e6, le=1e6)
    y: float = Field(allow_inf_nan=False, ge=-1e6, le=1e6)


class LinkIn(BaseModel):
    source_id: uuid.UUID
    target_id: uuid.UUID
    kind: Literal["wired", "wifi"]
    label: str | None = Field(default=None, max_length=64)


def _link(link: Link) -> dict[str, Any]:
    return {"id": link.id, "source_id": str(link.source_id), "target_id": str(link.target_id), "kind": link.kind,
            "label": link.label}


@router.get("")
def get_map(db: Session = Depends(get_db)) -> dict[str, Any]:
    placed = db.scalars(select(Device).where(Device.map_x.is_not(None), Device.map_y.is_not(None)))
    row = db.get(Setting, LAYOUT_KEY)
    return {
        "layout_version": row.value if row is not None else 1,
        "positions": [{"device_id": str(d.id), "x": d.map_x, "y": d.map_y} for d in placed],
        "links": [_link(link) for link in db.scalars(select(Link).order_by(Link.id))],
    }


@router.put("/positions")
def put_positions(body: Annotated[list[PositionIn], Body(max_length=1000)], db: Session = Depends(get_db)) -> dict[str, int]:
    updated = 0
    for item in body:
        device = db.get(Device, item.device_id)
        if device is not None:
            device.map_x, device.map_y = item.x, item.y
            updated += 1
    db.merge(Setting(key=LAYOUT_KEY, value=LAYOUT_VERSION))
    db.commit()
    return {"updated": updated}


@router.post("/links", status_code=status.HTTP_201_CREATED)
def create_link(body: LinkIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    if body.source_id == body.target_id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "a device cannot link to itself")
    if db.get(Device, body.source_id) is None or db.get(Device, body.target_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "device not found")
    existing = db.scalar(select(Link).where(or_(
        (Link.source_id == body.source_id) & (Link.target_id == body.target_id),
        (Link.source_id == body.target_id) & (Link.target_id == body.source_id),
    )))
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "these devices are already linked")
    link = Link(source_id=body.source_id, target_id=body.target_id, kind=body.kind, label=body.label)
    db.add(link)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "these devices are already linked") from exc
    return _link(link)


@router.delete("/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_link(link_id: int, db: Session = Depends(get_db)) -> Response:
    link = db.get(Link, link_id)
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "link not found")
    db.delete(link)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

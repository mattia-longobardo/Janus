from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import settings
from app.cutover import PiholeAdmin, preflight
from app.db import get_db
from app.netconfig import load_netconfig
from app.pihole.client import shared_session

router = APIRouter(prefix="/api/cutover", tags=["cutover"])


@router.get("/preflight")
def cutover_preflight(db: Session = Depends(get_db)) -> dict[str, Any]:
    url = load_netconfig(db).pihole_url
    with PiholeAdmin(url, settings.pihole_password, shared=shared_session(url)) as client:
        return preflight(db, client).as_dict()

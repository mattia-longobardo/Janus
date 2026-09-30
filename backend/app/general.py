from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Setting

TIMEZONE_KEY = "general.timezone"


def current_tz(db: Session) -> ZoneInfo:
    row = db.get(Setting, TIMEZONE_KEY)
    name = row.value if row is not None and isinstance(row.value, str) and row.value else settings.timezone
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")

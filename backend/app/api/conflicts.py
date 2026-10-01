from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


def commit_or_409(db: Session, detail: str) -> None:
    """Commit, turning a unique-constraint race (two requests at once) into 409 instead of a 500."""
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail) from exc

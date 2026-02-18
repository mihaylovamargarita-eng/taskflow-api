"""Health check API routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db

router = APIRouter()


@router.get("/live", status_code=status.HTTP_200_OK)
def liveness() -> dict[str, str]:
    """Return process liveness status."""
    return {"status": "ok"}


@router.get("/ready", status_code=status.HTTP_200_OK)
def readiness(db: Session = Depends(get_db)) -> dict[str, str]:
    """Return readiness status after checking database connectivity."""
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not ready.",
        ) from exc
    return {"status": "ok"}


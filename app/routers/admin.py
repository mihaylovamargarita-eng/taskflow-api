"""Admin API routes protected by role-based access control."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import get_current_admin
from app.config import get_settings
from app.database import get_db
from app.models import RefreshToken, Task, User, UserRole
from app.schemas import (
    AdminStatsResponse,
    AdminUserRoleUpdate,
    AdminUserStatusUpdate,
    ErrorResponse,
    UserResponse,
)
from app.security import limiter

router = APIRouter(
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
        404: {"model": ErrorResponse, "description": "Not found"},
        422: {"model": ErrorResponse, "description": "Validation error"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
    }
)
settings = get_settings()


@router.get("/users", response_model=list[UserResponse], status_code=status.HTTP_200_OK)
@limiter.limit(settings.RATE_LIMIT_READ)
def list_users(
    request: Request,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> list[User]:
    """List users for admin management."""
    return db.query(User).order_by(User.created_at.desc()).offset(skip).limit(limit).all()


@router.patch("/users/{user_id}/role", response_model=UserResponse, status_code=status.HTTP_200_OK)
@limiter.limit(settings.RATE_LIMIT_WRITE)
def update_user_role(
    request: Request,
    user_id: int,
    payload: AdminUserRoleUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> User:
    """Update role for a user account."""
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    if user.role == UserRole.ADMIN and payload.role != UserRole.ADMIN:
        admin_count = db.query(func.count(User.id)).filter(User.role == UserRole.ADMIN).scalar() or 0
        if admin_count <= 1 and user.id == current_admin.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove the last admin role.",
            )

    user.role = payload.role
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/users/{user_id}/status", response_model=UserResponse, status_code=status.HTTP_200_OK)
@limiter.limit(settings.RATE_LIMIT_WRITE)
def update_user_status(
    request: Request,
    user_id: int,
    payload: AdminUserStatusUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> User:
    """Activate or deactivate a user account."""
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    user.is_active = payload.is_active
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/stats", response_model=AdminStatsResponse, status_code=status.HTTP_200_OK)
@limiter.limit(settings.RATE_LIMIT_READ)
def admin_stats(
    request: Request,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> AdminStatsResponse:
    """Return aggregate platform stats for administrators."""
    total_users = db.query(func.count(User.id)).scalar() or 0
    active_users = db.query(func.count(User.id)).filter(User.is_active.is_(True)).scalar() or 0
    total_tasks = db.query(func.count(Task.id)).scalar() or 0
    active_refresh_sessions = (
        db.query(func.count(RefreshToken.id)).filter(RefreshToken.revoked_at.is_(None)).scalar() or 0
    )
    return AdminStatsResponse(
        total_users=total_users,
        active_users=active_users,
        total_tasks=total_tasks,
        active_refresh_sessions=active_refresh_sessions,
    )

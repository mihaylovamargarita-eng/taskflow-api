"""Pydantic schemas for request and response validation."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import TaskPriority, TaskStatus, UserRole


class UserCreate(BaseModel):
    """Schema for user registration payload."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "user@example.com",
                "password": "StrongPass123",
            }
        }
    )


class UserResponse(BaseModel):
    """Schema for user data returned by the API."""

    id: int
    email: EmailStr
    role: UserRole
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TaskCreate(BaseModel):
    """Schema for creating a task."""

    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "title": "Prepare sprint plan",
                "description": "Finalize sprint backlog and priorities",
                "status": "todo",
                "priority": "high",
            }
        },
    )


class TaskUpdate(BaseModel):
    """Schema for partial task updates."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "status": "in_progress",
                "priority": "medium",
            }
        },
    )


class TaskResponse(BaseModel):
    """Schema for task data returned by the API."""

    id: int
    user_id: int
    title: str
    description: str | None
    status: TaskStatus
    priority: TaskPriority
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    """Schema for JWT token responses."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "<jwt_access_token>",
                "refresh_token": "<jwt_refresh_token>",
                "token_type": "bearer",
            }
        }
    )


class TokenData(BaseModel):
    """Schema for JWT payload data."""

    email: str | None = None
    token_type: str | None = None
    jti: str | None = None


class RefreshTokenRequest(BaseModel):
    """Schema for refresh token exchange requests."""

    refresh_token: str

    model_config = ConfigDict(
        json_schema_extra={"example": {"refresh_token": "<jwt_refresh_token>"}}
    )


class AdminUserRoleUpdate(BaseModel):
    """Schema for admin role updates."""

    role: UserRole


class AdminUserStatusUpdate(BaseModel):
    """Schema for admin user activation updates."""

    is_active: bool


class AdminStatsResponse(BaseModel):
    """Schema for admin platform aggregate metrics."""

    total_users: int
    active_users: int
    total_tasks: int
    active_refresh_sessions: int


class ErrorResponse(BaseModel):
    """Standardized API error response schema."""

    detail: Any
    error_code: str
    request_id: str | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "detail": "Could not validate credentials.",
                "error_code": "unauthorized",
                "request_id": "1e5ebd89-5a6a-4a25-b56a-62c55fbf8c1d",
            }
        }
    )

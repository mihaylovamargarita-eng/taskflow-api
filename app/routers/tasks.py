"""Task management API routes."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models import Task, TaskPriority, TaskStatus, User
from app.security import limiter
from app.schemas import ErrorResponse, TaskCreate, TaskResponse, TaskUpdate

router = APIRouter(
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
        404: {"model": ErrorResponse, "description": "Not found"},
        409: {"model": ErrorResponse, "description": "Conflict"},
        422: {"model": ErrorResponse, "description": "Validation error"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
    }
)
settings = get_settings()

_status_order = {
    TaskStatus.TODO: 0,
    TaskStatus.IN_PROGRESS: 1,
    TaskStatus.DONE: 2,
}


def _normalize_title(raw_title: str) -> str:
    """Normalize task title by trimming and collapsing inner whitespace."""
    return " ".join(raw_title.split())


@router.get("", response_model=list[TaskResponse], status_code=status.HTTP_200_OK)
@limiter.limit(settings.RATE_LIMIT_READ)
def list_tasks(
    request: Request,
    status_filter: TaskStatus | None = Query(default=None, alias="status"),
    priority_filter: TaskPriority | None = Query(default=None, alias="priority"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Task]:
    """List current user's tasks with optional filters and pagination."""
    query = db.query(Task).filter(Task.user_id == current_user.id)

    if status_filter is not None:
        query = query.filter(Task.status == status_filter)
    if priority_filter is not None:
        query = query.filter(Task.priority == priority_filter)

    tasks = query.order_by(Task.created_at.desc()).offset(skip).limit(limit).all()
    return tasks


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.RATE_LIMIT_WRITE)
def create_task(
    request: Request,
    payload: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Task:
    """Create a new task for the authenticated user."""
    current_count = db.query(Task).filter(Task.user_id == current_user.id).count()
    if current_count >= settings.TASK_MAX_PER_USER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Task limit reached ({settings.TASK_MAX_PER_USER}).",
        )

    normalized_title = _normalize_title(payload.title)
    if not normalized_title:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Task title cannot be blank.",
        )

    task = Task(
        user_id=current_user.id,
        title=normalized_title,
        description=payload.description,
        status=payload.status,
        priority=payload.priority,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.get("/{task_id}", response_model=TaskResponse, status_code=status.HTTP_200_OK)
@limiter.limit(settings.RATE_LIMIT_READ)
def get_task(
    request: Request,
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Task:
    """Get a single task by ID after validating ownership."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")
    if task.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
    return task


@router.put("/{task_id}", response_model=TaskResponse, status_code=status.HTTP_200_OK)
@limiter.limit(settings.RATE_LIMIT_WRITE)
def update_task(
    request: Request,
    task_id: int,
    payload: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Task:
    """Update fields provided in the request for an existing user task."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")
    if task.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one updatable field is required.",
        )

    if task.status == TaskStatus.DONE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Completed tasks are immutable.",
        )

    if "status" in update_data:
        next_status = TaskStatus(update_data["status"])
        if _status_order[next_status] < _status_order[task.status]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Task status regression is not allowed.",
            )

    if "title" in update_data and update_data["title"] is not None:
        normalized_title = _normalize_title(update_data["title"])
        if not normalized_title:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Task title cannot be blank.",
            )
        update_data["title"] = normalized_title

    for field, value in update_data.items():
        setattr(task, field, value)
    task.updated_at = datetime.now(timezone.utc)

    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(settings.RATE_LIMIT_WRITE)
def delete_task(
    request: Request,
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """Delete a task after validating ownership."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")
    if task.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    db.delete(task)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

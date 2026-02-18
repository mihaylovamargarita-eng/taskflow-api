"""Authentication API routes."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy.orm import Session

from app.auth import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    get_current_user,
    get_password_hash,
    hash_token_identifier,
    verify_password,
)
from app.config import get_settings
from app.database import get_db
from app.models import RefreshToken, User
from app.security import limiter
from app.schemas import ErrorResponse, RefreshTokenRequest, Token, UserCreate, UserResponse

router = APIRouter(
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
        422: {"model": ErrorResponse, "description": "Validation error"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
    }
)
settings = get_settings()

email_adapter = TypeAdapter(EmailStr)


def _as_utc(dt: datetime) -> datetime:
    """Normalize database datetimes to timezone-aware UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Bad request"},
    },
)
@limiter.limit(settings.RATE_LIMIT_AUTH)
def register_user(request: Request, payload: UserCreate, db: Session = Depends(get_db)) -> User:
    """Register a new user account."""
    existing_user = db.query(User).filter(User.email == payload.email).first()
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already registered.",
        )

    user = User(
        email=payload.email,
        hashed_password=get_password_hash(payload.password),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post(
    "/login",
    response_model=Token,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid credentials"},
    },
    openapi_extra={
        "requestBody": {
            "content": {
                "application/x-www-form-urlencoded": {
                    "example": {
                        "username": "user@example.com",
                        "password": "StrongPass123",
                    }
                }
            }
        }
    },
)
@limiter.limit(settings.RATE_LIMIT_AUTH)
def login_user(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> Token:
    """Authenticate user credentials and return access and refresh tokens."""
    try:
        email = email_adapter.validate_python(form_data.username)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user = db.query(User).filter(User.email == email).first()
    if user is None or not verify_password(form_data.password, user.hashed_password) or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": user.email})
    refresh_token, refresh_jti, refresh_expires_at = create_refresh_token(data={"sub": user.email})

    refresh_session = RefreshToken(
        user_id=user.id,
        jti_hash=hash_token_identifier(refresh_jti),
        expires_at=refresh_expires_at,
    )
    db.add(refresh_session)
    db.commit()

    return Token(access_token=access_token, refresh_token=refresh_token, token_type="bearer")


@router.post(
    "/refresh",
    response_model=Token,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid refresh token"},
    },
)
@limiter.limit(settings.RATE_LIMIT_AUTH)
def refresh_access_token(
    request: Request,
    payload: RefreshTokenRequest,
    db: Session = Depends(get_db),
) -> Token:
    """Rotate refresh token and issue a new access/refresh token pair."""
    token_data = decode_refresh_token(payload.refresh_token)
    if token_data.jti is None or token_data.email is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    now = datetime.now(timezone.utc)
    current_token_hash = hash_token_identifier(token_data.jti)
    token_session = db.query(RefreshToken).filter(RefreshToken.jti_hash == current_token_hash).first()
    if token_session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if token_session.revoked_at is not None:
        db.query(RefreshToken).filter(
            RefreshToken.user_id == token_session.user_id,
            RefreshToken.revoked_at.is_(None),
        ).update({RefreshToken.revoked_at: now}, synchronize_session=False)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token reuse detected. Active sessions were revoked.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if _as_utc(token_session.expires_at) <= now:
        token_session.revoked_at = now
        db.add(token_session)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == token_session.user_id, User.email == token_data.email).first()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": user.email})
    new_refresh_token, new_refresh_jti, new_refresh_expires_at = create_refresh_token(data={"sub": user.email})
    new_refresh_hash = hash_token_identifier(new_refresh_jti)

    token_session.revoked_at = now
    token_session.replaced_by_jti_hash = new_refresh_hash
    db.add(token_session)
    db.add(
        RefreshToken(
            user_id=user.id,
            jti_hash=new_refresh_hash,
            expires_at=new_refresh_expires_at,
        )
    )
    db.commit()

    return Token(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(settings.RATE_LIMIT_AUTH)
def logout_user(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """Revoke all active refresh sessions for the authenticated user."""
    now = datetime.now(timezone.utc)
    db.query(RefreshToken).filter(
        RefreshToken.user_id == current_user.id,
        RefreshToken.revoked_at.is_(None),
    ).update({RefreshToken.revoked_at: now}, synchronize_session=False)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserResponse, status_code=status.HTTP_200_OK)
@limiter.limit(settings.RATE_LIMIT_READ)
def read_current_user(request: Request, current_user: User = Depends(get_current_user)) -> User:
    """Return the authenticated user's profile."""
    return current_user

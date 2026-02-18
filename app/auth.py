"""Authentication utilities and dependencies for TaskFlow API."""

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

from app.config import get_settings
from app.database import get_db
from app.models import User, UserRole
from app.schemas import TokenData

settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/auth/login",
    description="OAuth2 password flow. Use email as the username field and include bearer token as `Authorization: Bearer <token>`.",
)


def _credentials_exception(detail: str = "Could not validate credentials.") -> HTTPException:
    """Build a standardized 401 exception for authentication failures."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_password_hash(password: str) -> str:
    """Hash a plain-text password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against a bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "type": "access", "jti": str(uuid.uuid4())})
    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )
    return encoded_jwt


def create_refresh_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
) -> tuple[str, str, datetime]:
    """Create a signed JWT refresh token and return token, jti, and expiry."""
    to_encode = data.copy()
    jti = str(uuid.uuid4())
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "type": "refresh", "jti": jti})
    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )
    return encoded_jwt, jti, expire


def hash_token_identifier(jti: str) -> str:
    """Hash a token identifier before storing it in the database."""
    return hashlib.sha256(jti.encode("utf-8")).hexdigest()


def _decode_token(token: str, expected_type: str) -> TokenData:
    """Decode and validate a JWT token for the expected token type."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        email = payload.get("sub")
        token_type = payload.get("type")
        jti = payload.get("jti")
        if not email or token_type != expected_type:
            raise _credentials_exception("Invalid token payload.")
        if expected_type == "refresh" and not jti:
            raise _credentials_exception("Invalid token payload.")
        return TokenData(email=email, token_type=token_type, jti=jti)
    except ExpiredSignatureError as exc:
        raise _credentials_exception("Token has expired.") from exc
    except InvalidTokenError as exc:
        raise _credentials_exception() from exc


def decode_access_token(token: str) -> TokenData:
    """Decode and validate a JWT access token."""
    return _decode_token(token, expected_type="access")


def decode_refresh_token(token: str) -> TokenData:
    """Decode and validate a JWT refresh token."""
    return _decode_token(token, expected_type="refresh")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Return the authenticated user from the provided bearer token."""
    token_data = decode_access_token(token)
    user = db.query(User).filter(User.email == token_data.email).first()
    if user is None:
        raise _credentials_exception()
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account.",
        )
    return user


def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    """Return current user only if they hold the admin role."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions.",
        )
    return current_user

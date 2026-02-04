from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional
from jose import JWTError, jwt
import re

from .database import SessionLocal
from .core.config import settings
from . import crud, models

security = HTTPBearer()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        token = credentials.credentials
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = crud.get_user_by_username(db, username=username)
    if user is None:
        raise credentials_exception

    return user


def get_optional_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security, use_cache=False), db: Session = Depends(get_db)) -> Optional[models.User]:
    if not credentials:
        return None
    try:
        token = credentials.credentials
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
    except JWTError:
        return None  # invalid token, treat as anonymous

    user = crud.get_user_by_username(db, username=username)
    if user and user.is_active:
        return user
    return None


def get_current_active_user(current_user: models.User = Depends(get_current_user)):
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


async def validate_input(data: str) -> bool:
    if re.search(r"[<>{}$]", data):
        return False
    return True


async def sanitize_output(data: dict) -> dict:
    sensitive_fields = ["password", "secret", "token"]
    return {k: v for k, v in data.items() if k not in sensitive_fields}

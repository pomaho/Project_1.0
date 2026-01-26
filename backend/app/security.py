from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional

from jose import jwt
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_access_token(subject: str, expires_seconds: int) -> str:
    payload = {
        "sub": subject,
        "exp": datetime.utcnow() + timedelta(seconds=expires_seconds),
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def create_refresh_token(subject: str, expires_seconds: int) -> str:
    payload = {
        "sub": subject,
        "exp": datetime.utcnow() + timedelta(seconds=expires_seconds),
        "type": "refresh",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def create_download_token(file_id: str, user_id: str, expires_seconds: int) -> str:
    payload = {
        "sub": user_id,
        "file_id": file_id,
        "exp": datetime.utcnow() + timedelta(seconds=expires_seconds),
        "type": "download",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> Optional[dict[str, Any]]:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except Exception:
        return None

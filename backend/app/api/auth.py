from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.audit import log_action
from app.schemas import LoginRequest, RefreshRequest, TokenAccess, TokenPair
from app.security import create_access_token, create_refresh_token, decode_token, verify_password
from app.config import settings

router = APIRouter()


@router.post("/login", response_model=TokenPair)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenPair:
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User inactive")
    access = create_access_token(user.id, settings.jwt_access_ttl_seconds)
    refresh = create_refresh_token(user.id, settings.jwt_refresh_ttl_seconds)
    log_action(db, user_id=user.id, action=models.AuditAction.login)
    db.commit()
    return TokenPair(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenAccess)
def refresh(payload: RefreshRequest) -> TokenAccess:
    token_data = decode_token(payload.refresh_token)
    if not token_data or token_data.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    access = create_access_token(token_data["sub"], settings.jwt_access_ttl_seconds)
    return TokenAccess(access_token=access)


@router.post("/logout")
def logout() -> dict:
    return {"status": "ok"}

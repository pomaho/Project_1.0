from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str


class TokenAccess(BaseModel):
    access_token: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    email: EmailStr
    role: str
    is_active: bool
    created_at: datetime


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    role: str


class UserUpdate(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None


class SearchResultItem(BaseModel):
    id: str
    thumb_url: str
    medium_url: str
    keywords: List[str]
    shot_at: Optional[datetime] = None
    orientation: str


class SearchResponse(BaseModel):
    items: List[SearchResultItem]
    next_cursor: Optional[str] = None
    total: Optional[int] = None
    total_all: Optional[int] = None
    returned: Optional[int] = None
    job_id: Optional[str] = None


class FileDetail(BaseModel):
    id: str
    filename: str
    original_key: str
    size_bytes: int
    mime: str
    width: Optional[int] = None
    height: Optional[int] = None
    orientation: str
    shot_at: Optional[datetime] = None
    title: Optional[str] = None
    description: Optional[str] = None
    keywords: List[str]
    thumb_url: str
    medium_url: str


class KeywordUpdateRequest(BaseModel):
    add: List[str] = []
    remove: List[str] = []


class DownloadTokenResponse(BaseModel):
    token: str


class AuditLogOut(BaseModel):
    id: str
    user_id: str
    action: str
    meta: dict
    created_at: datetime


class DownloadLogOut(BaseModel):
    id: str
    user_id: str
    user_email: EmailStr
    file_id: str
    filename: str
    ip: str
    created_at: datetime

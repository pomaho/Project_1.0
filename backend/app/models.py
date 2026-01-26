from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    BigInteger,
    JSON,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db import Base


class Role(str, enum.Enum):
    admin = "admin"
    editor = "editor"
    viewer = "viewer"


class StorageMode(str, enum.Enum):
    filesystem = "filesystem"
    minio = "minio"


class Orientation(str, enum.Enum):
    portrait = "portrait"
    landscape = "landscape"
    square = "square"
    unknown = "unknown"


class AuditAction(str, enum.Enum):
    login = "login"
    search = "search"
    download = "download"
    keywords_update = "keywords_update"
    user_manage = "user_manage"
    reindex = "reindex"
    rescan = "rescan"


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(320), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(Role), nullable=False, default=Role.viewer)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class File(Base):
    __tablename__ = "files"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    storage_mode = Column(Enum(StorageMode), nullable=False)
    original_key = Column(Text, nullable=False)
    filename = Column(Text, nullable=False)
    ext = Column(String(16), nullable=False)
    mime = Column(String(128), nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    mtime = Column(DateTime, nullable=False)
    sha1 = Column(String(40), nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    orientation = Column(Enum(Orientation), nullable=False, default=Orientation.unknown)
    shot_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)
    duplicate_of = Column(String(36), ForeignKey("files.id"), nullable=True)

    keywords = relationship("Keyword", secondary="file_keywords", back_populates="files")


class Keyword(Base):
    __tablename__ = "keywords"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    value_norm = Column(Text, nullable=False, unique=True, index=True)
    value_display = Column(Text, nullable=False)
    usage_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    files = relationship("File", secondary="file_keywords", back_populates="keywords")


class FileKeyword(Base):
    __tablename__ = "file_keywords"
    __table_args__ = (UniqueConstraint("file_id", "keyword_id", name="uq_file_keyword"),)

    file_id = Column(String(36), ForeignKey("files.id"), primary_key=True)
    keyword_id = Column(String(36), ForeignKey("keywords.id"), primary_key=True)


class Preview(Base):
    __tablename__ = "previews"

    file_id = Column(String(36), ForeignKey("files.id"), primary_key=True)
    thumb_key = Column(Text, nullable=False)
    medium_key = Column(Text, nullable=False)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    action = Column(Enum(AuditAction), nullable=False)
    meta = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

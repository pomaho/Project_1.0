from __future__ import annotations

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app import models


def missing_text(column) -> object:
    return func.trim(func.coalesce(column, "")) == ""


def metadata_pending_clause() -> object:
    return or_(
        models.File.metadata_checked_at.is_(None),
        models.File.metadata_checked_at < models.File.mtime,
    )


def count_pending_metadata(session: Session) -> int:
    return (
        session.query(models.File.id)
        .filter(models.File.deleted_at.is_(None), metadata_pending_clause())
        .count()
    )


def missing_metadata_counts(session: Session) -> dict[str, int]:
    missing_keywords = (
        session.query(models.File.id)
        .filter(models.File.deleted_at.is_(None), models.File.keyword_count == 0)
        .count()
    )
    missing_text_count = (
        session.query(models.File.id)
        .filter(
            models.File.deleted_at.is_(None),
            missing_text(models.File.title) | missing_text(models.File.description),
        )
        .count()
    )
    missing_shot_at = (
        session.query(models.File.id)
        .filter(models.File.deleted_at.is_(None), models.File.shot_at.is_(None))
        .count()
    )
    return {
        "missing_keywords": missing_keywords,
        "missing_text": missing_text_count,
        "missing_shot_at": missing_shot_at,
    }

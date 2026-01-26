from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app import models


def log_action(
    db: Session,
    *,
    user_id: str,
    action: models.AuditAction,
    meta: dict[str, Any] | None = None,
) -> None:
    record = models.AuditLog(
        user_id=user_id,
        action=action,
        meta=meta or {},
        created_at=datetime.utcnow(),
    )
    db.add(record)

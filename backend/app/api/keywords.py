from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.deps import get_current_user
from app.keywords import normalize_keyword

router = APIRouter()


@router.get("/suggest")
def suggest(
    prefix: str = Query(default=""),
    limit: int = Query(default=20, ge=1, le=50),
    _: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    norm = normalize_keyword(prefix)
    query = db.query(models.Keyword)
    if norm:
        query = query.filter(models.Keyword.value_norm.like(f"{norm}%"))
    items = (
        query.order_by(desc(models.Keyword.usage_count))
        .limit(limit)
        .all()
    )
    return [{"value": item.value_display, "count": item.usage_count} for item in items]

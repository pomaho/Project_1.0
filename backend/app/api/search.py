from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.deps import get_current_user
from app.audit import log_action
from app.schemas import SearchResponse, SearchResultItem
from app.search_client import get_client, search_documents
from app.search_parser import evaluate, extract_positive_terms, parse_query

router = APIRouter()


@router.get("", response_model=SearchResponse)
def search(
    q: str = Query(default=""),
    limit: int = Query(default=60, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SearchResponse:
    total_all = db.query(models.File).filter(models.File.deleted_at.is_(None)).count()
    if not q.strip():
        rows = (
            db.query(models.File)
            .filter(models.File.deleted_at.is_(None))
            .order_by(models.File.mtime.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )
        items = [
            SearchResultItem(
                id=file_row.id,
                thumb_url=f"/api/files/{file_row.id}/preview?size=thumb",
                medium_url=f"/api/files/{file_row.id}/preview?size=medium",
                keywords=[kw.value_display for kw in file_row.keywords],
                shot_at=file_row.shot_at,
                orientation=file_row.orientation.value,
            )
            for file_row in rows
        ]
        next_cursor = str(offset + limit) if len(items) == limit else None
        return SearchResponse(
            items=items,
            next_cursor=next_cursor,
            total=total_all,
            total_all=total_all,
            returned=len(items),
        )

    ast = parse_query(q)
    query_terms = extract_positive_terms(ast)
    query_text = " ".join(query_terms)

    payload = {
        "q": query_text,
        "limit": min(limit * 3, 500),
        "offset": offset,
    }

    with get_client() as client:
        data = search_documents(client, payload)

    hits = data.get("hits", [])
    ids = [hit.get("id") for hit in hits if hit.get("id")]
    if not ids:
        return SearchResponse(items=[], next_cursor=None)

    files = (
        db.query(models.File)
        .filter(models.File.id.in_(ids), models.File.deleted_at.is_(None))
        .all()
    )
    file_map = {file_row.id: file_row for file_row in files}

    filtered_items: list[SearchResultItem] = []
    for hit in hits:
        file_id = hit.get("id")
        file_row = file_map.get(file_id)
        if not file_row:
            continue
        keywords_norm = {kw.value_norm for kw in file_row.keywords}
        text_parts = [
            file_row.title or "",
            file_row.description or "",
            file_row.filename or "",
            " ".join(kw.value_display for kw in file_row.keywords),
        ]
        text_blob = " ".join(part for part in text_parts if part)
        if not evaluate(ast, keywords_norm, text_blob):
            continue
        filtered_items.append(
            SearchResultItem(
                id=file_row.id,
                thumb_url=f"/api/files/{file_row.id}/preview?size=thumb",
                medium_url=f"/api/files/{file_row.id}/preview?size=medium",
                keywords=[kw.value_display for kw in file_row.keywords],
                shot_at=file_row.shot_at,
                orientation=file_row.orientation.value,
            )
        )
        if len(filtered_items) >= limit:
            break

    if not filtered_items:
        return SearchResponse(
            items=[],
            next_cursor=None,
            total=0,
            total_all=total_all,
            returned=0,
        )

    next_cursor = None
    estimated_total = int(data.get("estimatedTotalHits", 0) or 0)
    if estimated_total > offset + limit:
        next_cursor = str(offset + limit)
    log_action(
        db,
        user_id=_.id,
        action=models.AuditAction.search,
        meta={"q": q, "offset": offset, "limit": limit},
    )
    db.commit()
    return SearchResponse(
        items=filtered_items,
        next_cursor=next_cursor,
        total=estimated_total,
        total_all=total_all,
        returned=len(filtered_items),
    )

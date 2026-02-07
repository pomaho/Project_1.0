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
    limit: int = Query(default=10000, ge=1, le=10000),
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

    max_fetch = min(max(limit * 3, 500), 10000)
    payload = {
        "q": query_text,
        "limit": max_fetch,
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
    estimated_total = int(
        data.get("estimatedTotalHits")
        or data.get("totalHits")
        or data.get("nbHits")
        or 0
    )
    if len(filtered_items) == len(hits):
        if estimated_total > offset + limit:
            next_cursor = str(offset + limit)
    else:
        if estimated_total <= 0:
            estimated_total = offset + len(filtered_items)

    total_exact = 0
    scan_offset = 0
    chunk_size = 1000
    with get_client() as client:
        while True:
            scan_payload = {
                "q": query_text,
                "limit": chunk_size,
                "offset": scan_offset,
            }
            scan_data = search_documents(client, scan_payload)
            scan_hits = scan_data.get("hits", [])
            if not scan_hits:
                break
            scan_ids = [hit.get("id") for hit in scan_hits if hit.get("id")]
            if scan_ids:
                scan_files = (
                    db.query(models.File)
                    .filter(models.File.id.in_(scan_ids), models.File.deleted_at.is_(None))
                    .all()
                )
                scan_file_map = {file_row.id: file_row for file_row in scan_files}
                for hit in scan_hits:
                    file_id = hit.get("id")
                    file_row = scan_file_map.get(file_id)
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
                    if evaluate(ast, keywords_norm, text_blob):
                        total_exact += 1
            scan_offset += len(scan_hits)
            scan_estimated_total = int(
                scan_data.get("estimatedTotalHits")
                or scan_data.get("totalHits")
                or scan_data.get("nbHits")
                or 0
            )
            if scan_estimated_total and scan_offset >= scan_estimated_total:
                break
            if len(scan_hits) < chunk_size:
                break

    if total_exact > offset + len(filtered_items):
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
        total=total_exact,
        total_all=total_all,
        returned=len(filtered_items),
    )

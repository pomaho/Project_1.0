from __future__ import annotations

import json
import time
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.deps import get_current_user
from app.schemas import SearchResponse, SearchResultItem
from app.search_client import get_client, search_documents
from app.redis_client import get_redis
from app.tasks import async_search_task

router = APIRouter()

ASYNC_PREFIX = "search:async"
RESULTS_TTL_SECONDS = 3600
CHUNK_SIZE = 1000


def _meta_key(job_id: str) -> str:
    return f"{ASYNC_PREFIX}:{job_id}:meta"


def _list_key(job_id: str) -> str:
    return f"{ASYNC_PREFIX}:{job_id}:list"


def _seen_key(job_id: str) -> str:
    return f"{ASYNC_PREFIX}:{job_id}:seen"


def _set_meta(job_id: str, payload: dict) -> None:
    client = get_redis()
    client.hset(_meta_key(job_id), mapping=payload)
    client.expire(_meta_key(job_id), RESULTS_TTL_SECONDS)


def _get_meta(job_id: str) -> dict:
    client = get_redis()
    raw = client.hgetall(_meta_key(job_id))
    return raw or {}


def _set_ttl(job_id: str) -> None:
    client = get_redis()
    client.expire(_list_key(job_id), RESULTS_TTL_SECONDS)
    client.expire(_seen_key(job_id), RESULTS_TTL_SECONDS)


def _append_results(job_id: str, file_ids: list[str]) -> None:
    if not file_ids:
        return
    client = get_redis()
    pipe = client.pipeline()
    for file_id in file_ids:
        pipe.rpush(_list_key(job_id), file_id)
        pipe.sadd(_seen_key(job_id), file_id)
    pipe.execute()


@router.post("/async/start", response_model=SearchResponse)
def start_async_search(
    q: str = Query(default=""),
    limit: int = Query(default=60, ge=1, le=200),
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
        next_cursor = str(limit) if len(items) == limit else None
        return SearchResponse(
            items=items,
            next_cursor=next_cursor,
            total=total_all,
            total_all=total_all,
            returned=len(items),
        )

    job_id = str(uuid.uuid4())
    query_text = q.strip()

    initial_ids: list[str] = []
    scan_offset = 0

    with get_client() as client:
        while len(initial_ids) < limit:
            payload = {
                "q": query_text,
                "limit": CHUNK_SIZE,
                "offset": scan_offset,
            }
            data = search_documents(client, payload)
            hits = data.get("hits", [])
            if not hits:
                break
            ids = [hit.get("id") for hit in hits if hit.get("id")]
            if ids:
                files = (
                    db.query(models.File)
                    .filter(models.File.id.in_(ids), models.File.deleted_at.is_(None))
                    .all()
                )
                file_map = {file_row.id: file_row for file_row in files}
                for hit in hits:
                    file_id = hit.get("id")
                    file_row = file_map.get(file_id)
                    if not file_row:
                        continue
                    if file_id in initial_ids:
                        continue
                    initial_ids.append(file_id)
                    if len(initial_ids) >= limit:
                        break
            scan_offset += len(hits)
            estimated_total = int(
                data.get("estimatedTotalHits")
                or data.get("totalHits")
                or data.get("nbHits")
                or 0
            )
            if estimated_total and scan_offset >= estimated_total:
                break
            if len(hits) < CHUNK_SIZE:
                break

    _append_results(job_id, initial_ids)
    _set_meta(
        job_id,
        {
            "status": "running",
            "query": q,
            "query_text": query_text,
            "total_found": str(len(initial_ids)),
            "scanned": str(scan_offset),
            "next_offset": str(scan_offset),
            "updated_at": datetime.utcnow().isoformat(),
        },
    )
    _set_ttl(job_id)

    async_search_task.delay(job_id)

    items = (
        db.query(models.File)
        .filter(models.File.id.in_(initial_ids), models.File.deleted_at.is_(None))
        .all()
    )
    file_map = {file_row.id: file_row for file_row in items}
    ordered_items: list[SearchResultItem] = []
    for file_id in initial_ids:
        file_row = file_map.get(file_id)
        if not file_row:
            continue
        ordered_items.append(
            SearchResultItem(
                id=file_row.id,
                thumb_url=f"/api/files/{file_row.id}/preview?size=thumb",
                medium_url=f"/api/files/{file_row.id}/preview?size=medium",
                keywords=[kw.value_display for kw in file_row.keywords],
                shot_at=file_row.shot_at,
                orientation=file_row.orientation.value,
            )
        )

    next_cursor = None
    if len(initial_ids) >= limit:
        next_cursor = str(limit)

    return SearchResponse(
        items=ordered_items,
        next_cursor=next_cursor,
        total=len(initial_ids),
        total_all=total_all,
        returned=len(ordered_items),
        job_id=job_id,
    )


@router.get("/async/{job_id}", response_model=SearchResponse)
def async_search_page(
    job_id: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=60, ge=1, le=200),
    _: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SearchResponse:
    client = get_redis()
    meta = _get_meta(job_id)
    total_all = db.query(models.File).filter(models.File.deleted_at.is_(None)).count()
    total_found = int(meta.get("total_found") or 0)

    ids = client.lrange(_list_key(job_id), offset, offset + limit - 1)
    if not ids:
        return SearchResponse(items=[], next_cursor=None, total=total_found, total_all=total_all, returned=0)

    files = (
        db.query(models.File)
        .filter(models.File.id.in_(ids), models.File.deleted_at.is_(None))
        .all()
    )
    file_map = {file_row.id: file_row for file_row in files}

    items: list[SearchResultItem] = []
    for file_id in ids:
        file_row = file_map.get(file_id)
        if not file_row:
            continue
        items.append(
            SearchResultItem(
                id=file_row.id,
                thumb_url=f"/api/files/{file_row.id}/preview?size=thumb",
                medium_url=f"/api/files/{file_row.id}/preview?size=medium",
                keywords=[kw.value_display for kw in file_row.keywords],
                shot_at=file_row.shot_at,
                orientation=file_row.orientation.value,
            )
        )

    next_cursor = None
    if total_found > offset + len(items):
        next_cursor = str(offset + limit)

    return SearchResponse(
        items=items,
        next_cursor=next_cursor,
        total=total_found,
        total_all=total_all,
        returned=len(items),
        job_id=job_id,
    )


@router.get("/async/{job_id}/status")
def async_search_status(
    job_id: str,
    _: models.User = Depends(get_current_user),
) -> dict:
    meta = _get_meta(job_id)
    return {
        "status": meta.get("status") or "unknown",
        "total_found": int(meta.get("total_found") or 0),
        "scanned": int(meta.get("scanned") or 0),
        "updated_at": meta.get("updated_at"),
    }

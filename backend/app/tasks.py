from __future__ import annotations

import mimetypes
import os
import json
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app import models
from app.celery_app import celery_app
from app.config import settings
from app.db import SessionLocal
from app.keywords import normalize_keyword
from app.metadata import extract_metadata
from app.previews import generate_preview, write_preview
from app.search_client import ensure_index, get_client, upsert_documents
from app.search_index import build_doc, remove_file, upsert_file
from app.redis_client import get_redis

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}

PREVIEW_STATUS_KEY = "preview:refresh:status"
PREVIEW_EXCLUSIVE_KEY = "preview:exclusive"
ORPHAN_STATUS_KEY = "preview:orphans:status"
REINDEX_STATUS_KEY = "search:reindex:status"
INDEX_CANCEL_PREFIX = "index:cancel"


def _normalize_path(path: str) -> str:
    # Normalize Windows-style paths inside Linux containers:
    # - unify separators to "/"
    # - collapse duplicate slashes
    # - lowercase for case-insensitive compare
    normalized = path.replace("\\", "/").strip()

    while "//" in normalized:
        normalized = normalized.replace("//", "/")
    return normalized.lower().rstrip("/")


def _cancel_key(run_id: str) -> str:
    return f"{INDEX_CANCEL_PREFIX}:{run_id}"


def is_preview_exclusive() -> bool:
    client = get_redis()
    return bool(client.get(PREVIEW_EXCLUSIVE_KEY))


def set_preview_exclusive(enabled: bool) -> None:
    client = get_redis()
    if enabled:
        client.set(PREVIEW_EXCLUSIVE_KEY, "1")
    else:
        client.delete(PREVIEW_EXCLUSIVE_KEY)


def set_orphan_status(payload: dict) -> None:
    client = get_redis()
    client.set(ORPHAN_STATUS_KEY, json.dumps(payload))


def get_orphan_status() -> dict | None:
    client = get_redis()
    raw = client.get(ORPHAN_STATUS_KEY)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def set_reindex_status(payload: dict) -> None:
    client = get_redis()
    client.set(REINDEX_STATUS_KEY, json.dumps(payload))


def get_reindex_status() -> dict | None:
    client = get_redis()
    raw = client.get(REINDEX_STATUS_KEY)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _reindex_incr_completed(count: int) -> None:
    client = get_redis()
    client.incrby(f"{REINDEX_STATUS_KEY}:completed", count)
    completed_raw = client.get(f"{REINDEX_STATUS_KEY}:completed")
    completed = int(completed_raw or 0)
    status = get_reindex_status() or {}
    status.update(
        {
            "status": "running",
            "completed": completed,
            "count": completed,
            "updated_at": datetime.utcnow().isoformat(),
        }
    )
    set_reindex_status(status)


def _is_cancelled(run_id: str) -> bool:
    client = get_redis()
    return bool(client.get(_cancel_key(run_id)))


def _set_cancelled(run_id: str) -> None:
    client = get_redis()
    client.set(_cancel_key(run_id), "1")


def _clear_cancelled(run_id: str) -> None:
    client = get_redis()
    client.delete(_cancel_key(run_id))


def _is_excluded(path: str, excluded: list[str]) -> bool:
    if not excluded:
        return False
    normalized = _normalize_path(path)
    for item in excluded:
        if not item:
            continue
        target = _normalize_path(item)
        if normalized == target or normalized.startswith(target + "/"):
            return True
    return False


def _orientation(width: int | None, height: int | None) -> models.Orientation:
    if not width or not height:
        return models.Orientation.unknown
    if width == height:
        return models.Orientation.square
    if width > height:
        return models.Orientation.landscape
    return models.Orientation.portrait


@celery_app.task(name="scan_storage")
def scan_storage_task(run_id: str | None = None) -> dict:
    if settings.storage_mode != "filesystem":
        return {"status": "skipped", "reason": "non-filesystem mode"}

    root = Path(settings.filesystem_root)
    if not root.exists():
        return {"status": "error", "reason": "filesystem root missing"}
    excluded = settings.exclude_paths_list

    session: Session = SessionLocal()
    try:
        if run_id:
            run = session.query(models.IndexRun).filter(models.IndexRun.id == run_id).first()
        else:
            run = models.IndexRun(status=models.IndexRunStatus.running)
            session.add(run)
            session.flush()
            run_id = run.id

        rows_all = session.query(
            models.File.id,
            models.File.original_key,
            models.File.mtime,
            models.File.size_bytes,
            models.File.deleted_at,
        ).all()
        existing = {
            row.original_key: (row.id, row.mtime, row.size_bytes, row.deleted_at)
            for row in rows_all
        }
        existing_active_keys = {row.original_key for row in rows_all if row.deleted_at is None}
        missing_keywords_ids = {
            row.id
            for row in session.query(models.File.id)
            .outerjoin(models.FileKeyword, models.FileKeyword.file_id == models.File.id)
            .filter(models.FileKeyword.file_id.is_(None), models.File.deleted_at.is_(None))
        }
        missing_text_ids = {
            row.id
            for row in session.query(models.File.id).filter(
                models.File.deleted_at.is_(None),
                (models.File.title.is_(None)) | (models.File.description.is_(None)),
            )
        }
        seen_keys: set[str] = set()
        created = 0
        updated = 0
        restored = 0
        scanned = 0
        last_flush = 0

        def _abort_run() -> dict:
            if run_id:
                session.query(models.IndexRun).filter(models.IndexRun.id == run_id).update(
                    {
                        "status": models.IndexRunStatus.failed,
                        "error": "cancelled by operator",
                        "finished_at": datetime.utcnow(),
                    }
                )
                session.commit()
                _clear_cancelled(run_id)
            return {"status": "cancelled"}

        for dirpath, dirnames, filenames in os.walk(root):
            if run_id and _is_cancelled(run_id):
                return _abort_run()
            if _is_excluded(dirpath, excluded):
                dirnames[:] = []
                continue
            if excluded:
                dirnames[:] = [
                    name
                    for name in dirnames
                    if not _is_excluded(os.path.join(dirpath, name), excluded)
                ]
            for filename in filenames:
                if run_id and _is_cancelled(run_id):
                    return _abort_run()
                ext = Path(filename).suffix.lower()
                if ext not in SUPPORTED_EXTS:
                    continue
                full_path = str(Path(dirpath) / filename)
                try:
                    stat = os.stat(full_path)
                except OSError:
                    continue

                seen_keys.add(full_path)
                scanned += 1
                existing_row = existing.get(full_path)
                if not existing_row:
                    mime, _ = mimetypes.guess_type(filename)
                    file_row = models.File(
                        storage_mode=models.StorageMode.filesystem,
                        original_key=full_path,
                        filename=filename,
                        ext=ext.lstrip("."),
                        mime=mime or "application/octet-stream",
                        size_bytes=stat.st_size,
                        mtime=datetime.utcfromtimestamp(stat.st_mtime),
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                    )
                    session.add(file_row)
                    session.flush()
                    extract_metadata_task.delay(file_row.id)
                    created += 1
                else:
                    file_id, mtime, size, deleted_at = existing_row
                    current_mtime = datetime.utcfromtimestamp(stat.st_mtime)
                    if deleted_at is not None:
                        session.query(models.File).filter(models.File.id == file_id).update(
                            {
                                "deleted_at": None,
                                "size_bytes": stat.st_size,
                                "mtime": current_mtime,
                                "updated_at": datetime.utcnow(),
                            }
                        )
                        extract_metadata_task.delay(file_id)
                        upsert_search_doc_task.delay(file_id)
                        restored += 1
                    elif current_mtime != mtime or stat.st_size != size:
                        session.query(models.File).filter(models.File.id == file_id).update(
                            {
                                "size_bytes": stat.st_size,
                                "mtime": current_mtime,
                                "updated_at": datetime.utcnow(),
                            }
                        )
                        extract_metadata_task.delay(file_id)
                        updated += 1
                    else:
                        if file_id in missing_keywords_ids:
                            extract_metadata_task.delay(file_id)
                        elif file_id in missing_text_ids:
                            extract_metadata_task.delay(file_id)

                if run_id and scanned - last_flush >= 500:
                    session.query(models.IndexRun).filter(models.IndexRun.id == run_id).update(
                        {
                            "scanned_count": scanned,
                            "created_count": created,
                            "updated_count": updated,
                            "restored_count": restored,
                        }
                    )
                    session.commit()
                    last_flush = scanned

        deleted_keys = existing_active_keys - seen_keys
        if deleted_keys:
            deleted_ids = [
                row.id
                for row in session.query(models.File).filter(models.File.original_key.in_(deleted_keys))
            ]
            session.query(models.File).filter(models.File.original_key.in_(deleted_keys)).update(
                {"deleted_at": datetime.utcnow()}, synchronize_session=False
            )
            session.commit()
            for file_id in deleted_ids:
                remove_search_doc_task.delay(file_id)

        if run_id:
            session.query(models.IndexRun).filter(models.IndexRun.id == run_id).update(
                {
                    "status": models.IndexRunStatus.completed,
                    "scanned_count": scanned,
                    "created_count": created,
                    "updated_count": updated,
                    "restored_count": restored,
                    "deleted_count": len(deleted_keys),
                    "finished_at": datetime.utcnow(),
                }
            )
        session.commit()
        if run_id:
            _clear_cancelled(run_id)
        # Cleanup previews for deleted files after each rescan
        gc_previews_task.delay()
        return {
            "status": "ok",
            "created": created,
            "updated": updated,
            "restored": restored,
            "deleted": len(deleted_keys),
        }
    except Exception as exc:
        if run_id:
            session.query(models.IndexRun).filter(models.IndexRun.id == run_id).update(
                {
                    "status": models.IndexRunStatus.failed,
                    "error": str(exc),
                    "finished_at": datetime.utcnow(),
                }
            )
            session.commit()
        raise
    finally:
        session.close()


@celery_app.task(name="extract_metadata")
def extract_metadata_task(file_id: str) -> dict:
    if is_preview_exclusive():
        extract_metadata_task.apply_async(
            args=[file_id],
            countdown=settings.preview_exclusive_retry_seconds,
        )
        return {"status": "deferred", "reason": "preview_exclusive"}

    session: Session = SessionLocal()
    try:
        file_row = session.query(models.File).filter(models.File.id == file_id).first()
        if not file_row:
            return {"status": "missing"}

        meta = extract_metadata(file_row.original_key)
        file_row.mime = meta.get("mime", file_row.mime)
        file_row.width = meta.get("width")
        file_row.height = meta.get("height")
        file_row.shot_at = meta.get("shot_at")
        file_row.title = meta.get("title")
        file_row.description = meta.get("description")
        file_row.orientation = _orientation(file_row.width, file_row.height)
        file_row.updated_at = datetime.utcnow()

        raw_keywords = meta.get("keywords", [])
        normalized = {}
        for value in raw_keywords:
            norm = normalize_keyword(str(value))
            if not norm:
                continue
            normalized.setdefault(norm, str(value).strip())

        existing_keywords = {kw.value_norm: kw for kw in file_row.keywords}
        new_keywords = []
        added = 0
        removed = 0

        for norm, display in normalized.items():
            keyword = session.query(models.Keyword).filter(models.Keyword.value_norm == norm).first()
            if not keyword:
                keyword = models.Keyword(value_norm=norm, value_display=display, usage_count=0)
                session.add(keyword)
                session.flush()
            if norm not in existing_keywords:
                keyword.usage_count += 1
                added += 1
            new_keywords.append(keyword)

        removed_norms = set(existing_keywords.keys()) - set(normalized.keys())
        for norm in removed_norms:
            keyword = existing_keywords[norm]
            if keyword.usage_count > 0:
                keyword.usage_count -= 1
            removed += 1

        file_row.keywords = new_keywords
        session.commit()
        upsert_search_doc_task.delay(file_row.id)
        return {"status": "ok", "added": added, "removed": removed}
    finally:
        session.close()


@celery_app.task(name="generate_previews")
def generate_previews_task(file_id: str) -> dict:
    if settings.storage_mode != "filesystem":
        return {"status": "skipped", "reason": "non-filesystem mode"}

    session: Session = SessionLocal()
    try:
        file_row = session.query(models.File).filter(models.File.id == file_id).first()
        if not file_row or file_row.deleted_at:
            return {"status": "missing"}

        previews_root = settings.previews_root
        preview_data = generate_preview(file_row.original_key, "medium")
        preview_key = write_preview(previews_root, file_row.id, "medium", preview_data)

        preview_row = session.query(models.Preview).filter(models.Preview.file_id == file_row.id).first()
        if preview_row:
            preview_row.thumb_key = preview_key
            preview_row.medium_key = preview_key
            preview_row.updated_at = datetime.utcnow()
        else:
            preview_row = models.Preview(
                file_id=file_row.id,
                thumb_key=preview_key,
                medium_key=preview_key,
                updated_at=datetime.utcnow(),
            )
            session.add(preview_row)

        session.commit()
        return {"status": "ok"}
    finally:
        session.close()


@celery_app.task(name="upsert_search_doc")
def upsert_search_doc_task(file_id: str) -> dict:
    if is_preview_exclusive():
        upsert_search_doc_task.apply_async(
            args=[file_id],
            countdown=settings.preview_exclusive_retry_seconds,
        )
        return {"status": "deferred", "reason": "preview_exclusive"}

    session: Session = SessionLocal()
    try:
        upsert_file(session, file_id)
        return {"status": "ok"}
    finally:
        session.close()


@celery_app.task(name="remove_search_doc")
def remove_search_doc_task(file_id: str) -> dict:
    remove_file(file_id)
    return {"status": "ok"}


@celery_app.task(name="reindex_search")
def reindex_search_task() -> dict:
    session: Session = SessionLocal()
    try:
        started_at = datetime.utcnow().isoformat()
        total = (
            session.query(models.File.id)
            .filter(models.File.deleted_at.is_(None))
            .count()
        )
        client = get_redis()
        client.set(f"{REINDEX_STATUS_KEY}:completed", 0)
        set_reindex_status(
            {
                "status": "running",
                "count": 0,
                "completed": 0,
                "total": total,
                "updated_at": started_at,
                "started_at": started_at,
            }
        )
        chunk: list[str] = []
        for (file_id,) in (
            session.query(models.File.id)
            .filter(models.File.deleted_at.is_(None))
            .yield_per(2000)
        ):
            chunk.append(file_id)
            if len(chunk) >= 2000:
                reindex_search_chunk.delay(chunk)
                chunk = []
        if chunk:
            reindex_search_chunk.delay(chunk)
        return {"status": "queued", "total": total}
    finally:
        session.close()


@celery_app.task(name="reindex_search_chunk")
def reindex_search_chunk(file_ids: list[str]) -> dict:
    if not file_ids:
        return {"status": "skipped"}
    session: Session = SessionLocal()
    try:
        rows = (
            session.query(models.File)
            .filter(models.File.id.in_(file_ids), models.File.deleted_at.is_(None))
            .all()
        )
        docs = [build_doc(row) for row in rows]
        with get_client() as client:
            ensure_index(client)
            if docs:
                upsert_documents(client, docs)
        _reindex_incr_completed(len(docs))
        status = get_reindex_status() or {}
        total = int(status.get("total") or 0)
        completed = int(status.get("completed") or 0)
        if total and completed >= total:
            set_reindex_status(
                {
                    **status,
                    "status": "completed",
                    "updated_at": datetime.utcnow().isoformat(),
                }
            )
        return {"status": "ok", "count": len(docs)}
    finally:
        session.close()


@celery_app.task(name="gc_previews")
def gc_previews_task() -> dict:
    if settings.storage_mode != "filesystem":
        return {"status": "skipped", "reason": "non-filesystem mode"}

    session: Session = SessionLocal()
    removed = 0
    try:
        rows = (
            session.query(models.Preview, models.File)
            .join(models.File, models.File.id == models.Preview.file_id)
            .filter(models.File.deleted_at.isnot(None))
            .all()
        )
        for preview_row, file_row in rows:
            for key in (preview_row.thumb_key, preview_row.medium_key):
                try:
                    if key and os.path.exists(key):
                        os.remove(key)
                except OSError:
                    continue
            try:
                os.rmdir(os.path.dirname(preview_row.thumb_key))
            except OSError:
                pass
            session.delete(preview_row)
            removed += 1
        session.commit()
        return {"status": "ok", "removed": removed}
    finally:
        session.close()


@celery_app.task(name="queue_missing_previews")
def queue_missing_previews_task() -> dict:
    if settings.storage_mode != "filesystem":
        return {"status": "skipped", "reason": "non-filesystem mode"}

    session: Session = SessionLocal()
    queued = 0
    try:
        rows = (
            session.query(models.File.id)
            .outerjoin(models.Preview, models.Preview.file_id == models.File.id)
            .filter(models.File.deleted_at.is_(None), models.Preview.file_id.is_(None))
            .all()
        )
        for (file_id,) in rows:
            generate_previews_task.delay(file_id)
            queued += 1
        return {"status": "ok", "queued": queued}
    finally:
        session.close()


@celery_app.task(name="queue_missing_metadata")
def queue_missing_metadata_task() -> dict:
    if is_preview_exclusive():
        queue_missing_metadata_task.apply_async(
            countdown=settings.preview_exclusive_retry_seconds,
        )
        return {"status": "deferred", "reason": "preview_exclusive"}

    session: Session = SessionLocal()
    queued = 0
    try:
        rows = (
            session.query(models.File.id)
            .outerjoin(models.FileKeyword, models.FileKeyword.file_id == models.File.id)
            .filter(
                models.File.deleted_at.is_(None),
                (models.FileKeyword.file_id.is_(None))
                | (models.File.title.is_(None))
                | (models.File.description.is_(None)),
            )
            .all()
        )
        for (file_id,) in rows:
            extract_metadata_task.delay(file_id)
            queued += 1
        return {"status": "ok", "queued": queued}
    finally:
        session.close()


@celery_app.task(name="cancel_index_run")
def cancel_index_run(run_id: str) -> dict:
    _set_cancelled(run_id)
    return {"status": "queued"}


def _compute_preview_counts(session: Session) -> dict:
    total_files = (
        session.query(models.File.id)
        .filter(models.File.deleted_at.is_(None))
        .count()
    )
    missing_previews = (
        session.query(models.File.id)
        .outerjoin(models.Preview, models.Preview.file_id == models.File.id)
        .filter(models.File.deleted_at.is_(None), models.Preview.file_id.is_(None))
        .count()
    )
    total_previews = (
        session.query(models.Preview)
        .join(models.File, models.File.id == models.Preview.file_id)
        .filter(models.File.deleted_at.is_(None))
        .count()
    )
    progress = 1.0 if total_files == 0 else (total_files - missing_previews) / total_files
    return {
        "total_files": total_files,
        "total_previews": total_previews,
        "missing_previews": missing_previews,
        "progress": progress,
    }


def set_preview_status(payload: dict) -> None:
    client = get_redis()
    client.set(PREVIEW_STATUS_KEY, json.dumps(payload))


def get_preview_status() -> dict | None:
    client = get_redis()
    raw = client.get(PREVIEW_STATUS_KEY)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _remove_empty_dirs(root: str) -> int:
    removed = 0
    for dirpath, dirnames, filenames in os.walk(root, topdown=False):
        if dirpath == root:
            continue
        if not dirnames and not filenames:
            try:
                os.rmdir(dirpath)
                removed += 1
            except OSError:
                continue
    return removed


@celery_app.task(name="refresh_previews_cycle")
def refresh_previews_cycle(round_num: int, max_rounds: int | None = None) -> dict:
    session: Session = SessionLocal()
    try:
        max_rounds = max_rounds or settings.preview_check_rounds
        set_preview_exclusive(True)
        counts = _compute_preview_counts(session)
        payload = {
            "status": "running" if round_num < max_rounds else "completed",
            "round": round_num,
            "max_rounds": max_rounds,
            "total_files": counts["total_files"],
            "total_previews": counts["total_previews"],
            "missing_previews": counts["missing_previews"],
            "progress": counts["progress"],
            "updated_at": datetime.utcnow().isoformat(),
        }
        set_preview_status(payload)

        if counts["missing_previews"] > 0:
            queue_missing_previews_task.delay()

        if round_num < max_rounds:
            refresh_previews_cycle.apply_async(
                args=[round_num + 1, max_rounds],
                countdown=settings.preview_check_interval_seconds,
            )
        else:
            payload["status"] = "completed"
            set_preview_status(payload)
            set_preview_exclusive(False)

        return payload
    finally:
        session.close()


@celery_app.task(name="cleanup_orphan_previews")
def cleanup_orphan_previews_task() -> dict:
    if settings.storage_mode != "filesystem":
        return {"status": "skipped", "reason": "non-filesystem mode"}

    previews_root = settings.previews_root
    session: Session = SessionLocal()
    try:
        expected = {
            row[0]
            for row in session.query(models.Preview.thumb_key)
            .filter(models.Preview.thumb_key.isnot(None))
            .all()
        }
        expected.update(
            {
                row[0]
                for row in session.query(models.Preview.medium_key)
                .filter(models.Preview.medium_key.isnot(None))
                .all()
            }
        )

        total_orphans = 0
        for dirpath, _, filenames in os.walk(previews_root):
            for name in filenames:
                full_path = str(Path(dirpath) / name)
                if full_path not in expected:
                    total_orphans += 1

        payload = {
            "status": "running",
            "total_orphans": total_orphans,
            "deleted": 0,
            "processed": 0,
            "updated_at": datetime.utcnow().isoformat(),
            "started_at": datetime.utcnow().isoformat(),
        }
        set_orphan_status(payload)

        deleted = 0
        processed = 0
        for dirpath, _, filenames in os.walk(previews_root):
            for name in filenames:
                full_path = str(Path(dirpath) / name)
                if full_path not in expected:
                    try:
                        os.remove(full_path)
                        deleted += 1
                    except OSError:
                        pass
                processed += 1
                if processed % 500 == 0:
                    set_orphan_status(
                        {
                            "status": "running",
                            "total_orphans": total_orphans,
                            "deleted": deleted,
                            "processed": processed,
                            "updated_at": datetime.utcnow().isoformat(),
                            "started_at": payload["started_at"],
                        }
                    )

        removed_dirs = _remove_empty_dirs(previews_root)
        set_orphan_status(
            {
                "status": "completed",
                "total_orphans": total_orphans,
                "deleted": deleted,
                "processed": processed,
                "removed_dirs": removed_dirs,
                "updated_at": datetime.utcnow().isoformat(),
                "started_at": payload["started_at"],
            }
        )
        return {
            "status": "ok",
            "total_orphans": total_orphans,
            "deleted": deleted,
            "removed_dirs": removed_dirs,
        }
    finally:
        session.close()

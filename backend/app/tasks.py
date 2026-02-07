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
from app.search_index import remove_file, upsert_file
from app.redis_client import get_redis

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}

PREVIEW_STATUS_KEY = "preview:refresh:status"


def _normalize_path(path: str) -> str:
    # Normalize Windows-style paths inside Linux containers:
    # - unify separators to "/"
    # - collapse duplicate slashes
    # - lowercase for case-insensitive compare
    normalized = path.replace("\\", "/").strip()

    while "//" in normalized:
        normalized = normalized.replace("//", "/")
    return normalized.lower().rstrip("/")


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
        missing_preview_ids = {
            row.id
            for row in session.query(models.File.id)
            .outerjoin(models.Preview, models.Preview.file_id == models.File.id)
            .filter(models.Preview.file_id.is_(None), models.File.deleted_at.is_(None))
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

        for dirpath, dirnames, filenames in os.walk(root):
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
                        generate_previews_task.delay(file_id)
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
                        if file_id in missing_preview_ids:
                            generate_previews_task.delay(file_id)

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
        # Cleanup previews for deleted files after each rescan
        gc_previews_task.delay()
        # Ensure any missing previews are queued after each rescan
        queue_missing_previews_task.delay()
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
        generate_previews_task.delay(file_row.id)
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
        thumb_data = generate_preview(file_row.original_key, "thumb")
        medium_data = generate_preview(file_row.original_key, "medium")

        thumb_key = write_preview(previews_root, file_row.id, "thumb", thumb_data)
        medium_key = write_preview(previews_root, file_row.id, "medium", medium_data)

        preview_row = session.query(models.Preview).filter(models.Preview.file_id == file_row.id).first()
        if preview_row:
            preview_row.thumb_key = thumb_key
            preview_row.medium_key = medium_key
            preview_row.updated_at = datetime.utcnow()
        else:
            preview_row = models.Preview(
                file_id=file_row.id,
                thumb_key=thumb_key,
                medium_key=medium_key,
                updated_at=datetime.utcnow(),
            )
            session.add(preview_row)

        session.commit()
        return {"status": "ok"}
    finally:
        session.close()


@celery_app.task(name="upsert_search_doc")
def upsert_search_doc_task(file_id: str) -> dict:
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
        ids = [
            row.id
            for row in session.query(models.File.id).filter(models.File.deleted_at.is_(None))
        ]
        for file_id in ids:
            upsert_file(session, file_id)
        return {"status": "ok", "count": len(ids)}
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


@celery_app.task(name="refresh_previews_cycle")
def refresh_previews_cycle(round_num: int, max_rounds: int | None = None) -> dict:
    session: Session = SessionLocal()
    try:
        max_rounds = max_rounds or settings.preview_check_rounds
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

        return payload
    finally:
        session.close()

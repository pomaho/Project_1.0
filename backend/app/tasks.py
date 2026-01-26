from __future__ import annotations

import mimetypes
import os
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

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}


def _orientation(width: int | None, height: int | None) -> models.Orientation:
    if not width or not height:
        return models.Orientation.unknown
    if width == height:
        return models.Orientation.square
    if width > height:
        return models.Orientation.landscape
    return models.Orientation.portrait


@celery_app.task(name="scan_storage")
def scan_storage_task() -> dict:
    if settings.storage_mode != "filesystem":
        return {"status": "skipped", "reason": "non-filesystem mode"}

    root = Path(settings.filesystem_root)
    if not root.exists():
        return {"status": "error", "reason": "filesystem root missing"}

    session: Session = SessionLocal()
    try:
        existing = {
            row.original_key: (row.id, row.mtime, row.size_bytes)
            for row in session.query(models.File).filter(models.File.deleted_at.is_(None))
        }
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

        for dirpath, _, filenames in os.walk(root):
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
                    file_id, mtime, size = existing_row
                    current_mtime = datetime.utcfromtimestamp(stat.st_mtime)
                    if current_mtime != mtime or stat.st_size != size:
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

        deleted_keys = set(existing.keys()) - seen_keys
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

        session.commit()
        return {"status": "ok", "created": created, "updated": updated, "deleted": len(deleted_keys)}
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

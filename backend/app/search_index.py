from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app import models
from app.search_client import ensure_index, get_client, upsert_documents, delete_document


def build_doc(file_row: models.File) -> dict:
    keywords_display = [kw.value_display for kw in file_row.keywords]
    keywords_norm = [kw.value_norm for kw in file_row.keywords]
    return {
        "id": file_row.id,
        "keywords": keywords_display,
        "keywords_norm": keywords_norm,
        "filename": file_row.filename,
        "title": file_row.title,
        "description": file_row.description,
        "shot_at": file_row.shot_at.isoformat() if file_row.shot_at else None,
        "mtime": file_row.mtime.isoformat() if file_row.mtime else None,
        "orientation": file_row.orientation.value if file_row.orientation else None,
        "width": file_row.width,
        "height": file_row.height,
        "collections": [],
        "deleted": file_row.deleted_at is not None,
        "updated_at": datetime.utcnow().isoformat(),
    }


def upsert_file(session: Session, file_id: str) -> None:
    file_row = session.query(models.File).filter(models.File.id == file_id).first()
    if not file_row:
        return
    with get_client() as client:
        ensure_index(client)
        doc = build_doc(file_row)
        upsert_documents(client, [doc])


def remove_file(file_id: str) -> None:
    with get_client() as client:
        ensure_index(client)
        delete_document(client, file_id)

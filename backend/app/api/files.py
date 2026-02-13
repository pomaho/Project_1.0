from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.db import get_db
from app.audit import log_action
from app.deps import get_current_user, require_editor
from app.keywords import normalize_keyword
from app.previews import preview_path
from app.schemas import DownloadTokenResponse, FileDetail, KeywordUpdateRequest
from app.rate_limit import check_download_limit
from app.security import create_download_token, decode_token
from app.tasks import generate_previews_task, upsert_search_doc_task

router = APIRouter()


@router.get("/{file_id}", response_model=FileDetail)
def get_file(
    file_id: str,
    _: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileDetail:
    file_row = db.query(models.File).filter(models.File.id == file_id).first()
    if not file_row or file_row.deleted_at:
        raise HTTPException(status_code=404, detail="File not found")
    return FileDetail(
        id=file_row.id,
        filename=file_row.filename,
        original_key=file_row.original_key,
        size_bytes=file_row.size_bytes,
        mime=file_row.mime,
        width=file_row.width,
        height=file_row.height,
        orientation=file_row.orientation.value,
        shot_at=file_row.shot_at,
        title=file_row.title,
        description=file_row.description,
        keywords=[kw.value_display for kw in file_row.keywords],
        thumb_url=f"/api/files/{file_row.id}/preview?size=thumb",
        medium_url=f"/api/files/{file_row.id}/preview?size=medium",
    )


@router.patch("/{file_id}/keywords", response_model=FileDetail)
def update_keywords(
    file_id: str,
    payload: KeywordUpdateRequest,
    _: models.User = Depends(require_editor),
    db: Session = Depends(get_db),
) -> FileDetail:
    file_row = db.query(models.File).filter(models.File.id == file_id).first()
    if not file_row or file_row.deleted_at:
        raise HTTPException(status_code=404, detail="File not found")

    existing = {kw.value_norm: kw for kw in file_row.keywords}
    to_add = {}
    for value in payload.add:
        norm = normalize_keyword(value)
        if norm:
            to_add[norm] = value.strip()
    to_remove = {normalize_keyword(value) for value in payload.remove if normalize_keyword(value)}

    new_keywords = []
    for norm, keyword in existing.items():
        if norm in to_remove:
            if keyword.usage_count > 0:
                keyword.usage_count -= 1
            continue
        new_keywords.append(keyword)

    for norm, display in to_add.items():
        if norm in existing and norm not in to_remove:
            continue
        keyword = db.query(models.Keyword).filter(models.Keyword.value_norm == norm).first()
        if not keyword:
            keyword = models.Keyword(value_norm=norm, value_display=display, usage_count=0)
            db.add(keyword)
            db.flush()
        keyword.usage_count += 1
        new_keywords.append(keyword)

    file_row.keywords = new_keywords
    log_action(
        db,
        user_id=_.id,
        action=models.AuditAction.keywords_update,
        meta={"file_id": file_row.id, "added": len(to_add), "removed": len(to_remove)},
    )
    db.commit()
    upsert_search_doc_task.delay(file_row.id)

    return FileDetail(
        id=file_row.id,
        filename=file_row.filename,
        original_key=file_row.original_key,
        size_bytes=file_row.size_bytes,
        mime=file_row.mime,
        width=file_row.width,
        height=file_row.height,
        orientation=file_row.orientation.value,
        shot_at=file_row.shot_at,
        title=file_row.title,
        description=file_row.description,
        keywords=[kw.value_display for kw in file_row.keywords],
        thumb_url=f"/api/files/{file_row.id}/preview?size=thumb",
        medium_url=f"/api/files/{file_row.id}/preview?size=medium",
    )


@router.post("/{file_id}/download-token", response_model=DownloadTokenResponse)
def download_token(
    file_id: str,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DownloadTokenResponse:
    file_row = db.query(models.File).filter(models.File.id == file_id).first()
    if not file_row or file_row.deleted_at:
        raise HTTPException(status_code=404, detail="File not found")
    if not check_download_limit(user.id, settings.rate_limit_downloads_per_min):
        raise HTTPException(status_code=429, detail="Download rate limit exceeded")
    token = create_download_token(file_id, user.id, settings.download_token_ttl_seconds)
    log_action(
        db,
        user_id=user.id,
        action=models.AuditAction.download,
        meta={"file_id": file_id, "event": "token"},
    )
    db.commit()
    return DownloadTokenResponse(token=token)


@router.get("/{file_id}/preview")
def get_preview(
    file_id: str,
    request: Request,
    size: str = Query(default="thumb", pattern="^(thumb|medium)$"),
    token: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> FileResponse:
    auth_header = request.headers.get("authorization")
    token_value = None
    if auth_header and auth_header.lower().startswith("bearer "):
        token_value = auth_header.split(" ", 1)[1]
    elif token:
        token_value = token
    if not token_value:
        raise HTTPException(status_code=401, detail="Missing token")
    token_data = decode_token(token_value)
    if not token_data or token_data.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token")
    user = (
        db.query(models.User)
        .filter(models.User.id == token_data.get("sub"), models.User.is_active.is_(True))
        .first()
    )
    if not user:
        raise HTTPException(status_code=401, detail="Invalid user")

    file_row = db.query(models.File).filter(models.File.id == file_id).first()
    if not file_row or file_row.deleted_at:
        raise HTTPException(status_code=404, detail="File not found")
    if settings.storage_mode != "filesystem":
        raise HTTPException(status_code=501, detail="Preview mode not configured")

    path = preview_path(settings.previews_root, file_id, size)  # type: ignore[arg-type]
    if not path.exists():
        generate_previews_task.delay(file_id)
        raise HTTPException(status_code=404, detail="Preview not ready")

    return FileResponse(path, media_type="image/webp")

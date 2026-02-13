from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.db import get_db
from app.audit import log_action
from app.security import decode_token

router = APIRouter()


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


@router.get("/{token}")
def download_file(token: str, request: Request, db: Session = Depends(get_db)) -> FileResponse:
    token_data = decode_token(token)
    if not token_data or token_data.get("type") != "download":
        raise HTTPException(status_code=401, detail="Invalid token")
    file_id = token_data.get("file_id")
    file_row = db.query(models.File).filter(models.File.id == file_id).first()
    if not file_row or file_row.deleted_at:
        raise HTTPException(status_code=404, detail="File not found")
    if settings.storage_mode != "filesystem":
        raise HTTPException(status_code=501, detail="Download mode not configured")
    user_id = token_data.get("sub")
    if user_id:
        log_action(
            db,
            user_id=user_id,
            action=models.AuditAction.download,
            meta={
                "event": "download",
                "file_id": file_id,
                "filename": file_row.filename,
                "ip": _client_ip(request),
            },
        )
        db.commit()
    return FileResponse(file_row.original_key, media_type=file_row.mime, filename=file_row.filename)

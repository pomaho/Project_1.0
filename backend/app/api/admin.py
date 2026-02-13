from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import models
from app.audit import log_action
from app.config import settings
from app.db import get_db
from app.deps import require_admin
from app.schemas import AuditLogOut, UserCreate, UserOut, UserUpdate
from app.security import hash_password
from app.tasks import (
    get_orphan_status,
    get_preview_status,
    get_reindex_status,
    get_shot_at_status,
    reindex_after_metadata_task,
    cancel_index_run,
    cleanup_orphan_previews_task,
    cancel_preview_tasks,
    queue_missing_metadata_task,
    queue_missing_previews_task,
    refresh_shot_at_task,
    refresh_previews_cycle,
    reindex_search_task,
    scan_storage_task,
    set_orphan_status,
    set_preview_exclusive,
    set_preview_status,
    set_shot_at_status,
    reset_shot_at_state,
    set_reindex_status,
)

router = APIRouter()


def _preview_counts(db: Session) -> dict:
    total_files = db.query(models.File.id).filter(models.File.deleted_at.is_(None)).count()
    missing_previews = (
        db.query(models.File.id)
        .outerjoin(models.Preview, models.Preview.file_id == models.File.id)
        .filter(models.File.deleted_at.is_(None), models.Preview.file_id.is_(None))
        .count()
    )
    total_previews = (
        db.query(models.Preview)
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


@router.post("/index/refresh-all")
def refresh_all(
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    run = models.IndexRun(status=models.IndexRunStatus.running)
    db.add(run)
    db.commit()
    scan_storage_task.delay(run.id)
    queue_missing_metadata_task.delay()
    set_reindex_status(
        {
            "status": "waiting_metadata",
            "count": 0,
            "updated_at": datetime.utcnow().isoformat(),
            "started_at": datetime.utcnow().isoformat(),
        }
    )
    reindex_after_metadata_task.delay(run.id)
    log_action(db, user_id=admin.id, action=models.AuditAction.rescan)
    db.commit()
    return {"status": "queued", "run_id": run.id}


@router.post("/index/reindex")
def reindex_only(
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    set_reindex_status(
        {
            "status": "queued",
            "count": 0,
            "updated_at": datetime.utcnow().isoformat(),
            "started_at": datetime.utcnow().isoformat(),
        }
    )
    reindex_search_task.delay()
    log_action(
        db,
        user_id=admin.id,
        action=models.AuditAction.reindex,
        meta={"action": "reindex_search"},
    )
    db.commit()
    return {"status": "queued"}


@router.get("/index/reindex/status")
def reindex_status(_: models.User = Depends(require_admin)) -> dict:
    status = get_reindex_status()
    if status:
        return status
    return {
        "status": "idle",
        "count": 0,
        "updated_at": datetime.utcnow().isoformat(),
    }


@router.post("/previews/refresh")
def refresh_previews(
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    counts = _preview_counts(db)
    payload = {
        "status": "running",
        "round": 1,
        "max_rounds": settings.preview_check_rounds,
        "total_files": counts["total_files"],
        "total_previews": counts["total_previews"],
        "missing_previews": counts["missing_previews"],
        "progress": counts["progress"],
        "updated_at": datetime.utcnow().isoformat(),
        "started_at": datetime.utcnow().isoformat(),
    }
    set_preview_status(payload)
    queue_missing_previews_task.delay()
    set_preview_exclusive(False)
    log_action(
        db,
        user_id=admin.id,
        action=models.AuditAction.reindex,
        meta={"action": "refresh_previews"},
    )
    db.commit()
    return {"status": "queued"}


@router.post("/previews/restart")
def restart_previews(
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    counts = _preview_counts(db)
    cancelled = cancel_preview_tasks()
    payload = {
        "status": "running",
        "round": 1,
        "max_rounds": settings.preview_check_rounds,
        "total_files": counts["total_files"],
        "total_previews": counts["total_previews"],
        "missing_previews": counts["missing_previews"],
        "progress": counts["progress"],
        "updated_at": datetime.utcnow().isoformat(),
        "started_at": datetime.utcnow().isoformat(),
    }
    set_preview_status(payload)
    queue_missing_previews_task.delay()
    log_action(
        db,
        user_id=admin.id,
        action=models.AuditAction.reindex,
        meta={"action": "restart_previews", **cancelled},
    )
    db.commit()
    return {"status": "queued", **cancelled}


@router.post("/metadata/shot-at/refresh")
def refresh_shot_at(
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    set_shot_at_status(
        {
            "status": "queued",
            "total": 0,
            "scanned": 0,
            "updated": 0,
            "updated_at": datetime.utcnow().isoformat(),
            "started_at": datetime.utcnow().isoformat(),
        }
    )
    refresh_shot_at_task.delay(False)
    log_action(
        db,
        user_id=admin.id,
        action=models.AuditAction.reindex,
        meta={"action": "refresh_shot_at"},
    )
    db.commit()
    return {"status": "queued"}


@router.post("/metadata/shot-at/reset")
def reset_shot_at_status(
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    reset_shot_at_state()
    set_shot_at_status(
        {
            "status": "idle",
            "total": 0,
            "scanned": 0,
            "updated": 0,
            "updated_at": datetime.utcnow().isoformat(),
        }
    )
    log_action(
        db,
        user_id=admin.id,
        action=models.AuditAction.reindex,
        meta={"action": "reset_shot_at_status"},
    )
    db.commit()
    return {"status": "idle"}


@router.get("/metadata/shot-at/status")
def shot_at_status(_: models.User = Depends(require_admin)) -> dict:
    status = get_shot_at_status()
    if status:
        return status
    return {
        "status": "idle",
        "total": 0,
        "scanned": 0,
        "updated": 0,
        "updated_at": datetime.utcnow().isoformat(),
    }


@router.get("/previews/status")
def previews_status(_: models.User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    status = get_preview_status()
    counts = _preview_counts(db)
    return {
        "status": (status or {}).get("status", "idle"),
        "round": (status or {}).get("round", 0),
        "max_rounds": (status or {}).get("max_rounds", settings.preview_check_rounds),
        "total_files": counts["total_files"],
        "total_previews": counts["total_previews"],
        "missing_previews": counts["missing_previews"],
        "progress": counts["progress"],
        "updated_at": datetime.utcnow().isoformat(),
        "started_at": (status or {}).get("started_at"),
    }


@router.post("/previews/orphans/cleanup")
def cleanup_orphans(
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    payload = {
        "status": "queued",
        "total_orphans": 0,
        "deleted": 0,
        "processed": 0,
        "updated_at": datetime.utcnow().isoformat(),
        "started_at": datetime.utcnow().isoformat(),
    }
    set_orphan_status(payload)
    cleanup_orphan_previews_task.delay()
    log_action(
        db,
        user_id=admin.id,
        action=models.AuditAction.reindex,
        meta={"action": "cleanup_orphan_previews"},
    )
    db.commit()
    return {"status": "queued"}


@router.get("/previews/orphans/status")
def orphan_status(_: models.User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    status = get_orphan_status()
    if status:
        return status
    return {
        "status": "idle",
        "total_orphans": 0,
        "deleted": 0,
        "processed": 0,
        "updated_at": datetime.utcnow().isoformat(),
    }


@router.get("/index/status")
def index_status(_: models.User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    files_count = db.execute(text("SELECT COUNT(*) FROM files")).scalar()
    last_run = (
        db.query(models.IndexRun).order_by(models.IndexRun.started_at.desc()).first()
    )
    run_payload = None
    if last_run:
        run_payload = {
            "id": last_run.id,
            "status": last_run.status.value,
            "scanned": last_run.scanned_count,
            "created": last_run.created_count,
            "updated": last_run.updated_count,
            "restored": last_run.restored_count,
            "deleted": last_run.deleted_count,
            "started_at": last_run.started_at,
            "finished_at": last_run.finished_at,
            "error": last_run.error,
        }
    return {"files": files_count, "run": run_payload}


@router.post("/index/cancel")
def cancel_index(_: models.User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    last_run = (
        db.query(models.IndexRun)
        .order_by(models.IndexRun.started_at.desc())
        .first()
    )
    if not last_run or last_run.status != models.IndexRunStatus.running:
        raise HTTPException(status_code=400, detail="No running index")
    cancel_index_run.delay(last_run.id)
    log_action(
        db,
        user_id=_.id,
        action=models.AuditAction.reindex,
        meta={"action": "cancel_index", "run_id": last_run.id},
    )
    db.commit()
    return {"status": "cancel_requested", "run_id": last_run.id}


@router.get("/users", response_model=list[UserOut])
def list_users(_: models.User = Depends(require_admin), db: Session = Depends(get_db)) -> list[UserOut]:
    users = db.query(models.User).order_by(models.User.created_at.desc()).all()
    return [
        UserOut(
            id=user.id,
            email=user.email,
            role=user.role.value,
            is_active=user.is_active,
            created_at=user.created_at,
        )
        for user in users
    ]


@router.post("/users", response_model=UserOut)
def create_user(
    payload: UserCreate,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserOut:
    if db.query(models.User).filter(models.User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already exists")
    try:
        role = models.Role(payload.role)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid role") from exc
    user = models.User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.flush()
    log_action(
        db,
        user_id=admin.id,
        action=models.AuditAction.user_manage,
        meta={"target_id": user.id, "action": "create"},
    )
    db.commit()
    return UserOut(
        id=user.id,
        email=user.email,
        role=user.role.value,
        is_active=user.is_active,
        created_at=user.created_at,
    )


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: str,
    payload: UserUpdate,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserOut:
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if payload.role:
        try:
            user.role = models.Role(payload.role)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid role") from exc
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.password:
        user.password_hash = hash_password(payload.password)
    log_action(
        db,
        user_id=admin.id,
        action=models.AuditAction.user_manage,
        meta={"target_id": user.id, "action": "update"},
    )
    db.commit()
    return UserOut(
        id=user.id,
        email=user.email,
        role=user.role.value,
        is_active=user.is_active,
        created_at=user.created_at,
    )


@router.delete("/users/{user_id}")
def delete_user(
    user_id: str,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    log_action(
        db,
        user_id=admin.id,
        action=models.AuditAction.user_manage,
        meta={"target_id": user.id, "action": "delete"},
    )
    db.commit()
    return {"status": "deleted"}


@router.get("/audit", response_model=list[AuditLogOut])
def audit_log(
    limit: int = 100,
    offset: int = 0,
    _: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[AuditLogOut]:
    rows = (
        db.query(models.AuditLog)
        .order_by(models.AuditLog.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [
        AuditLogOut(
            id=row.id,
            user_id=row.user_id,
            action=row.action.value,
            meta=row.meta or {},
            created_at=row.created_at,
        )
        for row in rows
    ]

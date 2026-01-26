from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import models
from app.audit import log_action
from app.db import get_db
from app.deps import require_admin
from app.schemas import AuditLogOut, UserCreate, UserOut, UserUpdate
from app.security import hash_password
from app.tasks import gc_previews_task, queue_missing_previews_task, reindex_search_task, scan_storage_task

router = APIRouter()


@router.post("/index/rescan")
def rescan(
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    scan_storage_task.delay()
    log_action(db, user_id=admin.id, action=models.AuditAction.rescan)
    db.commit()
    return {"status": "queued"}


@router.post("/index/reindex")
def reindex(
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    reindex_search_task.delay()
    log_action(db, user_id=admin.id, action=models.AuditAction.reindex)
    db.commit()
    return {"status": "queued"}


@router.post("/index/gc-previews")
def gc_previews(_: models.User = Depends(require_admin)) -> dict:
    gc_previews_task.delay()
    return {"status": "queued"}


@router.post("/index/rebuild-previews")
def rebuild_previews(_: models.User = Depends(require_admin)) -> dict:
    queue_missing_previews_task.delay()
    return {"status": "queued"}


@router.get("/index/status")
def index_status(_: models.User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    files_count = db.execute(text("SELECT COUNT(*) FROM files")).scalar()
    return {"files": files_count}


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

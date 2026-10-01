from datetime import datetime, timedelta
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app import tasks
from app.api.admin import _refresh_state_is_stale
from app.db import Base
from app.metadata_state import count_pending_metadata, missing_metadata_counts


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def make_file(
    file_id: str,
    *,
    mtime: datetime,
    metadata_checked_at: datetime | None,
    keyword_count: int = 1,
    title: str | None = "title",
    description: str | None = "description",
    shot_at: datetime | None = None,
    deleted_at: datetime | None = None,
) -> models.File:
    return models.File(
        id=file_id,
        storage_mode=models.StorageMode.filesystem,
        original_key=f"/photos/{file_id}.jpg",
        filename=f"{file_id}.jpg",
        ext="jpg",
        mime="image/jpeg",
        size_bytes=100,
        mtime=mtime,
        width=100,
        height=100,
        orientation=models.Orientation.square,
        shot_at=shot_at,
        title=title,
        description=description,
        keyword_count=keyword_count,
        metadata_checked_at=metadata_checked_at,
        created_at=mtime,
        updated_at=mtime,
        deleted_at=deleted_at,
    )


def test_metadata_counts_do_not_require_file_keywords_join():
    session = make_session()
    now = datetime(2026, 10, 1, 10, 0, 0)
    session.add_all(
        [
            make_file("complete", mtime=now, metadata_checked_at=now, shot_at=now),
            make_file(
                "missing",
                mtime=now,
                metadata_checked_at=now,
                keyword_count=0,
                title="",
                description=None,
            ),
            make_file(
                "deleted",
                mtime=now,
                metadata_checked_at=now,
                keyword_count=0,
                title="",
                description="",
                deleted_at=now,
            ),
        ]
    )
    session.commit()

    assert missing_metadata_counts(session) == {
        "missing_keywords": 1,
        "missing_text": 1,
        "missing_shot_at": 1,
    }


def test_pending_metadata_tracks_new_and_changed_files_only():
    session = make_session()
    now = datetime(2026, 10, 1, 10, 0, 0)
    session.add_all(
        [
            make_file("complete", mtime=now, metadata_checked_at=now),
            make_file("new", mtime=now, metadata_checked_at=None),
            make_file(
                "changed",
                mtime=now,
                metadata_checked_at=now - timedelta(minutes=1),
            ),
            make_file(
                "deleted",
                mtime=now,
                metadata_checked_at=None,
                deleted_at=now,
            ),
        ]
    )
    session.commit()

    assert count_pending_metadata(session) == 2


def test_refresh_state_becomes_idle_when_persisted_status_is_stale():
    now = datetime(2026, 10, 1, 10, 0, 0)
    state = {
        "status": "running",
        "updated_at": (now - timedelta(minutes=10)).isoformat(),
    }
    completed_run = SimpleNamespace(status=models.IndexRunStatus.completed)

    assert _refresh_state_is_stale(state, {"status": "idle"}, completed_run, now)
    assert not _refresh_state_is_stale(state, {"status": "running"}, completed_run, now)


def test_refresh_state_does_not_expire_an_active_scan():
    now = datetime(2026, 10, 1, 10, 0, 0)
    state = {
        "status": "running",
        "updated_at": (now - timedelta(hours=1)).isoformat(),
    }
    active_run = SimpleNamespace(status=models.IndexRunStatus.running)

    assert not _refresh_state_is_stale(state, {"status": "idle"}, active_run, now)


def test_celery_status_is_reused_for_status_poll_burst(monkeypatch):
    calls = []
    payload = {"status": "idle", "updated_at": "2026-10-01T10:00:00"}

    monkeypatch.setattr(tasks, "_celery_status_cache", None)
    monkeypatch.setattr(tasks, "_celery_status_cache_until", 0.0)
    monkeypatch.setattr(tasks.time, "monotonic", lambda: 100.0)
    monkeypatch.setattr(
        tasks,
        "_collect_celery_status",
        lambda queue_sample_size=1000: calls.append(queue_sample_size) or payload,
    )

    assert tasks.get_celery_status() == payload
    assert tasks.get_celery_status() == payload
    assert calls == [1000]


def test_celery_status_ttl_starts_after_collection(monkeypatch):
    calls = []
    clock = iter([10.0, 14.0, 14.1])

    monkeypatch.setattr(tasks, "_celery_status_cache", None)
    monkeypatch.setattr(tasks, "_celery_status_cache_until", 0.0)
    monkeypatch.setattr(tasks.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(
        tasks,
        "_collect_celery_status",
        lambda queue_sample_size=1000: calls.append(queue_sample_size) or {"status": "idle"},
    )

    first = tasks.get_celery_status()
    second = tasks.get_celery_status()

    assert first == second
    assert calls == [1000]


def test_celery_inspector_stops_after_all_expected_workers_reply(monkeypatch):
    calls = []
    marker = object()

    monkeypatch.setattr(tasks.settings, "celery_expected_workers", 8)
    monkeypatch.setattr(
        tasks.celery_app.control,
        "inspect",
        lambda **kwargs: calls.append(kwargs) or marker,
    )

    assert tasks._get_celery_inspector() is marker
    assert calls == [{"timeout": 1, "limit": 8}]


def test_parallel_stat_preserves_order_and_skips_unreadable_files(monkeypatch):
    def fake_stat(path):
        if path == "missing.jpg":
            raise FileNotFoundError(path)
        return path

    monkeypatch.setattr(tasks.os, "stat", fake_stat)
    paths = ["first.jpg", "missing.jpg", "last.jpg"]

    with tasks.ThreadPoolExecutor(max_workers=2) as executor:
        result = tasks._stat_paths(paths, executor)

    assert result == ["first.jpg", None, "last.jpg"]


def test_metadata_refresh_updates_keywords_in_one_consistent_set(monkeypatch):
    session = make_session()
    factory = sessionmaker(bind=session.get_bind())
    now = datetime(2026, 10, 1, 10, 0, 0)
    file_row = make_file("photo", mtime=now, metadata_checked_at=None)
    alpha = models.Keyword(id="alpha", value_norm="alpha", value_display="Alpha", usage_count=1)
    beta = models.Keyword(id="beta", value_norm="beta", value_display="Beta", usage_count=1)
    file_row.keywords = [alpha, beta]
    session.add(file_row)
    session.commit()
    session.close()

    monkeypatch.setattr(tasks, "SessionLocal", factory)
    monkeypatch.setattr(
        tasks,
        "extract_metadata",
        lambda _: {
            "mime": "image/jpeg",
            "width": 200,
            "height": 100,
            "shot_at": now,
            "title": "Updated title",
            "description": "Updated description",
            "keywords": ["gamma", "beta"],
        },
    )
    monkeypatch.setattr(tasks, "enqueue_upsert_search_doc", lambda _: True)
    monkeypatch.setattr(tasks, "clear_extract_metadata_enqueue", lambda _: None)

    result = tasks.extract_metadata_task.run("photo")

    check = factory()
    refreshed = check.query(models.File).filter(models.File.id == "photo").one()
    usage = {
        keyword.value_norm: keyword.usage_count
        for keyword in check.query(models.Keyword).all()
    }
    assert result == {"status": "ok", "added": 1, "removed": 1}
    assert sorted(keyword.value_norm for keyword in refreshed.keywords) == ["beta", "gamma"]
    assert refreshed.keyword_count == 2
    assert refreshed.metadata_checked_at is not None
    assert usage == {"alpha": 0, "beta": 1, "gamma": 1}
    check.close()

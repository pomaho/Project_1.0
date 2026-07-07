from app.tasks import clear_generate_preview_enqueue, enqueue_generate_preview


class FakeRedis:
    def __init__(self) -> None:
        self.store = {}
        self.expirations = {}

    def set(self, key: str, value: str, nx: bool = False, ex: int | None = None) -> bool:
        if nx and key in self.store:
            return False
        self.store[key] = value
        if ex is not None:
            self.expirations[key] = ex
        return True

    def delete(self, key: str) -> None:
        self.store.pop(key, None)


def test_preview_enqueue_deduplicates_by_file_id(monkeypatch):
    fake = FakeRedis()
    delayed = []

    monkeypatch.setattr("app.tasks.get_redis", lambda: fake)
    monkeypatch.setattr("app.tasks.generate_previews_task.delay", lambda file_id: delayed.append(file_id))

    assert enqueue_generate_preview("file-1") is True
    assert enqueue_generate_preview("file-1") is False
    assert delayed == ["file-1"]

    clear_generate_preview_enqueue("file-1")

    assert enqueue_generate_preview("file-1") is True
    assert delayed == ["file-1", "file-1"]

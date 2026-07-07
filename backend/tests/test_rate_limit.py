from app.rate_limit import check_download_limit, check_rate_limit, get_recent_request_metrics


class FakeRedis:
    def __init__(self) -> None:
        self.store = {}
        self.expirations = {}

    def incr(self, key: str) -> int:
        value = int(self.store.get(key, 0)) + 1
        self.store[key] = value
        return value

    def expire(self, key: str, ttl: int) -> None:
        self.expirations[key] = ttl

    def get(self, key: str) -> str | None:
        return self.store.get(key)


def test_rate_limit_allows_under_limit(monkeypatch):
    fake = FakeRedis()

    def fake_get():
        return fake

    monkeypatch.setattr("app.rate_limit.get_redis", fake_get)

    assert check_download_limit("user-1", 2) is True
    assert check_download_limit("user-1", 2) is True
    assert check_download_limit("user-1", 2) is False

    assert any(
        key.startswith("rate:download:user-1:") and ttl == 60
        for key, ttl in fake.expirations.items()
    )


def test_scoped_rate_limits_are_independent(monkeypatch):
    fake = FakeRedis()

    def fake_get():
        return fake

    monkeypatch.setattr("app.rate_limit.get_redis", fake_get)

    assert check_rate_limit("search", "1.2.3.4", 1) is True
    assert check_rate_limit("search", "1.2.3.4", 1) is False
    assert check_rate_limit("preview", "1.2.3.4", 1) is True


def test_zero_rate_limit_disables_limit(monkeypatch):
    fake = FakeRedis()

    def fake_get():
        return fake

    monkeypatch.setattr("app.rate_limit.get_redis", fake_get)

    assert check_rate_limit("search", "1.2.3.4", 0) is True
    assert fake.store == {}


def test_request_metrics_are_recorded(monkeypatch):
    fake = FakeRedis()

    def fake_get():
        return fake

    monkeypatch.setattr("app.rate_limit.get_redis", fake_get)
    monkeypatch.setattr("app.rate_limit.time.time", lambda: 120)

    assert check_rate_limit("preview", "1.2.3.4", 10) is True
    assert check_rate_limit("search", "1.2.3.4", 10) is True

    metrics = get_recent_request_metrics(2)

    assert metrics["totals"]["preview"] == 1
    assert metrics["totals"]["search"] == 1
    assert metrics["totals"]["total"] == 2

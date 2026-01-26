from app.rate_limit import check_download_limit


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


def test_rate_limit_allows_under_limit(monkeypatch):
    fake = FakeRedis()

    def fake_get():
        return fake

    monkeypatch.setattr("app.rate_limit.get_redis", fake_get)

    assert check_download_limit("user-1", 2) is True
    assert check_download_limit("user-1", 2) is True
    assert check_download_limit("user-1", 2) is False

    assert list(fake.expirations.values()) == [60]

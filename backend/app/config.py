from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


def parse_duration_to_seconds(value: str, default_seconds: int) -> int:
    if not value:
        return default_seconds
    raw = value.strip().lower()
    if raw.isdigit():
        return int(raw)
    if raw.endswith("s") and raw[:-1].isdigit():
        return int(raw[:-1])
    if raw.endswith("m") and raw[:-1].isdigit():
        return int(raw[:-1]) * 60
    if raw.endswith("h") and raw[:-1].isdigit():
        return int(raw[:-1]) * 3600
    if raw.endswith("d") and raw[:-1].isdigit():
        return int(raw[:-1]) * 86400
    return default_seconds


class Settings(BaseSettings):
    app_env: str = "dev"
    storage_mode: str = "filesystem"

    filesystem_root: str = "/data/originals"
    previews_root: str = "/data/previews"

    minio_endpoint: str = "http://minio:9000"
    minio_access_key: str = ""
    minio_secret_key: str = ""
    minio_bucket_originals: str = "originals"
    minio_bucket_previews: str = "previews"

    database_url: str
    redis_url: str = "redis://redis:6379/0"
    meili_url: str = "http://meili:7700"
    meili_key: str | None = None

    jwt_secret: str = "change-me"
    jwt_access_ttl: str = "15m"
    jwt_refresh_ttl: str = "30d"
    download_token_ttl: str = "90s"

    rate_limit_downloads_per_min: int = 20

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def jwt_access_ttl_seconds(self) -> int:
        return parse_duration_to_seconds(self.jwt_access_ttl, 900)

    @property
    def jwt_refresh_ttl_seconds(self) -> int:
        return parse_duration_to_seconds(self.jwt_refresh_ttl, 2592000)

    @property
    def download_token_ttl_seconds(self) -> int:
        return parse_duration_to_seconds(self.download_token_ttl, 90)


settings = Settings()

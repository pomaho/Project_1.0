from __future__ import annotations

import time

from fastapi import Request

from app.redis_client import get_redis

REQUEST_METRIC_SCOPES = ("search", "preview", "download", "download_ip")
REQUEST_METRIC_TTL_SECONDS = 600


def client_ip(request: Request) -> str:
    cf_connecting_ip = request.headers.get("cf-connecting-ip")
    if cf_connecting_ip:
        return cf_connecting_ip.strip()
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _window(window_seconds: int = 60) -> int:
    return int(time.time() // window_seconds)


def _record_request_metric(client, scope: str, window: int) -> None:
    if scope not in REQUEST_METRIC_SCOPES:
        return
    for key in (f"traffic:{scope}:{window}", f"traffic:total:{window}"):
        value = client.incr(key)
        if value == 1:
            client.expire(key, REQUEST_METRIC_TTL_SECONDS)


def check_rate_limit(scope: str, identifier: str, limit: int, window_seconds: int = 60) -> bool:
    if limit <= 0:
        return True
    try:
        client = get_redis()
        window = _window(window_seconds)
        _record_request_metric(client, scope, window)
        key = f"rate:{scope}:{identifier}:{window}"
        value = client.incr(key)
        if value == 1:
            client.expire(key, window_seconds)
        return value <= limit
    except Exception:
        return True


def check_download_limit(user_id: str, limit_per_min: int) -> bool:
    return check_rate_limit("download", user_id, limit_per_min)


def get_recent_request_metrics(minutes: int = 5) -> dict:
    client = get_redis()
    current_window = _window()
    windows = [current_window - offset for offset in range(max(1, minutes))]
    scopes = (*REQUEST_METRIC_SCOPES, "total")
    totals = {scope: 0 for scope in scopes}
    per_minute = []

    for window in reversed(windows):
        item = {"window": window}
        for scope in scopes:
            raw = client.get(f"traffic:{scope}:{window}")
            value = int(raw or 0)
            item[scope] = value
            totals[scope] += value
        per_minute.append(item)

    return {
        "minutes": len(windows),
        "totals": totals,
        "per_minute": per_minute,
    }

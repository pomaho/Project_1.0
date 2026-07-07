from __future__ import annotations

import time

from fastapi import Request

from app.redis_client import get_redis


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


def check_rate_limit(scope: str, identifier: str, limit: int, window_seconds: int = 60) -> bool:
    if limit <= 0:
        return True
    try:
        client = get_redis()
        window = int(time.time() // window_seconds)
        key = f"rate:{scope}:{identifier}:{window}"
        value = client.incr(key)
        if value == 1:
            client.expire(key, window_seconds)
        return value <= limit
    except Exception:
        return True


def check_download_limit(user_id: str, limit_per_min: int) -> bool:
    return check_rate_limit("download", user_id, limit_per_min)

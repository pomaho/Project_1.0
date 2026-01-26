from __future__ import annotations

import time

from app.redis_client import get_redis


def check_download_limit(user_id: str, limit_per_min: int) -> bool:
    if limit_per_min <= 0:
        return True
    try:
        client = get_redis()
        window = int(time.time() // 60)
        key = f"rate:download:{user_id}:{window}"
        value = client.incr(key)
        if value == 1:
            client.expire(key, 60)
        return value <= limit_per_min
    except Exception:
        return True

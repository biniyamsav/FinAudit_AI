import threading
import time

_rate_limit_lock = threading.Lock()
_rate_limit_buckets: dict[str, list[float]] = {}


def check_rate_limit(key: str, limit: int) -> int | None:
    now = time.time()
    window = 60.0
    with _rate_limit_lock:
        bucket = _rate_limit_buckets.setdefault(key, [])
        bucket[:] = [t for t in bucket if now - t < window]
        if len(bucket) >= limit:
            retry_after = int(window - (now - bucket[0])) + 1
            return max(1, retry_after)
        bucket.append(now)
        return None


def reset_rate_limits() -> None:
    with _rate_limit_lock:
        _rate_limit_buckets.clear()
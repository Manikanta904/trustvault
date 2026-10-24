import time
from collections import defaultdict
from threading import Lock

from fastapi import HTTPException, Request, status


class SlidingWindowRateLimiter:
    """
    Thread-safe in-memory sliding window rate limiter.
    Tracks timestamps of requests per key (e.g. IP address or User ID).
    """

    def __init__(self, max_requests: int, window_seconds: int, name: str = "rate_limiter"):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.name = name
        self._history: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def check(self, key: str) -> None:
        """
        Check if the request exceeds the rate limit.
        If exceeded, raises HTTP 429 Too Many Requests.
        """
        now = time.time()
        window_start = now - self.window_seconds

        with self._lock:
            timestamps = self._history[key]
            # Prune timestamps outside the current sliding window
            valid_timestamps = [t for t in timestamps if t > window_start]
            self._history[key] = valid_timestamps

            if len(valid_timestamps) >= self.max_requests:
                retry_after = int(self.window_seconds - (now - valid_timestamps[0])) + 1
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Please try again later.",
                    headers={"Retry-After": str(max(1, retry_after))},
                )

            self._history[key].append(now)

    def reset(self, key: str | None = None) -> None:
        """Reset history for a key or all keys (useful in tests)."""
        with self._lock:
            if key:
                self._history.pop(key, None)
            else:
                self._history.clear()


def get_client_ip(request: Request) -> str:
    """
    Extract the client's IP address safely.
    Inspects request.client.host. Arbitrary X-Forwarded-For headers from untrusted clients
    are not trusted unless running behind an explicitly verified proxy.
    """
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"


# Pre-configured rate limiters for critical application surfaces:
# 1. Login: 10 attempts per 60 seconds per IP
login_rate_limiter = SlidingWindowRateLimiter(
    max_requests=10, window_seconds=60, name="login_limiter"
)

# 2. Registration: 5 attempts per 60 seconds per IP
register_rate_limiter = SlidingWindowRateLimiter(
    max_requests=5, window_seconds=60, name="register_limiter"
)

# 3. User search: 30 queries per 60 seconds per user/IP
user_search_rate_limiter = SlidingWindowRateLimiter(
    max_requests=30, window_seconds=60, name="user_search_limiter"
)

# 4. Sensitive document operations (bulk share/revoke, uploads): 30 per 60 seconds per user
document_sensitive_limiter = SlidingWindowRateLimiter(
    max_requests=30, window_seconds=60, name="document_sensitive_limiter"
)

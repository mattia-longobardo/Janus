import time
from collections.abc import Callable
from typing import Any, Protocol


class Debouncer(Protocol):
    def first(self, key: str, ttl_s: int) -> bool: ...


class MemoryDebouncer:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._expires: dict[str, float] = {}

    def first(self, key: str, ttl_s: int) -> bool:
        now = self._clock()
        if self._expires.get(key, 0.0) > now:
            return False
        self._expires[key] = now + ttl_s
        return True


class RedisDebouncer:
    def __init__(self, client: Any) -> None:
        self._client = client

    def first(self, key: str, ttl_s: int) -> bool:
        return bool(self._client.set(f"janus:notify:{key}", "1", nx=True, ex=ttl_s))

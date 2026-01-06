from __future__ import annotations

import threading
from typing import Callable, Iterator


class StreamLimiter:
    def __init__(self, max_streams: int) -> None:
        self.max_streams = max_streams
        self._active = 0
        self._lock = threading.Lock()

    @property
    def active(self) -> int:
        return self._active

    def try_acquire(self) -> bool:
        if self.max_streams <= 0:
            return True
        with self._lock:
            if self._active >= self.max_streams:
                return False
            self._active += 1
            return True

    def release(self) -> None:
        if self.max_streams <= 0:
            return
        with self._lock:
            self._active = max(0, self._active - 1)


class ReleasingIterator:
    def __init__(self, source: Iterator[bytes], release: Callable[[], None]) -> None:
        self._source = source
        self._release = release
        self._released = False
        self._lock = threading.Lock()

    def __iter__(self) -> "ReleasingIterator":
        return self

    def __next__(self) -> bytes:
        try:
            return next(self._source)
        except BaseException:
            self.close()
            raise

    def close(self) -> None:
        close_source = getattr(self._source, "close", None)
        if close_source:
            close_source()
        with self._lock:
            if self._released:
                return
            self._released = True
        self._release()

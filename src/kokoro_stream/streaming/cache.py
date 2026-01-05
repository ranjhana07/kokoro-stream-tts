from __future__ import annotations

import threading
from collections import OrderedDict
from typing import Hashable

import numpy as np


class ChunkCache:
    def __init__(self, max_bytes: int) -> None:
        self.max_bytes = max_bytes
        self.hits = 0
        self.misses = 0
        self._entries: OrderedDict[Hashable, np.ndarray] = OrderedDict()
        self._size = 0
        self._lock = threading.Lock()

    @property
    def size_bytes(self) -> int:
        return self._size

    def __len__(self) -> int:
        return len(self._entries)

    def get(self, key: Hashable) -> np.ndarray | None:
        with self._lock:
            audio = self._entries.get(key)
            if audio is None:
                self.misses += 1
                return None
            self._entries.move_to_end(key)
            self.hits += 1
            return audio

    def put(self, key: Hashable, audio: np.ndarray) -> None:
        if audio.nbytes > self.max_bytes:
            return
        stored = audio.copy()
        stored.setflags(write=False)
        with self._lock:
            previous = self._entries.pop(key, None)
            if previous is not None:
                self._size -= previous.nbytes
            self._entries[key] = stored
            self._size += stored.nbytes
            while self._size > self.max_bytes and self._entries:
                _, evicted = self._entries.popitem(last=False)
                self._size -= evicted.nbytes

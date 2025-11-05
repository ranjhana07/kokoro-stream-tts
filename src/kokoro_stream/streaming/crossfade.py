from __future__ import annotations

import numpy as np


def equal_power_curves(length: int) -> tuple[np.ndarray, np.ndarray]:
    position = (np.arange(length, dtype=np.float32) + 0.5) / length
    angle = position * (np.pi / 2.0)
    return np.cos(angle), np.sin(angle)


class Crossfader:
    def __init__(self, sample_rate: int, crossfade_ms: int = 60) -> None:
        self.fade_length = int(sample_rate * crossfade_ms / 1000)
        self._tail: np.ndarray | None = None
        if self.fade_length > 0:
            self._fade_out, self._fade_in = equal_power_curves(self.fade_length)

    def push(self, chunk: np.ndarray) -> np.ndarray:
        if chunk.size == 0:
            return chunk
        if self.fade_length == 0:
            return chunk
        if self._tail is None:
            return self._hold(chunk)
        if self._tail.size < self.fade_length or chunk.size < self.fade_length:
            joined = np.concatenate([self._tail, chunk])
            self._tail = None
            return joined
        blended = self._tail * self._fade_out + chunk[: self.fade_length] * self._fade_in
        body = np.concatenate([blended, chunk[self.fade_length :]])
        return self._hold(body, skip_head=False)

    def _hold(self, audio: np.ndarray, skip_head: bool = False) -> np.ndarray:
        if audio.size <= self.fade_length:
            self._tail = audio
            return audio[:0]
        self._tail = audio[-self.fade_length :]
        return audio[: -self.fade_length]

    def flush(self) -> np.ndarray:
        tail = self._tail
        self._tail = None
        if tail is None:
            return np.zeros(0, dtype=np.float32)
        return tail

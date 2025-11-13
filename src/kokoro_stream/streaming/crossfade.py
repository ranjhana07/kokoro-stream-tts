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
        self._curves: dict[int, tuple[np.ndarray, np.ndarray]] = {}

    def curves_for(self, length: int) -> tuple[np.ndarray, np.ndarray]:
        if length not in self._curves:
            self._curves[length] = equal_power_curves(length)
        return self._curves[length]

    def push(self, chunk: np.ndarray) -> np.ndarray:
        if chunk.size == 0 or self.fade_length == 0:
            return chunk
        if self._tail is None:
            return self._hold(chunk)
        overlap = min(self._tail.size, chunk.size)
        fade_out, fade_in = self.curves_for(overlap)
        blended = self._tail[self._tail.size - overlap :] * fade_out + chunk[:overlap] * fade_in
        combined = np.concatenate(
            [self._tail[: self._tail.size - overlap], blended, chunk[overlap:]]
        )
        return self._hold(combined)

    def _hold(self, audio: np.ndarray) -> np.ndarray:
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

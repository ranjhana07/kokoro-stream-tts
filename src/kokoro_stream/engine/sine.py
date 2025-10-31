from __future__ import annotations

import time
import zlib

import numpy as np

from kokoro_stream.engine.base import EngineError

SECONDS_PER_CHAR = 0.06
EDGE_FADE_SECONDS = 0.004
AMPLITUDE = 0.3


class SineEngine:
    def __init__(self, sample_rate: int = 24000, latency_per_char: float = 0.0, voices: tuple[str, ...] = ("sine_low", "sine_mid", "sine_high")) -> None:
        self.sample_rate = sample_rate
        self.latency_per_char = latency_per_char
        self._voices = list(voices)

    def voices(self) -> list[str]:
        return list(self._voices)

    def synthesize(self, text: str, voice: str, speed: float = 1.0) -> np.ndarray:
        if voice not in self._voices:
            raise EngineError(f"unknown voice: {voice}")
        if speed <= 0:
            raise EngineError("speed must be positive")
        if self.latency_per_char:
            time.sleep(self.latency_per_char * len(text))
        base_frequency = 180.0 + 90.0 * self._voices.index(voice)
        pieces = [self._word_tone(word, base_frequency, speed) for word in text.split()]
        if not pieces:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(pieces).astype(np.float32)

    def _word_tone(self, word: str, base_frequency: float, speed: float) -> np.ndarray:
        duration = (len(word) + 1) * SECONDS_PER_CHAR / speed
        sample_count = max(1, int(duration * self.sample_rate))
        offset = (zlib.crc32(word.encode("utf-8")) % 9) * 22.0
        timeline = np.arange(sample_count) / self.sample_rate
        tone = AMPLITUDE * np.sin(2.0 * np.pi * (base_frequency + offset) * timeline)
        fade_count = min(sample_count // 2, int(EDGE_FADE_SECONDS * self.sample_rate))
        if fade_count > 0:
            ramp = np.linspace(0.0, 1.0, fade_count)
            tone[:fade_count] *= ramp
            tone[-fade_count:] *= ramp[::-1]
        return tone

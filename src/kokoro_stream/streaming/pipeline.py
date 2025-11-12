from __future__ import annotations

import time
from typing import Callable, Iterator

import numpy as np

from kokoro_stream.config import Settings
from kokoro_stream.engine.base import SpeechEngine
from kokoro_stream.streaming.crossfade import Crossfader
from kokoro_stream.streaming.frames import encode_audio, encode_end, encode_error
from kokoro_stream.streaming.prefetch import PrefetchPool, StreamPrefetcher
from kokoro_stream.text.chunker import Chunk, ChunkBudget, plan_chunks
from kokoro_stream.text.ssml import parse_ssml

ChunkObserver = Callable[[float], None]


class StreamingSynthesizer:
    def __init__(
        self,
        engine: SpeechEngine,
        pool: PrefetchPool,
        settings: Settings,
        chunk_observer: ChunkObserver | None = None,
    ) -> None:
        self.engine = engine
        self.pool = pool
        self.settings = settings
        self._chunk_observer = chunk_observer
        self._budget = ChunkBudget(
            first_chars=settings.first_chunk_chars, max_chars=settings.max_chunk_chars
        )

    def prepare(self, text: str) -> list[Chunk]:
        return plan_chunks(parse_ssml(text), self._budget)

    def synthesize_chunk(self, chunk: Chunk, voice: str, speed: float) -> np.ndarray:
        started = time.perf_counter()
        if chunk.text:
            audio = self.engine.synthesize(chunk.text, voice, speed * chunk.speed)
        else:
            audio = np.zeros(0, dtype=np.float32)
        if chunk.pause_ms:
            silence = np.zeros(int(self.engine.sample_rate * chunk.pause_ms / 1000), dtype=np.float32)
            audio = np.concatenate([audio, silence])
        if self._chunk_observer:
            self._chunk_observer(time.perf_counter() - started)
        return audio

    def render(self, chunks: list[Chunk], voice: str, speed: float = 1.0) -> Iterator[np.ndarray]:
        crossfader = Crossfader(self.engine.sample_rate, self.settings.crossfade_ms)
        prefetcher = StreamPrefetcher(
            self.pool,
            chunks,
            lambda chunk: self.synthesize_chunk(chunk, voice, speed),
            depth=self.settings.prefetch_depth,
        )
        try:
            for audio in prefetcher:
                blended = crossfader.push(audio)
                if blended.size:
                    yield blended
            remainder = crossfader.flush()
            if remainder.size:
                yield remainder
        finally:
            prefetcher.close()

    def frames(self, chunks: list[Chunk], voice: str, speed: float = 1.0) -> Iterator[bytes]:
        sequence = 0
        sample_rate = self.engine.sample_rate
        try:
            for audio in self.render(chunks, voice, speed):
                yield encode_audio(sequence, audio, sample_rate)
                sequence += 1
            yield encode_end(sequence, sample_rate)
        except Exception as error:
            yield encode_error(sequence, f"{type(error).__name__}: {error}", sample_rate)

    def synthesize(self, chunks: list[Chunk], voice: str, speed: float = 1.0) -> np.ndarray:
        pieces = list(self.render(chunks, voice, speed))
        if not pieces:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(pieces)

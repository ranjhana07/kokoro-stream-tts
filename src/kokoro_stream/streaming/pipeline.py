from __future__ import annotations

import time
from typing import Callable, Iterator

import numpy as np

from kokoro_stream.config import Settings
from kokoro_stream.engine.base import SpeechEngine
from kokoro_stream.streaming.audio import resample, trim_silence
from kokoro_stream.streaming.cache import ChunkCache
from kokoro_stream.streaming.crossfade import Crossfader
from kokoro_stream.streaming.frames import encode_audio, encode_end, encode_error, float_to_pcm16
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
        cache: ChunkCache | None = None,
    ) -> None:
        self.engine = engine
        self.pool = pool
        self.settings = settings
        self._chunk_observer = chunk_observer
        self._cache = cache
        self._budget = ChunkBudget(
            first_chars=settings.first_chunk_chars, max_chars=settings.max_chunk_chars
        )

    def prepare(self, text: str) -> list[Chunk]:
        return plan_chunks(parse_ssml(text), self._budget)

    def speech_audio(self, text: str, voice: str, speed: float, output_rate: int) -> np.ndarray:
        key = (voice, round(speed, 3), text, output_rate, self.settings.trim_silence)
        if self._cache is not None:
            cached = self._cache.get(key)
            if cached is not None:
                return cached
        audio = self.engine.synthesize(text, voice, speed)
        if self.settings.trim_silence:
            audio = trim_silence(audio, self.engine.sample_rate)
        if audio.size and output_rate != self.engine.sample_rate:
            audio = resample(audio, self.engine.sample_rate, output_rate)
        if self._cache is not None:
            self._cache.put(key, audio)
        return audio

    def synthesize_chunk(
        self, chunk: Chunk, voice: str, speed: float, output_rate: int | None = None
    ) -> np.ndarray:
        output_rate = output_rate or self.engine.sample_rate
        started = time.perf_counter()
        if chunk.text:
            audio = self.speech_audio(chunk.text, voice, speed * chunk.speed, output_rate)
        else:
            audio = np.zeros(0, dtype=np.float32)
        if chunk.pause_ms:
            silence = np.zeros(int(output_rate * chunk.pause_ms / 1000), dtype=np.float32)
            audio = np.concatenate([audio, silence])
        if self._chunk_observer:
            self._chunk_observer(time.perf_counter() - started)
        return audio

    def render(
        self, chunks: list[Chunk], voice: str, speed: float = 1.0, sample_rate: int | None = None
    ) -> Iterator[np.ndarray]:
        output_rate = sample_rate or self.engine.sample_rate
        crossfader = Crossfader(output_rate, self.settings.crossfade_ms)
        prefetcher = StreamPrefetcher(
            self.pool,
            chunks,
            lambda chunk: self.synthesize_chunk(chunk, voice, speed, output_rate),
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

    def frames(
        self, chunks: list[Chunk], voice: str, speed: float = 1.0, sample_rate: int | None = None
    ) -> Iterator[bytes]:
        sequence = 0
        sample_rate = sample_rate or self.engine.sample_rate
        try:
            for audio in self.render(chunks, voice, speed, sample_rate):
                yield encode_audio(sequence, audio, sample_rate)
                sequence += 1
            yield encode_end(sequence, sample_rate)
        except Exception as error:
            yield encode_error(sequence, f"{type(error).__name__}: {error}", sample_rate)

    def pcm_stream(
        self,
        chunks: list[Chunk],
        voice: str,
        speed: float = 1.0,
        sample_rate: int | None = None,
        header: bytes = b"",
    ) -> Iterator[bytes]:
        if header:
            yield header
        for audio in self.render(chunks, voice, speed, sample_rate):
            yield float_to_pcm16(audio).tobytes()

    def synthesize(
        self, chunks: list[Chunk], voice: str, speed: float = 1.0, sample_rate: int | None = None
    ) -> np.ndarray:
        pieces = list(self.render(chunks, voice, speed, sample_rate))
        if not pieces:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(pieces)

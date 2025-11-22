from __future__ import annotations

from kokoro_stream.config import Settings
from kokoro_stream.engine.base import EngineError, SpeechEngine
from kokoro_stream.engine.sine import SineEngine


def build_engine(settings: Settings) -> SpeechEngine:
    name = settings.engine.lower()
    if name == "sine":
        return SineEngine(sample_rate=settings.sample_rate)
    if name == "kokoro":
        from kokoro_stream.engine.kokoro import KokoroEngine

        return KokoroEngine(
            model_path=settings.model_path,
            voices_path=settings.voices_path,
            vocab_path=settings.vocab_path,
            providers=settings.providers,
            intra_op_threads=settings.intra_op_threads,
        )
    raise EngineError(f"unknown engine: {settings.engine}")

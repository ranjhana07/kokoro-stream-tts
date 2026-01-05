import numpy as np
import pytest

from kokoro_stream.engine.base import EngineError
from kokoro_stream.streaming.frames import FrameType, decode_all
from kokoro_stream.streaming.pipeline import StreamingSynthesizer

TEXT = (
    "Streaming speech needs a short first chunk. The rest can be larger and arrives later. "
    "Each sentence is synthesized while the previous one is being sent. "
    "That keeps the pipeline full for the whole response."
)


def test_prepare_produces_short_first_chunk(synthesizer):
    chunks = synthesizer.prepare(TEXT)
    assert len(chunks) >= 3
    assert len(chunks[0].text) <= 40


def test_synthesize_length_accounts_for_crossfades(synthesizer, engine, settings):
    chunks = synthesizer.prepare(TEXT)
    pieces = [engine.synthesize(chunk.text, "sine_mid") for chunk in chunks]
    fade = int(settings.sample_rate * settings.crossfade_ms / 1000)
    expected = sum(len(piece) for piece in pieces) - fade * (len(pieces) - 1)
    audio = synthesizer.synthesize(chunks, "sine_mid")
    assert len(audio) == expected


def test_frames_end_with_end_frame_and_sequences_are_contiguous(synthesizer):
    chunks = synthesizer.prepare(TEXT)
    frames = decode_all(b"".join(synthesizer.frames(chunks, "sine_mid")))
    assert frames[-1].frame_type is FrameType.END
    audio_frames = frames[:-1]
    assert all(frame.frame_type is FrameType.AUDIO for frame in audio_frames)
    assert [frame.sequence for frame in audio_frames] == list(range(len(audio_frames)))
    assert frames[-1].sequence == len(audio_frames)


def test_frames_match_synthesize_output(synthesizer):
    chunks = synthesizer.prepare(TEXT)
    streamed = np.concatenate(
        [frame.samples() for frame in decode_all(b"".join(synthesizer.frames(chunks, "sine_mid")))[:-1]]
    )
    direct = synthesizer.synthesize(chunks, "sine_mid")
    assert len(streamed) == len(direct)
    assert np.max(np.abs(streamed / 32767.0 - direct)) < 1e-3


def test_pause_adds_silence(synthesizer, settings):
    plain = synthesizer.synthesize(synthesizer.prepare("<speak>One. Two.</speak>"), "sine_mid")
    paused = synthesizer.synthesize(
        synthesizer.prepare('<speak>One.<break time="500ms"/>Two.</speak>'), "sine_mid"
    )
    extra = len(paused) - len(plain)
    assert extra == pytest.approx(settings.sample_rate * 0.5, abs=settings.sample_rate * 0.07)


def test_empty_plan_yields_only_end_frame(synthesizer):
    frames = decode_all(b"".join(synthesizer.frames([], "sine_mid")))
    assert [frame.frame_type for frame in frames] == [FrameType.END]


def test_engine_failure_becomes_error_frame(synthesizer):
    chunks = synthesizer.prepare(TEXT)
    frames = decode_all(b"".join(synthesizer.frames(chunks, "missing_voice")))
    assert frames[-1].frame_type is FrameType.ERROR
    assert "EngineError" in frames[-1].message()


def test_engine_failure_raises_from_synthesize(synthesizer):
    with pytest.raises(EngineError):
        synthesizer.synthesize(synthesizer.prepare(TEXT), "missing_voice")


def test_chunk_observer_sees_every_chunk(engine, pool, settings):
    seen = []
    synthesizer = StreamingSynthesizer(engine, pool, settings, chunk_observer=seen.append)
    chunks = synthesizer.prepare(TEXT)
    synthesizer.synthesize(chunks, "sine_mid")
    assert len(seen) == len(chunks)
    assert all(duration >= 0 for duration in seen)


def test_speed_changes_duration(synthesizer):
    chunks = synthesizer.prepare(TEXT)
    normal = synthesizer.synthesize(chunks, "sine_mid", speed=1.0)
    fast = synthesizer.synthesize(chunks, "sine_mid", speed=1.5)
    assert len(fast) < len(normal) * 0.8


class PaddedEngine:
    sample_rate = 24000

    def voices(self):
        return ["v"]

    def synthesize(self, text, voice, speed=1.0):
        body = np.full(12000, 0.3, dtype=np.float32)
        silence = np.zeros(6000, dtype=np.float32)
        return np.concatenate([silence, body, silence])


def test_silence_trimming_shortens_chunks(pool, settings):
    from dataclasses import replace

    trimmed = StreamingSynthesizer(PaddedEngine(), pool, replace(settings, trim_silence=True))
    untrimmed = StreamingSynthesizer(PaddedEngine(), pool, replace(settings, trim_silence=False))
    chunks = trimmed.prepare("One sentence here. Another sentence there.")
    short = len(trimmed.synthesize(chunks, "v"))
    long = len(untrimmed.synthesize(chunks, "v"))
    assert long - short >= 2 * 2 * (6000 - int(24000 * 0.012)) - 10


class CountingEngine:
    sample_rate = 24000

    def __init__(self):
        self.calls = 0

    def voices(self):
        return ["v"]

    def synthesize(self, text, voice, speed=1.0):
        self.calls += 1
        return np.full(6000, 0.2, dtype=np.float32)


def test_cache_skips_repeated_chunks(pool, settings):
    from kokoro_stream.streaming.cache import ChunkCache

    engine = CountingEngine()
    cache = ChunkCache(max_bytes=1_000_000)
    synthesizer = StreamingSynthesizer(engine, pool, settings, cache=cache)
    chunks = synthesizer.prepare("The same sentence again. And a second sentence.")
    first = synthesizer.synthesize(chunks, "v")
    calls_after_first = engine.calls
    second = synthesizer.synthesize(chunks, "v")
    assert engine.calls == calls_after_first
    assert np.array_equal(first, second)
    assert cache.hits == len(chunks)


def test_cache_key_includes_voice_and_speed(pool, settings):
    from kokoro_stream.streaming.cache import ChunkCache

    engine = CountingEngine()
    synthesizer = StreamingSynthesizer(engine, pool, settings, cache=ChunkCache(1_000_000))
    chunks = synthesizer.prepare("Only one sentence here.")
    synthesizer.synthesize(chunks, "v", speed=1.0)
    synthesizer.synthesize(chunks, "v", speed=1.2)
    assert engine.calls == 2

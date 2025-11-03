import numpy as np
import pytest

from kokoro_stream.engine.base import EngineError, SpeechEngine
from kokoro_stream.engine.sine import SineEngine


def test_engine_satisfies_protocol():
    assert isinstance(SineEngine(), SpeechEngine)


def test_output_is_deterministic():
    engine = SineEngine()
    first = engine.synthesize("hello world", "sine_mid")
    second = engine.synthesize("hello world", "sine_mid")
    assert np.array_equal(first, second)


def test_output_dtype_and_range():
    audio = SineEngine().synthesize("some words here", "sine_low")
    assert audio.dtype == np.float32
    assert np.max(np.abs(audio)) <= 1.0


def test_duration_scales_with_text_and_speed():
    engine = SineEngine(sample_rate=16000)
    short = engine.synthesize("hi", "sine_mid")
    long = engine.synthesize("hi there everyone", "sine_mid")
    fast = engine.synthesize("hi there everyone", "sine_mid", speed=2.0)
    assert len(long) > len(short)
    assert len(fast) == pytest.approx(len(long) / 2, rel=0.05)


def test_voices_differ():
    engine = SineEngine()
    assert not np.array_equal(
        engine.synthesize("same text", "sine_low"), engine.synthesize("same text", "sine_high")
    )


def test_empty_text_gives_empty_audio():
    assert SineEngine().synthesize("   ", "sine_mid").size == 0


def test_unknown_voice_raises():
    with pytest.raises(EngineError):
        SineEngine().synthesize("hi", "nope")


def test_bad_speed_raises():
    with pytest.raises(EngineError):
        SineEngine().synthesize("hi", "sine_mid", speed=0)

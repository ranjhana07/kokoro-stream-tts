import numpy as np
import pytest

from kokoro_stream.streaming.audio import trim_silence

RATE = 24000


def tone(length):
    return (0.3 * np.sin(2 * np.pi * 220 * np.arange(length) / RATE)).astype(np.float32)


def test_trims_leading_and_trailing_silence_but_keeps_margin():
    body = tone(4800)
    padded = np.concatenate([np.zeros(6000, dtype=np.float32), body, np.zeros(9000, dtype=np.float32)])
    trimmed = trim_silence(padded, RATE, keep_ms=10)
    margin = int(RATE * 0.01)
    assert len(trimmed) <= len(body) + 2 * margin + 1
    assert len(trimmed) >= len(body)
    assert np.max(np.abs(trimmed)) == pytest.approx(np.max(np.abs(body)))


def test_audio_without_silence_is_unchanged():
    body = tone(3000) + 0.1
    assert np.array_equal(trim_silence(body, RATE), body)


def test_all_silence_becomes_empty():
    assert trim_silence(np.zeros(5000, dtype=np.float32), RATE).size == 0


def test_empty_input():
    assert trim_silence(np.zeros(0, dtype=np.float32), RATE).size == 0


def test_quiet_noise_below_threshold_is_removed():
    noise = (np.random.default_rng(1).standard_normal(8000) * 1e-4).astype(np.float32)
    padded = np.concatenate([noise, tone(2400), noise])
    trimmed = trim_silence(padded, RATE, threshold_db=-50.0, keep_ms=5)
    assert len(trimmed) < 2400 + 2 * int(RATE * 0.005) + 400

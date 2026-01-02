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


from kokoro_stream.streaming.audio import resample


def sine(frequency, rate, seconds=0.5):
    return np.sin(2 * np.pi * frequency * np.arange(int(rate * seconds)) / rate).astype(np.float32)


def test_resample_length_scales_with_rate():
    assert len(resample(sine(440, 24000), 24000, 16000)) == 8000
    assert len(resample(sine(440, 16000), 16000, 24000)) == 12000


def test_resample_same_rate_is_identity():
    original = sine(440, 24000)
    assert resample(original, 24000, 24000) is original


def test_resample_preserves_tone_frequency():
    resampled = resample(sine(500, 24000), 24000, 16000)
    spectrum = np.abs(np.fft.rfft(resampled))
    peak_hz = np.argmax(spectrum) * 16000 / len(resampled)
    assert peak_hz == pytest.approx(500, abs=5)


def test_downsampling_removes_content_above_new_nyquist():
    high = sine(9000, 24000)
    resampled = resample(high, 24000, 8000)
    assert np.sqrt(np.mean(resampled[200:-200] ** 2)) < 0.05 * np.sqrt(np.mean(high**2))


def test_resample_empty():
    assert resample(np.zeros(0, dtype=np.float32), 24000, 16000).size == 0

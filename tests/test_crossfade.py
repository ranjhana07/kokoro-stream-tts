import numpy as np
import pytest

from kokoro_stream.streaming.crossfade import Crossfader, equal_power_curves

SAMPLE_RATE = 24000
FADE = int(SAMPLE_RATE * 0.06)


def run(chunks, crossfade_ms=60):
    crossfader = Crossfader(SAMPLE_RATE, crossfade_ms)
    pieces = [crossfader.push(chunk) for chunk in chunks]
    pieces.append(crossfader.flush())
    return np.concatenate(pieces)


def tone(length, frequency=220.0, phase=0.0):
    timeline = np.arange(length) / SAMPLE_RATE
    return (0.4 * np.sin(2 * np.pi * frequency * timeline + phase)).astype(np.float32)


def test_fade_length_matches_milliseconds():
    assert Crossfader(SAMPLE_RATE, 60).fade_length == 1440


def test_curves_are_equal_power():
    fade_out, fade_in = equal_power_curves(500)
    assert np.allclose(fade_out**2 + fade_in**2, 1.0, atol=1e-5)
    assert fade_out[0] > 0.99 and fade_in[0] < 0.01
    assert fade_out[-1] < 0.01 and fade_in[-1] > 0.99


def test_output_length_is_sum_minus_overlaps():
    chunks = [tone(8000), tone(9000), tone(12000), tone(5000)]
    output = run(chunks)
    assert len(output) == sum(len(chunk) for chunk in chunks) - 3 * FADE


def test_single_chunk_passes_through_unchanged():
    chunk = tone(5000)
    assert np.array_equal(run([chunk]), chunk)


def test_zero_crossfade_is_plain_concatenation():
    chunks = [tone(3000), tone(4000)]
    assert np.array_equal(run(chunks, crossfade_ms=0), np.concatenate(chunks))


def test_first_chunk_head_and_last_chunk_tail_are_untouched():
    first, last = tone(6000), tone(6000, frequency=330.0)
    output = run([first, last])
    assert np.array_equal(output[: 6000 - FADE], first[: 6000 - FADE])
    assert np.array_equal(output[-(6000 - FADE) :], last[FADE:])


def test_step_between_chunks_is_smoothed():
    low = np.full(6000, -0.5, dtype=np.float32)
    high = np.full(6000, 0.5, dtype=np.float32)
    hard_step = np.max(np.abs(np.diff(np.concatenate([low, high]))))
    smoothed_step = np.max(np.abs(np.diff(run([low, high]))))
    assert hard_step == pytest.approx(1.0)
    assert smoothed_step < hard_step / 100


def test_midpoint_of_fade_has_equal_weights():
    first = np.full(6000, 1.0, dtype=np.float32)
    second = np.zeros(6000, dtype=np.float32)
    output = run([first, second])
    midpoint = output[6000 - FADE + FADE // 2]
    assert midpoint == pytest.approx(np.cos(np.pi / 4), abs=1e-2)


def test_continuity_across_random_phase_tones():
    rng = np.random.default_rng(7)
    chunks = [tone(7000, 200.0 + 40 * index, phase=rng.uniform(0, 6.28)) for index in range(5)]
    output = run(chunks)
    assert np.max(np.abs(np.diff(output))) < 0.12
    assert np.all(np.isfinite(output))


def test_empty_chunks_are_ignored():
    chunks = [tone(5000), np.zeros(0, dtype=np.float32), tone(5000)]
    assert len(run(chunks)) == 10000 - FADE


def test_flush_without_input_is_empty():
    assert Crossfader(SAMPLE_RATE).flush().size == 0

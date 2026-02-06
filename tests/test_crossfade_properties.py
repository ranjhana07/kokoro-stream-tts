import numpy as np
import pytest

from kokoro_stream.streaming.crossfade import Crossfader

RATE = 24000
FADE = int(RATE * 0.06)


def run(chunks, crossfade_ms=60):
    crossfader = Crossfader(RATE, crossfade_ms)
    pieces = [crossfader.push(chunk) for chunk in chunks]
    pieces.append(crossfader.flush())
    return np.concatenate(pieces)


@pytest.mark.parametrize("seed", range(30))
def test_random_chunk_lengths_keep_bounds(seed):
    rng = np.random.default_rng(seed)
    lengths = rng.integers(1, 9000, size=int(rng.integers(1, 12)))
    chunks = [rng.uniform(-0.8, 0.8, size=int(length)).astype(np.float32) for length in lengths]
    output = run(chunks)
    total = int(lengths.sum())
    assert np.all(np.isfinite(output))
    assert len(output) <= total
    assert len(output) >= total - (len(chunks) - 1) * FADE
    assert len(output) >= int(lengths.max()) - FADE


@pytest.mark.parametrize("seed", range(10))
def test_untouched_head_of_the_first_chunk(seed):
    rng = np.random.default_rng(1000 + seed)
    first = rng.uniform(-0.5, 0.5, size=int(rng.integers(FADE + 10, 8000))).astype(np.float32)
    second = rng.uniform(-0.5, 0.5, size=int(rng.integers(1, 8000))).astype(np.float32)
    output = run([first, second])
    head = len(first) - FADE
    assert np.array_equal(output[:head], first[:head])


@pytest.mark.parametrize("crossfade_ms", [0, 10, 60, 120])
def test_total_length_matches_the_closed_form_for_long_chunks(crossfade_ms):
    fade = int(RATE * crossfade_ms / 1000)
    chunks = [np.ones(10000, dtype=np.float32) * 0.1 for _ in range(5)]
    assert len(run(chunks, crossfade_ms)) == 5 * 10000 - 4 * fade


@pytest.mark.parametrize("seed", range(15))
def test_equal_power_blend_stays_below_root_two_of_the_peak(seed):
    rng = np.random.default_rng(500 + seed)
    lengths = rng.integers(2 * FADE + 1, 9000, size=int(rng.integers(2, 8)))
    chunks = [rng.uniform(-0.8, 0.8, size=int(length)).astype(np.float32) for length in lengths]
    assert np.max(np.abs(run(chunks))) <= 0.8 * np.sqrt(2) + 1e-4

import numpy as np

from kokoro_stream.streaming.crossfade import Crossfader

SAMPLE_RATE = 24000
FADE = int(SAMPLE_RATE * 0.06)


def run(chunks):
    crossfader = Crossfader(SAMPLE_RATE, 60)
    pieces = [crossfader.push(chunk) for chunk in chunks]
    pieces.append(crossfader.flush())
    return np.concatenate(pieces)


def test_chunk_shorter_than_fade_does_not_step():
    low = np.full(8000, -0.5, dtype=np.float32)
    short = np.full(400, 0.5, dtype=np.float32)
    output = run([low, short, low])
    assert np.max(np.abs(np.diff(output))) < 0.05


def test_short_first_chunk_then_long_chunk():
    first = np.full(500, 0.3, dtype=np.float32)
    second = np.full(9000, -0.3, dtype=np.float32)
    output = run([first, second])
    assert np.max(np.abs(np.diff(output))) < 0.05
    assert len(output) == 500 + 9000 - 500


def test_many_short_chunks_keep_length_bookkeeping():
    chunks = [np.full(700, 0.1 * (index % 3), dtype=np.float32) for index in range(10)]
    output = run(chunks)
    assert len(output) == 700
    assert np.all(np.isfinite(output))


def test_short_chunk_between_long_ones_is_not_dropped():
    long_chunk = np.full(6000, 0.2, dtype=np.float32)
    short = np.full(100, 0.2, dtype=np.float32)
    output = run([long_chunk, short, long_chunk])
    assert len(output) == 6000 + 100 + 6000 - FADE - 100

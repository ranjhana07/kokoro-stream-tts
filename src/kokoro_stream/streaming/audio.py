from __future__ import annotations

import numpy as np


def trim_silence(
    samples: np.ndarray,
    sample_rate: int,
    threshold_db: float = -45.0,
    keep_ms: float = 12.0,
) -> np.ndarray:
    if samples.size == 0:
        return samples
    threshold = 10.0 ** (threshold_db / 20.0)
    audible = np.flatnonzero(np.abs(samples) > threshold)
    if audible.size == 0:
        return samples[:0]
    margin = int(sample_rate * keep_ms / 1000.0)
    start = max(0, int(audible[0]) - margin)
    end = min(samples.size, int(audible[-1]) + 1 + margin)
    return samples[start:end]

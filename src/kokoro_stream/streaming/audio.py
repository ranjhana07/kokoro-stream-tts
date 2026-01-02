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


def lowpass_kernel(cutoff: float, taps: int = 63) -> np.ndarray:
    positions = np.arange(taps) - (taps - 1) / 2.0
    kernel = np.sinc(2.0 * cutoff * positions) * np.hanning(taps)
    return (kernel / kernel.sum()).astype(np.float32)


def resample(samples: np.ndarray, source_rate: int, target_rate: int) -> np.ndarray:
    if source_rate == target_rate or samples.size == 0:
        return samples
    if target_rate < source_rate:
        cutoff = 0.45 * target_rate / source_rate
        samples = np.convolve(samples, lowpass_kernel(cutoff), mode="same")
    target_length = max(1, int(round(samples.size * target_rate / source_rate)))
    source_positions = np.arange(target_length) * (source_rate / target_rate)
    return np.interp(source_positions, np.arange(samples.size), samples).astype(np.float32)

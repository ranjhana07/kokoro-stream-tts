from __future__ import annotations

import time
from typing import Protocol, runtime_checkable

import numpy as np


class EngineError(RuntimeError):
    pass


@runtime_checkable
class SpeechEngine(Protocol):
    sample_rate: int

    def voices(self) -> list[str]: ...

    def synthesize(self, text: str, voice: str, speed: float = 1.0) -> np.ndarray: ...


def warm_up(engine: SpeechEngine, voice: str, rounds: int = 2) -> float:
    started = time.perf_counter()
    for _ in range(rounds):
        engine.synthesize("Warming up the speech engine.", voice, 1.0)
    return time.perf_counter() - started

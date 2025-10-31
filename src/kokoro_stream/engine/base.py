from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np


class EngineError(RuntimeError):
    pass


@runtime_checkable
class SpeechEngine(Protocol):
    sample_rate: int

    def voices(self) -> list[str]: ...

    def synthesize(self, text: str, voice: str, speed: float = 1.0) -> np.ndarray: ...

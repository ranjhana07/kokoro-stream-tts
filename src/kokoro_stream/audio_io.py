from __future__ import annotations

import io
import struct
import wave
from pathlib import Path
from types import TracebackType

import numpy as np

from kokoro_stream.streaming.frames import float_to_pcm16


def encode_wav(samples: np.ndarray, sample_rate: int) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(sample_rate)
        writer.writeframes(float_to_pcm16(samples).tobytes())
    return buffer.getvalue()


UNKNOWN_SIZE = 0xFFFFFFFF


def streaming_wav_header(sample_rate: int, channels: int = 1) -> bytes:
    byte_rate = sample_rate * channels * 2
    return b"".join(
        [
            b"RIFF",
            struct.pack("<I", UNKNOWN_SIZE),
            b"WAVEfmt ",
            struct.pack("<IHHIIHH", 16, 1, channels, sample_rate, byte_rate, channels * 2, 16),
            b"data",
            struct.pack("<I", UNKNOWN_SIZE),
        ]
    )


class WavFileWriter:
    def __init__(self, path: Path, sample_rate: int, channels: int = 1) -> None:
        self.path = path
        self.frames_written = 0
        self.sample_rate = sample_rate
        self._writer = wave.open(str(path), "wb")
        self._writer.setnchannels(channels)
        self._writer.setsampwidth(2)
        self._writer.setframerate(sample_rate)

    def write_float(self, samples: np.ndarray) -> None:
        self.write_pcm(float_to_pcm16(samples))

    def write_pcm(self, pcm: np.ndarray) -> None:
        self._writer.writeframes(pcm.astype("<i2").tobytes())
        self.frames_written += pcm.size

    @property
    def duration(self) -> float:
        return self.frames_written / self.sample_rate

    def close(self) -> None:
        self._writer.close()

    def __enter__(self) -> "WavFileWriter":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

from __future__ import annotations

import struct
from dataclasses import dataclass
from enum import IntEnum

import numpy as np

MAGIC = b"KSTF"
VERSION = 1
HEADER = struct.Struct(">4sBBIIHI")
HEADER_SIZE = HEADER.size
MAX_PAYLOAD_BYTES = 1 << 24
PCM_MAX = 32767


class FrameType(IntEnum):
    AUDIO = 1
    END = 2
    ERROR = 3


class FrameError(ValueError):
    pass


@dataclass(frozen=True)
class Frame:
    frame_type: FrameType
    sequence: int
    sample_rate: int
    channels: int
    payload: bytes = b""

    def samples(self) -> np.ndarray:
        if self.frame_type is not FrameType.AUDIO:
            raise FrameError("only audio frames carry samples")
        return np.frombuffer(self.payload, dtype="<i2")

    def message(self) -> str:
        if self.frame_type is not FrameType.ERROR:
            raise FrameError("only error frames carry a message")
        return self.payload.decode("utf-8", errors="replace")


def float_to_pcm16(samples: np.ndarray) -> np.ndarray:
    clipped = np.clip(samples, -1.0, 1.0)
    return np.rint(clipped * PCM_MAX).astype("<i2")


def pcm16_to_float(samples: np.ndarray) -> np.ndarray:
    return samples.astype(np.float32) / PCM_MAX


def encode_frame(frame: Frame) -> bytes:
    if len(frame.payload) > MAX_PAYLOAD_BYTES:
        raise FrameError("payload too large")
    header = HEADER.pack(
        MAGIC,
        VERSION,
        int(frame.frame_type),
        frame.sequence,
        frame.sample_rate,
        frame.channels,
        len(frame.payload),
    )
    return header + frame.payload


def encode_audio(sequence: int, samples: np.ndarray, sample_rate: int, channels: int = 1) -> bytes:
    pcm = samples if samples.dtype == np.dtype("<i2") else float_to_pcm16(samples)
    return encode_frame(Frame(FrameType.AUDIO, sequence, sample_rate, channels, pcm.tobytes()))


def encode_end(sequence: int, sample_rate: int, channels: int = 1) -> bytes:
    return encode_frame(Frame(FrameType.END, sequence, sample_rate, channels))


def encode_error(sequence: int, message: str, sample_rate: int = 0, channels: int = 1) -> bytes:
    payload = message.encode("utf-8")[:4096]
    return encode_frame(Frame(FrameType.ERROR, sequence, sample_rate, channels, payload))

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

STREAM_MIMETYPE = "application/x-kokoro-frames"
STREAM_FORMATS = ("frames", "pcm", "wav")
MIN_SPEED = 0.5
MAX_SPEED = 2.0
MIN_SAMPLE_RATE = 8000
MAX_SAMPLE_RATE = 48000


class RequestError(ValueError):
    pass


@dataclass(frozen=True)
class TTSRequest:
    text: str
    voice: str
    speed: float
    sample_rate: int
    output_format: str = "frames"


def parse_request(
    payload: object,
    voices: Sequence[str],
    default_voice: str,
    max_text_chars: int,
    native_rate: int,
) -> TTSRequest:
    if not isinstance(payload, dict):
        raise RequestError("request body must be a JSON object")
    text = payload.get("text")
    if not isinstance(text, str) or not text.strip():
        raise RequestError("text is required")
    if len(text) > max_text_chars:
        raise RequestError(f"text is longer than {max_text_chars} characters")
    voice = str(payload.get("voice") or default_voice)
    if voice not in voices:
        raise RequestError(f"unknown voice: {voice}")
    try:
        speed = float(payload.get("speed", 1.0))
    except (TypeError, ValueError) as error:
        raise RequestError("speed must be a number") from error
    if not MIN_SPEED <= speed <= MAX_SPEED:
        raise RequestError(f"speed must be between {MIN_SPEED} and {MAX_SPEED}")
    try:
        sample_rate = int(payload.get("sample_rate", native_rate))
    except (TypeError, ValueError) as error:
        raise RequestError("sample_rate must be an integer") from error
    if not MIN_SAMPLE_RATE <= sample_rate <= MAX_SAMPLE_RATE:
        raise RequestError(f"sample_rate must be between {MIN_SAMPLE_RATE} and {MAX_SAMPLE_RATE}")
    output_format = str(payload.get("format", "frames")).lower()
    if output_format not in STREAM_FORMATS:
        raise RequestError(f"format must be one of {', '.join(STREAM_FORMATS)}")
    return TTSRequest(
        text=text, voice=voice, speed=speed, sample_rate=sample_rate, output_format=output_format
    )

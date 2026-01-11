from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Sequence

import numpy as np
import requests

from kokoro_stream.audio_io import WavFileWriter
from kokoro_stream.streaming.frames import FrameDecoder, FrameType, pcm16_to_float


class StreamError(RuntimeError):
    pass


@dataclass
class StreamResult:
    sample_rate: int = 0
    time_to_first_audio: float = 0.0
    total_seconds: float = 0.0
    frame_count: int = 0
    sample_count: int = 0
    arrivals: list[float] = field(default_factory=list)

    @property
    def audio_seconds(self) -> float:
        return self.sample_count / self.sample_rate if self.sample_rate else 0.0

    @property
    def real_time_factor(self) -> float:
        audio = self.audio_seconds
        return self.total_seconds / audio if audio else float("inf")


AudioCallback = Callable[[np.ndarray, int], None]


def stream_speech(
    base_url: str,
    text: str,
    voice: str | None = None,
    speed: float = 1.0,
    timeout: float = 60.0,
    on_audio: AudioCallback | None = None,
    session: requests.Session | None = None,
    api_key: str | None = None,
    sample_rate: int | None = None,
) -> StreamResult:
    payload: dict[str, object] = {"text": text, "speed": speed}
    if voice:
        payload["voice"] = voice
    if sample_rate:
        payload["sample_rate"] = sample_rate
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    http = session or requests
    result = StreamResult()
    decoder = FrameDecoder()
    started = time.perf_counter()
    with http.post(
        f"{base_url.rstrip('/')}/v1/tts/stream", json=payload, headers=headers, stream=True, timeout=timeout
    ) as response:
        if response.status_code != 200:
            raise StreamError(f"HTTP {response.status_code}: {response.text[:200]}")
        for piece in response.iter_content(chunk_size=None):
            for frame in decoder.feed(piece):
                now = time.perf_counter() - started
                if frame.frame_type is FrameType.ERROR:
                    raise StreamError(frame.message())
                if frame.frame_type is FrameType.END:
                    result.total_seconds = now
                    return result
                if result.frame_count == 0:
                    result.time_to_first_audio = now
                result.sample_rate = frame.sample_rate
                samples = frame.samples()
                result.frame_count += 1
                result.sample_count += samples.size
                result.arrivals.append(now)
                if on_audio:
                    on_audio(pcm16_to_float(samples), frame.sample_rate)
    raise StreamError("stream ended without an end frame")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kokoro-client", description="Stream speech from a kokoro-stream-tts server")
    parser.add_argument("--url", default="http://localhost:8000")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--text")
    source.add_argument("--file", type=Path)
    parser.add_argument("--voice")
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--sample-rate", type=int)
    parser.add_argument("--api-key", default=os.environ.get("KOKORO_API_KEY"))
    parser.add_argument("--out", type=Path, help="write the stream to a WAV file")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    text = args.text if args.text is not None else args.file.read_text(encoding="utf-8")
    writer: WavFileWriter | None = None

    def handle_audio(samples: np.ndarray, sample_rate: int) -> None:
        nonlocal writer
        if args.out and writer is None:
            writer = WavFileWriter(args.out, sample_rate)
        if writer:
            writer.write_float(samples)

    try:
        result = stream_speech(
            args.url,
            text,
            args.voice,
            args.speed,
            on_audio=handle_audio,
            api_key=args.api_key,
            sample_rate=args.sample_rate,
        )
    except (StreamError, requests.RequestException) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    finally:
        if writer:
            writer.close()
    print(
        f"frames={result.frame_count} audio={result.audio_seconds:.2f}s "
        f"ttfa={result.time_to_first_audio * 1000:.0f}ms total={result.total_seconds:.2f}s "
        f"rtf={result.real_time_factor:.2f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

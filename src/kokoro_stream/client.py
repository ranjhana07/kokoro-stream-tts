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

RETRYABLE_STATUS = frozenset({429, 503})
MAX_RETRY_DELAY = 5.0


def retry_delay(response: requests.Response, attempt: int) -> float:
    header = response.headers.get("Retry-After", "")
    try:
        delay = float(header)
    except ValueError:
        delay = 0.25 * (2**attempt)
    return min(max(delay, 0.0), MAX_RETRY_DELAY)


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
    retries: int = 0,
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
    url = f"{base_url.rstrip('/')}/v1/tts/stream"
    attempt = 0
    while True:
        response = http.post(url, json=payload, headers=headers, stream=True, timeout=timeout)
        if response.status_code not in RETRYABLE_STATUS or attempt >= retries:
            break
        delay = retry_delay(response, attempt)
        response.close()
        attempt += 1
        time.sleep(delay)
    with response:
        if response.status_code != 200:
            raise StreamError(f"HTTP {response.status_code}: {response.text[:200]}")
        for piece in response.iter_content(chunk_size=None):
            for frame in decoder.feed(piece):
                now = time.perf_counter() - started
                if frame.frame_type is FrameType.ERROR:
                    raise StreamError(frame.message())
                if frame.frame_type is FrameType.END:
                    if frame.sequence != result.frame_count:
                        raise StreamError(
                            f"end frame reports {frame.sequence} audio frames, received {result.frame_count}"
                        )
                    result.total_seconds = now
                    return result
                if frame.sequence != result.frame_count:
                    raise StreamError(f"frame {frame.sequence} arrived where {result.frame_count} was expected")
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


class Player:
    def __init__(self) -> None:
        try:
            import sounddevice
        except ImportError as error:
            raise StreamError("playback needs the sounddevice package") from error
        self._sounddevice = sounddevice
        self._stream = None

    def write(self, samples: np.ndarray, sample_rate: int) -> None:
        if self._stream is None:
            self._stream = self._sounddevice.OutputStream(samplerate=sample_rate, channels=1, dtype="float32")
            self._stream.start()
        self._stream.write(samples.reshape(-1, 1).astype(np.float32))

    def close(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kokoro-client", description="Stream speech from a kokoro-stream-tts server")
    parser.add_argument("--url", default="http://localhost:8000")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--text")
    source.add_argument("--file", type=Path)
    parser.add_argument("--voice")
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--sample-rate", type=int)
    parser.add_argument("--retries", type=int, default=0, help="retries when the service answers 429 or 503")
    parser.add_argument("--api-key", default=os.environ.get("KOKORO_API_KEY"))
    parser.add_argument("--out", type=Path, help="write the stream to a WAV file")
    parser.add_argument("--play", action="store_true", help="play the audio while it streams, needs sounddevice")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    text = args.text if args.text is not None else args.file.read_text(encoding="utf-8")
    writer: WavFileWriter | None = None
    try:
        player = Player() if args.play else None
    except StreamError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    def handle_audio(samples: np.ndarray, sample_rate: int) -> None:
        nonlocal writer
        if args.out and writer is None:
            writer = WavFileWriter(args.out, sample_rate)
        if writer:
            writer.write_float(samples)
        if player:
            player.write(samples, sample_rate)

    try:
        result = stream_speech(
            args.url,
            text,
            args.voice,
            args.speed,
            on_audio=handle_audio,
            api_key=args.api_key,
            sample_rate=args.sample_rate,
            retries=args.retries,
        )
    except (StreamError, requests.RequestException) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    finally:
        if writer:
            writer.close()
        if player:
            player.close()
    print(
        f"frames={result.frame_count} audio={result.audio_seconds:.2f}s "
        f"ttfa={result.time_to_first_audio * 1000:.0f}ms total={result.total_seconds:.2f}s "
        f"rtf={result.real_time_factor:.2f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

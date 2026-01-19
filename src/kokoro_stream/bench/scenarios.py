from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from typing import Any, Iterator

import requests
from werkzeug.serving import make_server

from kokoro_stream.client import stream_speech
from kokoro_stream.config import Settings
from kokoro_stream.engine.base import SpeechEngine
from kokoro_stream.loadtest import run_streams, summarize
from kokoro_stream.service.app import create_app


@contextmanager
def running_service(settings: Settings, engine: SpeechEngine | None = None) -> Iterator[str]:
    app = create_app(settings, engine)
    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=10)


def full_synthesis_latency(url: str, text: str, voice: str | None) -> dict[str, float]:
    payload: dict[str, Any] = {"text": text}
    if voice:
        payload["voice"] = voice
    started = time.perf_counter()
    with requests.post(f"{url}/v1/tts", json=payload, stream=True, timeout=600) as response:
        response.raise_for_status()
        first_byte = None
        size = 0
        for piece in response.iter_content(chunk_size=8192):
            if first_byte is None:
                first_byte = time.perf_counter() - started
            size += len(piece)
        total = time.perf_counter() - started
        audio_seconds = float(response.headers.get("X-Audio-Duration", "0"))
    return {"ttfa_ms": (first_byte or total) * 1000, "total_ms": total * 1000, "audio_s": audio_seconds}


def streaming_latency(url: str, text: str, voice: str | None) -> dict[str, float]:
    result = stream_speech(url, text, voice, timeout=600)
    return {
        "ttfa_ms": result.time_to_first_audio * 1000,
        "total_ms": result.total_seconds * 1000,
        "audio_s": result.audio_seconds,
    }


def run_ttfa_comparison(
    url: str, prompts: dict[str, str], repetitions: int, voice: str | None
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name, text in prompts.items():
        for repetition in range(repetitions):
            for mode, measure in (("full", full_synthesis_latency), ("stream", streaming_latency)):
                measurement = measure(url, text, voice)
                rows.append(
                    {
                        "scenario": "ttfa",
                        "prompt": name,
                        "prompt_chars": len(text),
                        "mode": mode,
                        "repetition": repetition,
                        **{key: round(value, 3) for key, value in measurement.items()},
                    }
                )
    return rows


def run_concurrency(
    url: str, text: str, prompt_name: str, stream_counts: list[int], rounds: int, voice: str | None
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for streams in stream_counts:
        for round_index in range(rounds):
            samples = run_streams(lambda: stream_speech(url, text, voice, timeout=900), streams)
            for index, sample in enumerate(samples):
                rows.append(
                    {
                        "scenario": "concurrency",
                        "prompt": prompt_name,
                        "streams": streams,
                        "round": round_index,
                        "stream": index,
                        "ttfa_ms": round(sample.ttfa * 1000, 3),
                        "total_ms": round(sample.total * 1000, 3),
                        "audio_s": round(sample.audio_seconds, 3),
                        "rtf": round(sample.real_time_factor, 4),
                        "error": sample.error or "",
                    }
                )
    return rows


def summarize_ttfa(rows: list[dict[str, Any]]) -> dict[str, Any]:
    from kokoro_stream.loadtest import percentile

    summary: dict[str, Any] = {}
    for prompt in sorted({row["prompt"] for row in rows}):
        for mode in ("full", "stream"):
            values = [row["ttfa_ms"] for row in rows if row["prompt"] == prompt and row["mode"] == mode]
            if values:
                summary[f"{prompt}/{mode}"] = {
                    "runs": len(values),
                    "ttfa_ms_median": round(percentile(values, 0.5), 1),
                    "ttfa_ms_min": round(min(values), 1),
                    "ttfa_ms_max": round(max(values), 1),
                }
    return summary


def summarize_concurrency(rows: list[dict[str, Any]]) -> dict[str, Any]:
    from kokoro_stream.loadtest import StreamSample

    summary: dict[str, Any] = {}
    for streams in sorted({row["streams"] for row in rows}):
        samples = [
            StreamSample(row["ttfa_ms"] / 1000, row["total_ms"] / 1000, row["audio_s"], row["error"] or None)
            for row in rows
            if row["streams"] == streams
        ]
        stats = summarize(samples)
        summary[str(streams)] = {key: (round(value, 2) if isinstance(value, float) else value) for key, value in stats.items()}
    return summary

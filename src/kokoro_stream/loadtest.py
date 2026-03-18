from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Sequence

import numpy as np

from kokoro_stream.client import StreamResult, stream_speech

DEFAULT_TEXT = (
    "Streaming synthesis sends the first sentence as soon as it is ready. "
    "The remaining sentences are prepared in the background while audio is already playing. "
    "That keeps the wait before the first sound short, even when the full text is long."
)

StreamFunction = Callable[[], StreamResult]


@dataclass(frozen=True)
class StreamSample:
    ttfa: float
    total: float
    audio_seconds: float
    error: str | None = None

    @property
    def real_time_factor(self) -> float:
        return self.total / self.audio_seconds if self.audio_seconds else float("inf")


def percentile(values: Sequence[float], fraction: float) -> float:
    if not values:
        return float("nan")
    return float(np.percentile(np.asarray(values, dtype=np.float64), fraction * 100.0))


def run_streams(stream_function: StreamFunction, streams: int) -> list[StreamSample]:
    samples: list[StreamSample | None] = [None] * streams
    barrier = threading.Barrier(streams)

    def worker(index: int) -> None:
        barrier.wait()
        try:
            result = stream_function()
            samples[index] = StreamSample(
                result.time_to_first_audio, result.total_seconds, result.audio_seconds
            )
        except Exception as error:
            samples[index] = StreamSample(float("nan"), float("nan"), 0.0, error=str(error))

    threads = [threading.Thread(target=worker, args=(index,)) for index in range(streams)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return [sample for sample in samples if sample is not None]


def summarize(samples: Sequence[StreamSample]) -> dict[str, float | int]:
    good = [sample for sample in samples if sample.error is None]
    ttfa = [sample.ttfa for sample in good]
    factors = [sample.real_time_factor for sample in good]
    return {
        "streams": len(samples),
        "errors": len(samples) - len(good),
        "ttfa_p50_ms": percentile(ttfa, 0.50) * 1000,
        "ttfa_p95_ms": percentile(ttfa, 0.95) * 1000,
        "ttfa_max_ms": (max(ttfa) * 1000) if ttfa else float("nan"),
        "rtf_mean": statistics.fmean(factors) if factors else float("nan"),
        "rtf_p95": percentile(factors, 0.95),
    }


def write_csv(path: Path, samples: Sequence[StreamSample]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["ttfa_ms", "total_ms", "audio_s", "rtf", "error"])
        for sample in samples:
            writer.writerow(
                [
                    round(sample.ttfa * 1000, 3),
                    round(sample.total * 1000, 3),
                    round(sample.audio_seconds, 3),
                    round(sample.real_time_factor, 4),
                    sample.error or "",
                ]
            )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kokoro-loadtest", description="Open concurrent streams and report TTFA and real-time factor")
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--streams", type=int, default=25)
    parser.add_argument("--voice")
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--api-key", default=os.environ.get("KOKORO_API_KEY"))
    parser.add_argument("--text")
    parser.add_argument("--file", type=Path)
    parser.add_argument("--rounds", type=int, default=1, help="repeat the whole set of streams this many times")
    parser.add_argument("--json", type=Path, help="write the summary to this file")
    parser.add_argument("--csv", type=Path, help="write one row per stream to this file")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.file:
        text = args.file.read_text(encoding="utf-8")
    else:
        text = args.text or DEFAULT_TEXT
    samples: list[StreamSample] = []
    for _ in range(max(1, args.rounds)):
        samples.extend(
            run_streams(
                lambda: stream_speech(args.url, text, args.voice, args.speed, api_key=args.api_key),
                args.streams,
            )
        )
    summary = summarize(samples)
    print(f"streams      {summary['streams']}  errors {summary['errors']}")
    print(f"ttfa p50     {summary['ttfa_p50_ms']:.0f} ms")
    print(f"ttfa p95     {summary['ttfa_p95_ms']:.0f} ms")
    print(f"ttfa max     {summary['ttfa_max_ms']:.0f} ms")
    print(f"rtf mean     {summary['rtf_mean']:.3f}")
    print(f"rtf p95      {summary['rtf_p95']:.3f}")
    if args.json:
        payload = {"summary": summary, "samples": [asdict(sample) for sample in samples]}
        args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    if args.csv:
        write_csv(args.csv, samples)
    return 1 if summary["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

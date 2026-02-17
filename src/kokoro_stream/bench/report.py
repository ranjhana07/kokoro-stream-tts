from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

SETTING_KEYS = (
    "engine",
    "intra_op_threads",
    "prefetch_workers",
    "prefetch_depth",
    "prefetch_head_first",
    "first_chunk_chars",
    "max_chunk_chars",
    "trim_silence",
    "crossfade_ms",
    "chunk_cache_mb",
)


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def table(headers: Sequence[str], rows: Sequence[Sequence[object]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return "\n".join(lines)


def describe(document: dict[str, Any]) -> str:
    host = document["host"]
    settings = document["settings"]
    arguments = document.get("arguments", {})
    model = Path(arguments.get("model_file", "")).name or arguments.get("model_file", "")
    parts = [f"{key}={settings[key]}" for key in SETTING_KEYS if key in settings]
    header = (
        f"{document['name']}: {host['cpu']}, {host['logical_cores']} logical cores, {host['os']}, "
        f"onnxruntime {host['onnxruntime']}, model {model}, "
        f"background cpu before run {host.get('cpu_utilization_before_run_percent')}%"
    )
    return header + "\n" + ", ".join(parts)


def ttfa_table(document: dict[str, Any]) -> str:
    rows = []
    for key, stats in sorted(document["summary"].items()):
        prompt, mode = key.split("/")
        rows.append([prompt, mode, stats["runs"], stats["ttfa_ms_median"], stats["ttfa_ms_min"], stats["ttfa_ms_max"]])
    return table(["prompt", "mode", "runs", "median ms", "min ms", "max ms"], rows)


def concurrency_table(document: dict[str, Any]) -> str:
    rows = []
    for streams, stats in sorted(document["summary"].items(), key=lambda item: int(item[0])):
        rows.append(
            [
                streams,
                stats["streams"],
                stats["errors"],
                stats["ttfa_p50_ms"],
                stats["ttfa_p95_ms"],
                stats["ttfa_max_ms"],
                stats["rtf_mean"],
            ]
        )
    return table(["concurrent streams", "samples", "errors", "ttfa p50 ms", "ttfa p95 ms", "ttfa max ms", "mean rtf"], rows)


def render(document: dict[str, Any]) -> str:
    rows = document["rows"]
    scenario = rows[0]["scenario"] if rows else "empty"
    body = ttfa_table(document) if scenario == "ttfa" else concurrency_table(document)
    return describe(document) + "\n\n" + body + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kokoro-bench-report", description="Render result files as markdown tables")
    parser.add_argument("files", nargs="+", type=Path)
    args = parser.parse_args(argv)
    print("\n".join(render(load(path)) for path in args.files))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

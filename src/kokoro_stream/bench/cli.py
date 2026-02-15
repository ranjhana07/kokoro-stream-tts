from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path
from typing import Sequence

from kokoro_stream.bench import hostinfo
from kokoro_stream.bench.results import write_results
from kokoro_stream.bench.scenarios import (
    run_concurrency,
    run_ttfa_comparison,
    running_service,
    summarize_concurrency,
    summarize_ttfa,
)
from kokoro_stream.config import Settings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kokoro-bench", description="Measure time to first audio and concurrency")
    parser.add_argument("--scenario", choices=["ttfa", "concurrency"], required=True)
    parser.add_argument("--name", required=True, help="result file name without extension")
    parser.add_argument("--out-dir", type=Path, default=Path("benchmarks/results"))
    parser.add_argument("--prompts-dir", type=Path, default=Path("benchmarks/prompts"))
    parser.add_argument("--prompts", default="short,medium,long", help="comma separated prompt names")
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--streams", default="1,5,10,25", help="comma separated stream counts")
    parser.add_argument("--rounds", type=int, default=2)
    parser.add_argument("--voice")
    parser.add_argument("--engine", choices=["kokoro", "sine"], default="kokoro")
    parser.add_argument("--model-dir", type=Path, default=Path("models"))
    parser.add_argument("--model-file", default="kokoro-v1.0.onnx")
    parser.add_argument("--intra-op-threads", type=int)
    parser.add_argument("--workers", type=int, help="prefetch pool threads")
    parser.add_argument("--depth", type=int, help="prefetch depth per stream")
    parser.add_argument("--first-chunk-chars", type=int)
    parser.add_argument("--max-chunk-chars", type=int)
    parser.add_argument("--no-trim", action="store_true")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--high-priority", action="store_true", help="raise the process priority on a busy host")
    return parser


def settings_from_args(args: argparse.Namespace) -> Settings:
    settings = Settings.from_env(
        {
            "KOKORO_ENGINE": args.engine,
            "KOKORO_MODEL_PATH": str(args.model_dir / args.model_file),
            "KOKORO_VOICES_PATH": str(args.model_dir / "voices-v1.0.bin"),
            "KOKORO_VOCAB_PATH": str(args.model_dir / "config.json"),
        }
    )
    overrides: dict[str, object] = {"chunk_cache_mb": 0 if args.no_cache else settings.chunk_cache_mb, "max_streams": 0}
    if args.intra_op_threads:
        overrides["intra_op_threads"] = args.intra_op_threads
    if args.workers:
        overrides["prefetch_workers"] = args.workers
    if args.depth:
        overrides["prefetch_depth"] = args.depth
    if args.first_chunk_chars:
        overrides["first_chunk_chars"] = args.first_chunk_chars
    if args.max_chunk_chars:
        overrides["max_chunk_chars"] = args.max_chunk_chars
    if args.no_trim:
        overrides["trim_silence"] = False
    return dataclasses.replace(settings, **overrides).validate()


def load_prompts(directory: Path, names: Sequence[str]) -> dict[str, str]:
    prompts: dict[str, str] = {}
    for name in names:
        path = directory / f"{name}.txt"
        prompts[name] = " ".join(path.read_text(encoding="utf-8").split())
    return prompts


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = settings_from_args(args)
    priority_raised = hostinfo.raise_priority() if args.high_priority else False
    names = [name.strip() for name in args.prompts.split(",") if name.strip()]
    prompts = load_prompts(args.prompts_dir, names)
    with running_service(settings) as url:
        if args.scenario == "ttfa":
            rows = run_ttfa_comparison(url, prompts, args.repetitions, args.voice)
            summary = summarize_ttfa(rows)
        else:
            counts = [int(value) for value in args.streams.split(",")]
            prompt_name = names[0]
            rows = run_concurrency(url, prompts[prompt_name], prompt_name, counts, args.rounds, args.voice)
            summary = summarize_concurrency(rows)
    arguments = {key: str(value) for key, value in vars(args).items()}
    arguments["priority_raised"] = str(priority_raised)
    json_path, csv_path = write_results(
        args.out_dir, args.name, rows, summary, dataclasses.asdict(settings), arguments
    )
    print(json.dumps(summary, indent=2))
    print(f"wrote {json_path} and {csv_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

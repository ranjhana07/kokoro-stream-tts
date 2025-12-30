from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping


def _read_int(environ: Mapping[str, str], name: str, default: int) -> int:
    raw = environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


def _read_float(environ: Mapping[str, str], name: str, default: float) -> float:
    raw = environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return float(raw)


def _read_list(environ: Mapping[str, str], name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return tuple(part.strip() for part in raw.split(",") if part.strip())


@dataclass(frozen=True)
class Settings:
    engine: str = "sine"
    model_path: str = "models/kokoro-v1.0.onnx"
    voices_path: str = "models/voices-v1.0.bin"
    vocab_path: str = "models/config.json"
    providers: tuple[str, ...] = ("CPUExecutionProvider",)
    intra_op_threads: int = 2
    sample_rate: int = 24000
    default_voice: str = "af_heart"
    first_chunk_chars: int = 60
    max_chunk_chars: int = 220
    prefetch_depth: int = 3
    prefetch_workers: int = 4
    crossfade_ms: int = 60
    kafka_bootstrap: str = ""
    kafka_request_topic: str = "tts.jobs.requests"
    kafka_status_topic: str = "tts.jobs.status"
    kafka_group: str = "tts-workers"
    output_dir: str = "output"
    job_output: str = "output/audio"
    warmup: bool = True
    max_text_chars: int = 5000
    max_job_text_chars: int = 200000

    def validate(self) -> "Settings":
        if self.engine not in ("sine", "kokoro"):
            raise ValueError(f"KOKORO_ENGINE must be sine or kokoro, got {self.engine!r}")
        if self.sample_rate <= 0:
            raise ValueError("SAMPLE_RATE must be positive")
        if self.prefetch_depth < 1 or self.prefetch_workers < 1:
            raise ValueError("PREFETCH_DEPTH and PREFETCH_WORKERS must be at least 1")
        if self.crossfade_ms < 0:
            raise ValueError("CROSSFADE_MS cannot be negative")
        if not 0 < self.first_chunk_chars <= self.max_chunk_chars:
            raise ValueError("FIRST_CHUNK_CHARS must be positive and no larger than MAX_CHUNK_CHARS")
        if self.intra_op_threads < 1:
            raise ValueError("KOKORO_INTRA_OP_THREADS must be at least 1")
        return self

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "Settings":
        env = os.environ if environ is None else environ
        defaults = cls()
        return cls(
            engine=env.get("KOKORO_ENGINE", defaults.engine),
            model_path=env.get("KOKORO_MODEL_PATH", defaults.model_path),
            voices_path=env.get("KOKORO_VOICES_PATH", defaults.voices_path),
            vocab_path=env.get("KOKORO_VOCAB_PATH", defaults.vocab_path),
            providers=_read_list(env, "KOKORO_PROVIDERS", defaults.providers),
            intra_op_threads=_read_int(env, "KOKORO_INTRA_OP_THREADS", defaults.intra_op_threads),
            sample_rate=_read_int(env, "SAMPLE_RATE", defaults.sample_rate),
            default_voice=env.get("DEFAULT_VOICE", defaults.default_voice),
            first_chunk_chars=_read_int(env, "FIRST_CHUNK_CHARS", defaults.first_chunk_chars),
            max_chunk_chars=_read_int(env, "MAX_CHUNK_CHARS", defaults.max_chunk_chars),
            prefetch_depth=_read_int(env, "PREFETCH_DEPTH", defaults.prefetch_depth),
            prefetch_workers=_read_int(env, "PREFETCH_WORKERS", defaults.prefetch_workers),
            crossfade_ms=_read_int(env, "CROSSFADE_MS", defaults.crossfade_ms),
            kafka_bootstrap=env.get("KAFKA_BOOTSTRAP", defaults.kafka_bootstrap),
            kafka_request_topic=env.get("KAFKA_REQUEST_TOPIC", defaults.kafka_request_topic),
            kafka_status_topic=env.get("KAFKA_STATUS_TOPIC", defaults.kafka_status_topic),
            kafka_group=env.get("KAFKA_GROUP", defaults.kafka_group),
            output_dir=env.get("OUTPUT_DIR", defaults.output_dir),
            job_output=env.get("JOB_OUTPUT", defaults.job_output),
            warmup=_read_int(env, "WARMUP", int(defaults.warmup)) != 0,
            max_text_chars=_read_int(env, "MAX_TEXT_CHARS", defaults.max_text_chars),
            max_job_text_chars=_read_int(env, "MAX_JOB_TEXT_CHARS", defaults.max_job_text_chars),
        ).validate()

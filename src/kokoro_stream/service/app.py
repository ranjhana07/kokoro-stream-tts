from __future__ import annotations

import time
import uuid
from pathlib import Path

from flask import Flask, Response, g, jsonify, request, send_file

from kokoro_stream.audio_io import encode_wav, streaming_wav_header
from kokoro_stream.config import Settings
from kokoro_stream.engine.base import EngineError, SpeechEngine, warm_up
from kokoro_stream.engine.factory import build_engine
from kokoro_stream.jobs.kafka_io import JobPublisher, KafkaJobPublisher
from kokoro_stream.jobs.models import JobRequest, JobState, JobStatus, new_job_id
from kokoro_stream.jobs.store import FileJobStore, JobStore
from kokoro_stream.service.auth import OPEN_ENDPOINTS, extract_token, is_authorized
from kokoro_stream.service.limits import ReleasingIterator, StreamLimiter
from kokoro_stream.service.metrics import Metrics
from kokoro_stream.service.streams import instrument_stream
from kokoro_stream.service.requests import (
    STREAM_MIMETYPE,
    RequestError,
    TTSRequest,
    parse_request,
)
from kokoro_stream.streaming.cache import ChunkCache
from kokoro_stream.streaming.frames import HEADER_SIZE
from kokoro_stream.streaming.pipeline import StreamingSynthesizer
from kokoro_stream.streaming.prefetch import PrefetchPool
from kokoro_stream.text.ssml import SSMLError


def create_app(
    settings: Settings | None = None,
    engine: SpeechEngine | None = None,
    publisher: JobPublisher | None = None,
    job_store: JobStore | None = None,
) -> Flask:
    settings = settings or Settings.from_env()
    engine = engine or build_engine(settings)
    if publisher is None and settings.kafka_bootstrap:
        publisher = KafkaJobPublisher(
            settings.kafka_bootstrap, settings.kafka_request_topic, settings.kafka_status_topic
        )
    job_store = job_store or FileJobStore(Path(settings.output_dir) / "status")
    voices_available = engine.voices()
    default_voice = (
        settings.default_voice if settings.default_voice in voices_available else voices_available[0]
    )
    metrics = Metrics()
    limiter = StreamLimiter(settings.max_streams)
    if settings.warmup:
        metrics.warmup_seconds.set(warm_up(engine, default_voice))
    pool = PrefetchPool(settings.prefetch_workers)
    cache = ChunkCache(settings.chunk_cache_mb * 1024 * 1024) if settings.chunk_cache_mb else None
    if cache is not None:
        metrics.track_cache(cache)
    synthesizer = StreamingSynthesizer(
        engine, pool, settings, chunk_observer=metrics.chunk_latency.observe, cache=cache
    )
    app = Flask(__name__)
    app.extensions["synthesizer"] = synthesizer
    app.extensions["metrics"] = metrics

    def read_request(max_chars: int) -> TTSRequest:
        return parse_request(
            request.get_json(silent=True), voices_available, default_voice, max_chars, engine.sample_rate
        )

    @app.before_request
    def require_api_key():
        if not settings.api_keys or request.endpoint in OPEN_ENDPOINTS:
            return None
        if not is_authorized(extract_token(request.headers), settings.api_keys):
            response = jsonify(error="missing or invalid API key")
            response.status_code = 401
            response.headers["WWW-Authenticate"] = "Bearer"
            return response
        return None

    @app.before_request
    def assign_request_id():
        g.request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]

    @app.after_request
    def count_request(response: Response):
        response.headers["X-Request-ID"] = g.get("request_id", "")
        if request.endpoint and request.endpoint != "metrics":
            metrics.requests.labels(request.endpoint, str(response.status_code)).inc()
        return response

    @app.get("/metrics")
    def metrics_endpoint():
        return Response(metrics.render(), mimetype=Metrics.content_type)

    @app.errorhandler(RequestError)
    @app.errorhandler(SSMLError)
    def bad_request(error: Exception):
        return jsonify(error=str(error)), 400

    @app.errorhandler(EngineError)
    def engine_failure(error: Exception):
        return jsonify(error=str(error)), 422

    @app.get("/healthz")
    def healthz():
        return jsonify(status="ok", engine=type(engine).__name__, sample_rate=engine.sample_rate)

    @app.get("/v1/voices")
    def voices():
        return jsonify(voices=voices_available, default=default_voice)

    @app.post("/v1/tts")
    def tts():
        tts_request = read_request(settings.max_text_chars)
        chunks = synthesizer.prepare(tts_request.text)
        audio = synthesizer.synthesize(
            chunks, tts_request.voice, tts_request.speed, tts_request.sample_rate
        )
        body = encode_wav(audio, tts_request.sample_rate)
        response = Response(body, mimetype="audio/wav")
        response.headers["X-Audio-Duration"] = f"{audio.size / tts_request.sample_rate:.3f}"
        return response

    @app.post("/v1/tts/stream")
    def tts_stream():
        started = time.perf_counter()
        tts_request = read_request(settings.max_text_chars)
        chunks = synthesizer.prepare(tts_request.text)
        if not limiter.try_acquire():
            metrics.rejected_streams.inc()
            response = jsonify(error="too many concurrent streams")
            response.status_code = 429
            response.headers["Retry-After"] = "1"
            return response
        is_framed = tts_request.output_format == "frames"
        if is_framed:
            source = synthesizer.frames(
                chunks, tts_request.voice, tts_request.speed, tts_request.sample_rate
            )
            mimetype = STREAM_MIMETYPE
        else:
            header = streaming_wav_header(tts_request.sample_rate) if tts_request.output_format == "wav" else b""
            source = synthesizer.pcm_stream(
                chunks, tts_request.voice, tts_request.speed, tts_request.sample_rate, header
            )
            mimetype = "audio/wav" if header else f"audio/L16;rate={tts_request.sample_rate};channels=1"
        body = ReleasingIterator(
            instrument_stream(
                source,
                metrics,
                started,
                g.request_id,
                detect_errors=is_framed,
                bytes_per_second=tts_request.sample_rate * 2,
                frame_overhead=HEADER_SIZE if is_framed else 0,
            ),
            limiter.release,
        )
        response = Response(body, mimetype=mimetype)
        response.headers["X-Sample-Rate"] = str(tts_request.sample_rate)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Accel-Buffering"] = "no"
        return response

    @app.post("/v1/jobs")
    def submit_job():
        if publisher is None:
            return jsonify(error="async jobs are not configured"), 503
        tts_request = read_request(settings.max_job_text_chars)
        job_id = new_job_id()
        job_request = JobRequest(job_id, tts_request.text, tts_request.voice, tts_request.speed)
        job_store.put(JobStatus(job_id, JobState.QUEUED))
        try:
            publisher.submit(job_request)
        except Exception as error:
            job_store.put(JobStatus(job_id, JobState.FAILED, detail=f"could not enqueue: {error}"))
            return jsonify(error="could not enqueue job"), 503
        return jsonify(job_id=job_id, state=JobState.QUEUED.value, status_url=f"/v1/jobs/{job_id}"), 202

    @app.get("/v1/jobs/<job_id>")
    def job_status(job_id: str):
        status = job_store.get(job_id)
        if status is None:
            return jsonify(error="job not found"), 404
        return jsonify(status.to_dict())

    @app.delete("/v1/jobs/<job_id>")
    def cancel_job(job_id: str):
        status = job_store.get(job_id)
        if status is None:
            return jsonify(error="job not found"), 404
        if status.state is not JobState.QUEUED:
            return jsonify(error=f"job is {status.state.value} and cannot be cancelled"), 409
        cancelled = JobStatus(job_id, JobState.CANCELLED, detail="cancelled by request")
        job_store.put(cancelled)
        return jsonify(cancelled.to_dict())

    @app.get("/v1/jobs/<job_id>/audio")
    def job_audio(job_id: str):
        status = job_store.get(job_id)
        if status is None:
            return jsonify(error="job not found"), 404
        if status.state is not JobState.DONE:
            return jsonify(error=f"job is {status.state.value}"), 409
        if status.output.startswith("s3://"):
            return jsonify(location=status.output)
        root = Path(settings.job_output).resolve()
        target = Path(status.output).resolve()
        if root != target.parent or not target.is_file():
            return jsonify(error="audio file is not available"), 404
        return send_file(target, mimetype="audio/wav", download_name=f"{job_id}.wav")

    return app

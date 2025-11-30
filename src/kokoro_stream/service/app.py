from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Iterator

from flask import Flask, Response, jsonify, request

from kokoro_stream.audio_io import encode_wav
from kokoro_stream.config import Settings
from kokoro_stream.engine.base import EngineError, SpeechEngine
from kokoro_stream.engine.factory import build_engine
from kokoro_stream.service.metrics import Metrics
from kokoro_stream.streaming.frames import FrameType
from kokoro_stream.streaming.pipeline import StreamingSynthesizer
from kokoro_stream.streaming.prefetch import PrefetchPool
from kokoro_stream.text.ssml import SSMLError


STREAM_MIMETYPE = "application/x-kokoro-frames"


class RequestError(ValueError):
    pass


@dataclass(frozen=True)
class TTSRequest:
    text: str
    voice: str
    speed: float


def parse_request(payload: object, settings: Settings) -> TTSRequest:
    if not isinstance(payload, dict):
        raise RequestError("request body must be a JSON object")
    text = payload.get("text")
    if not isinstance(text, str) or not text.strip():
        raise RequestError("text is required")
    voice = payload.get("voice") or settings.default_voice
    try:
        speed = float(payload.get("speed", 1.0))
    except (TypeError, ValueError) as error:
        raise RequestError("speed must be a number") from error
    return TTSRequest(text=text, voice=str(voice), speed=speed)


def instrument_stream(frames: Iterator[bytes], metrics: Metrics, started: float) -> Iterator[bytes]:
    metrics.active_streams.inc()
    first_frame = True
    try:
        for frame in frames:
            if first_frame:
                metrics.ttfa.observe(time.perf_counter() - started)
                first_frame = False
            if frame[5] == FrameType.ERROR:
                metrics.stream_errors.inc()
            yield frame
    finally:
        metrics.active_streams.dec()
        close = getattr(frames, "close", None)
        if close:
            close()


def create_app(settings: Settings | None = None, engine: SpeechEngine | None = None) -> Flask:
    settings = settings or Settings.from_env()
    engine = engine or build_engine(settings)
    metrics = Metrics()
    pool = PrefetchPool(settings.prefetch_workers)
    synthesizer = StreamingSynthesizer(
        engine, pool, settings, chunk_observer=metrics.chunk_latency.observe
    )
    app = Flask(__name__)
    app.extensions["synthesizer"] = synthesizer
    app.extensions["metrics"] = metrics

    @app.after_request
    def count_request(response: Response):
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
        return jsonify(voices=engine.voices(), default=settings.default_voice)

    @app.post("/v1/tts")
    def tts():
        tts_request = parse_request(request.get_json(silent=True), settings)
        chunks = synthesizer.prepare(tts_request.text)
        audio = synthesizer.synthesize(chunks, tts_request.voice, tts_request.speed)
        body = encode_wav(audio, engine.sample_rate)
        response = Response(body, mimetype="audio/wav")
        response.headers["X-Audio-Duration"] = f"{audio.size / engine.sample_rate:.3f}"
        return response

    @app.post("/v1/tts/stream")
    def tts_stream():
        started = time.perf_counter()
        tts_request = parse_request(request.get_json(silent=True), settings)
        chunks = synthesizer.prepare(tts_request.text)
        frames = synthesizer.frames(chunks, tts_request.voice, tts_request.speed)
        response = Response(instrument_stream(frames, metrics, started), mimetype=STREAM_MIMETYPE)
        response.headers["X-Sample-Rate"] = str(engine.sample_rate)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Accel-Buffering"] = "no"
        return response

    return app

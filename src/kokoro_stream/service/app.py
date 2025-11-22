from __future__ import annotations

import io
import wave
from dataclasses import dataclass

import numpy as np
from flask import Flask, Response, jsonify, request

from kokoro_stream.config import Settings
from kokoro_stream.engine.base import EngineError, SpeechEngine
from kokoro_stream.engine.factory import build_engine
from kokoro_stream.streaming.frames import float_to_pcm16
from kokoro_stream.streaming.pipeline import StreamingSynthesizer
from kokoro_stream.streaming.prefetch import PrefetchPool
from kokoro_stream.text.ssml import SSMLError


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


def encode_wav(samples: np.ndarray, sample_rate: int) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(sample_rate)
        writer.writeframes(float_to_pcm16(samples).tobytes())
    return buffer.getvalue()


def create_app(settings: Settings | None = None, engine: SpeechEngine | None = None) -> Flask:
    settings = settings or Settings.from_env()
    engine = engine or build_engine(settings)
    pool = PrefetchPool(settings.prefetch_workers)
    synthesizer = StreamingSynthesizer(engine, pool, settings)
    app = Flask(__name__)
    app.extensions["synthesizer"] = synthesizer

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

    return app

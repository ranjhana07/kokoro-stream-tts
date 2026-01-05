import io
import wave

import numpy as np
import pytest

from kokoro_stream.config import Settings
from kokoro_stream.engine.sine import SineEngine
from kokoro_stream.service.app import create_app
from kokoro_stream.streaming.frames import FrameDecoder, FrameType, decode_all

TEXT = (
    "Streaming speech needs a short first chunk. The rest can be larger and arrives later. "
    "Each sentence is synthesized while the previous one is being sent."
)


@pytest.fixture
def client():
    settings = Settings(first_chunk_chars=40, max_chunk_chars=120, default_voice="sine_mid")
    app = create_app(settings, SineEngine(sample_rate=settings.sample_rate))
    return app.test_client()


def test_healthz(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json["status"] == "ok"
    assert response.json["sample_rate"] == 24000


def test_voices(client):
    response = client.get("/v1/voices")
    assert response.json["voices"] == ["sine_low", "sine_mid", "sine_high"]


def test_stream_returns_decodable_frames(client):
    response = client.post("/v1/tts/stream", json={"text": TEXT, "voice": "sine_mid"})
    assert response.status_code == 200
    assert response.mimetype == "application/x-kokoro-frames"
    assert response.headers["X-Sample-Rate"] == "24000"
    frames = decode_all(response.data)
    assert frames[-1].frame_type is FrameType.END
    assert all(frame.frame_type is FrameType.AUDIO for frame in frames[:-1])
    assert len(frames) > 2


def test_stream_arrives_as_separate_chunks(client):
    response = client.post("/v1/tts/stream", json={"text": TEXT, "voice": "sine_mid"})
    decoder = FrameDecoder()
    arrivals = [len(decoder.feed(piece)) for piece in response.iter_encoded()]
    assert sum(arrivals) > 2
    assert sum(1 for count in arrivals if count) > 2


def test_stream_audio_matches_wav_endpoint(client):
    body = {"text": TEXT, "voice": "sine_mid"}
    frames = decode_all(client.post("/v1/tts/stream", json=body).data)
    streamed = np.concatenate([frame.samples() for frame in frames[:-1]])
    with wave.open(io.BytesIO(client.post("/v1/tts", json=body).data)) as reader:
        wav_samples = np.frombuffer(reader.readframes(reader.getnframes()), dtype="<i2")
    assert np.array_equal(streamed, wav_samples)


def test_wav_endpoint_headers_and_format(client):
    response = client.post("/v1/tts", json={"text": TEXT, "voice": "sine_mid"})
    assert response.mimetype == "audio/wav"
    with wave.open(io.BytesIO(response.data)) as reader:
        assert reader.getframerate() == 24000
        assert reader.getnchannels() == 1
        assert reader.getsampwidth() == 2
        duration = reader.getnframes() / reader.getframerate()
    assert float(response.headers["X-Audio-Duration"]) == pytest.approx(duration, abs=0.001)


def test_ssml_input(client):
    markup = '<speak>Hello.<break time="300ms"/>World.</speak>'
    frames = decode_all(client.post("/v1/tts/stream", json={"text": markup, "voice": "sine_low"}).data)
    assert frames[-1].frame_type is FrameType.END


def test_missing_text_is_rejected(client):
    response = client.post("/v1/tts/stream", json={"voice": "sine_mid"})
    assert response.status_code == 400
    assert "text" in response.json["error"]


def test_invalid_json_is_rejected(client):
    response = client.post("/v1/tts", data="not json", content_type="application/json")
    assert response.status_code == 400


def test_bad_ssml_is_rejected(client):
    response = client.post("/v1/tts/stream", json={"text": "<speak><p>oops</speak>"})
    assert response.status_code == 400


def test_non_numeric_speed_is_rejected(client):
    response = client.post("/v1/tts", json={"text": "hi", "speed": "fast"})
    assert response.status_code == 400


def test_metrics_reflect_traffic(client):
    client.post("/v1/tts/stream", json={"text": TEXT, "voice": "sine_mid"})
    body = client.get("/metrics").data.decode()
    assert "tts_time_to_first_audio_seconds_count 1.0" in body
    assert "tts_active_streams 0.0" in body
    assert 'tts_requests_total{endpoint="tts_stream",status="200"} 1.0' in body
    assert "tts_chunk_synthesis_seconds_count" in body


def test_unknown_voice_is_rejected(client):
    response = client.post("/v1/tts", json={"text": "hi", "voice": "af_heart"})
    assert response.status_code == 400
    assert "unknown voice" in response.json["error"]


def test_default_voice_falls_back_to_first_available():
    settings = Settings(default_voice="af_heart")
    app = create_app(settings, SineEngine(sample_rate=settings.sample_rate))
    client = app.test_client()
    assert client.get("/v1/voices").json["default"] == "sine_low"
    assert client.post("/v1/tts", json={"text": "Hello there."}).status_code == 200


def test_text_over_limit_is_rejected():
    settings = Settings(default_voice="sine_mid", max_text_chars=50)
    client = create_app(settings, SineEngine()).test_client()
    assert client.post("/v1/tts/stream", json={"text": "x" * 51}).status_code == 400
    assert client.post("/v1/tts/stream", json={"text": "short text"}).status_code == 200


@pytest.mark.parametrize("speed", [0.1, 3, -1])
def test_out_of_range_speed_is_rejected(client, speed):
    response = client.post("/v1/tts", json={"text": "hi", "speed": speed})
    assert response.status_code == 400
    assert "speed" in response.json["error"]


class CountingEngine(SineEngine):
    def __init__(self):
        super().__init__()
        self.calls = 0

    def synthesize(self, text, voice, speed=1.0):
        self.calls += 1
        return super().synthesize(text, voice, speed)


def test_engine_is_warmed_up_before_serving():
    engine = CountingEngine()
    app = create_app(Settings(warmup=True), engine)
    assert engine.calls == 2
    assert "tts_warmup_seconds" in app.test_client().get("/metrics").data.decode()


def test_warmup_can_be_disabled():
    engine = CountingEngine()
    create_app(Settings(warmup=False), engine)
    assert engine.calls == 0


def test_request_id_is_echoed_or_generated(client):
    echoed = client.get("/healthz", headers={"X-Request-ID": "abc-123"})
    assert echoed.headers["X-Request-ID"] == "abc-123"
    generated = client.get("/healthz")
    assert len(generated.headers["X-Request-ID"]) == 12


def test_stream_can_be_resampled(client):
    body = {"text": TEXT, "voice": "sine_mid", "sample_rate": 16000}
    response = client.post("/v1/tts/stream", json=body)
    assert response.headers["X-Sample-Rate"] == "16000"
    frames = decode_all(response.data)
    assert {frame.sample_rate for frame in frames} == {16000}
    native = decode_all(client.post("/v1/tts/stream", json={**body, "sample_rate": 24000}).data)
    resampled_samples = sum(frame.samples().size for frame in frames[:-1])
    native_samples = sum(frame.samples().size for frame in native[:-1])
    assert resampled_samples == pytest.approx(native_samples * 16000 / 24000, rel=0.02)


def test_wav_uses_requested_sample_rate(client):
    response = client.post("/v1/tts", json={"text": TEXT, "voice": "sine_mid", "sample_rate": 8000})
    with wave.open(io.BytesIO(response.data)) as reader:
        assert reader.getframerate() == 8000


@pytest.mark.parametrize("rate", [100, 96000, "fast"])
def test_bad_sample_rate_is_rejected(client, rate):
    response = client.post("/v1/tts", json={"text": "hi", "sample_rate": rate})
    assert response.status_code == 400


def test_repeated_request_hits_the_chunk_cache(client):
    body = {"text": TEXT, "voice": "sine_mid"}
    client.post("/v1/tts", json=body)
    client.post("/v1/tts", json=body)
    metrics = client.get("/metrics").data.decode()
    hits = float(next(line for line in metrics.splitlines() if line.startswith("tts_chunk_cache_hits ")).split()[1])
    assert hits >= 2


def test_cache_can_be_disabled():
    settings = Settings(chunk_cache_mb=0, default_voice="sine_mid")
    client = create_app(settings, SineEngine()).test_client()
    client.post("/v1/tts", json={"text": "Hello there."})
    assert "tts_chunk_cache_hits" not in client.get("/metrics").data.decode()

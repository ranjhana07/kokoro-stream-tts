import math
import threading
import time

import pytest
from werkzeug.serving import make_server

from kokoro_stream.client import StreamResult, stream_speech
from kokoro_stream.config import Settings
from kokoro_stream.engine.sine import SineEngine
from kokoro_stream.loadtest import StreamSample, percentile, run_streams, summarize
from kokoro_stream.service.app import create_app


def test_percentile_matches_known_values():
    values = [10, 20, 30, 40, 50]
    assert percentile(values, 0.5) == 30
    assert percentile(values, 0.0) == 10
    assert percentile(values, 1.0) == 50
    assert percentile(values, 0.95) == pytest.approx(48.0)


def test_percentile_of_empty_is_nan():
    assert math.isnan(percentile([], 0.5))


def test_summarize_ignores_failed_streams():
    samples = [
        StreamSample(0.2, 2.0, 4.0),
        StreamSample(0.4, 3.0, 4.0),
        StreamSample(float("nan"), float("nan"), 0.0, error="boom"),
    ]
    summary = summarize(samples)
    assert summary["streams"] == 3
    assert summary["errors"] == 1
    assert summary["ttfa_p50_ms"] == pytest.approx(300.0)
    assert summary["rtf_mean"] == pytest.approx((0.5 + 0.75) / 2)


def test_run_streams_starts_all_streams_together():
    started = []
    lock = threading.Lock()

    def fake_stream():
        with lock:
            started.append(time.perf_counter())
        time.sleep(0.02)
        return StreamResult(sample_rate=24000, time_to_first_audio=0.1, total_seconds=1.0, sample_count=48000)

    samples = run_streams(fake_stream, 8)
    assert len(samples) == 8
    assert max(started) - min(started) < 0.2
    assert all(sample.audio_seconds == 2.0 for sample in samples)


def test_run_streams_records_errors():
    def failing_stream():
        raise RuntimeError("connection refused")

    samples = run_streams(failing_stream, 3)
    assert [sample.error for sample in samples] == ["connection refused"] * 3


@pytest.fixture
def live_server():
    settings = Settings(first_chunk_chars=40, max_chunk_chars=120, default_voice="sine_mid")
    app = create_app(settings, SineEngine(sample_rate=settings.sample_rate))
    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    thread.join(timeout=5)


def test_client_streams_from_live_server(live_server):
    text = "First sentence is here. Second sentence follows it. Third one closes the text."
    collected = []
    result = stream_speech(live_server, text, "sine_mid", on_audio=lambda samples, rate: collected.append(len(samples)))
    assert result.frame_count == len(collected) >= 2
    assert result.sample_rate == 24000
    assert 0 < result.time_to_first_audio <= result.total_seconds
    assert result.audio_seconds > 1.0


def test_concurrent_streams_against_live_server(live_server):
    text = "One short sentence. And a second one for good measure."
    samples = run_streams(lambda: stream_speech(live_server, text, "sine_mid"), 6)
    assert all(sample.error is None for sample in samples)
    assert summarize(samples)["errors"] == 0


def test_client_sends_api_key():
    settings = Settings(api_keys=("k-123",), default_voice="sine_mid")
    app = create_app(settings, SineEngine(sample_rate=settings.sample_rate))
    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}"
    try:
        with pytest.raises(Exception, match="401"):
            stream_speech(url, "Hello there.", "sine_mid")
        result = stream_speech(url, "Hello there.", "sine_mid", api_key="k-123")
        assert result.frame_count >= 1
    finally:
        server.shutdown()
        thread.join(timeout=5)

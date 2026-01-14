import threading
import time

import pytest
import requests
from werkzeug.serving import make_server

from kokoro_stream.config import Settings
from kokoro_stream.engine.sine import SineEngine
from kokoro_stream.service.app import create_app

LONG_TEXT = " ".join(f"This is sentence number {index} in a long request." for index in range(40))


@pytest.fixture
def server():
    settings = Settings(
        first_chunk_chars=40,
        max_chunk_chars=100,
        default_voice="sine_mid",
        prefetch_depth=2,
        max_streams=2,
        warmup=False,
        chunk_cache_mb=0,
    )
    app = create_app(settings, SineEngine(latency_per_char=0.002))
    http_server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = threading.Thread(target=http_server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{http_server.server_port}", app
    http_server.shutdown()
    thread.join(timeout=5)


def wait_until(predicate, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


def test_abandoned_stream_releases_its_slot(server):
    url, app = server
    metrics = app.extensions["metrics"]
    response = requests.post(f"{url}/v1/tts/stream", json={"text": LONG_TEXT}, stream=True, timeout=10)
    next(response.iter_content(chunk_size=None))
    assert wait_until(lambda: metrics.active_streams._value.get() == 1)
    response.close()
    assert wait_until(lambda: metrics.active_streams._value.get() == 0)
    for _ in range(4):
        reply = requests.post(f"{url}/v1/tts/stream", json={"text": "Short one."}, timeout=10)
        assert reply.status_code == 200


def test_abandoned_streams_stop_synthesizing(server):
    url, app = server
    synthesizer = app.extensions["synthesizer"]
    observed = []
    original = synthesizer.engine.synthesize

    def counting(text, voice, speed=1.0):
        observed.append(text)
        return original(text, voice, speed)

    synthesizer.engine.synthesize = counting
    response = requests.post(f"{url}/v1/tts/stream", json={"text": LONG_TEXT}, stream=True, timeout=10)
    next(response.iter_content(chunk_size=None))
    response.close()
    time.sleep(1.0)
    settled = len(observed)
    time.sleep(0.5)
    assert len(observed) == settled
    assert settled < 25

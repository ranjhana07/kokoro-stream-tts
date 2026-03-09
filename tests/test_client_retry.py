import threading

import pytest
from werkzeug.serving import make_server

from kokoro_stream.client import StreamError, retry_delay, stream_speech
from kokoro_stream.config import Settings
from kokoro_stream.engine.sine import SineEngine
from kokoro_stream.service.app import create_app


class FakeResponse:
    def __init__(self, headers):
        self.headers = headers


def test_retry_after_header_is_used_and_capped():
    assert retry_delay(FakeResponse({"Retry-After": "2"}), 0) == 2.0
    assert retry_delay(FakeResponse({"Retry-After": "120"}), 0) == 5.0


def test_missing_header_falls_back_to_exponential_backoff():
    assert retry_delay(FakeResponse({}), 0) == 0.25
    assert retry_delay(FakeResponse({}), 3) == 2.0
    assert retry_delay(FakeResponse({"Retry-After": "soon"}), 1) == 0.5


@pytest.fixture
def full_service():
    settings = Settings(max_streams=1, default_voice="sine_mid", warmup=False)
    app = create_app(settings, SineEngine(latency_per_char=0.003))
    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    thread.join(timeout=5)


LONG_TEXT = " ".join(f"Sentence number {index} fills the only slot." for index in range(6))


def test_client_gives_up_without_retries_when_the_service_is_full(full_service):
    outcome = {}

    def occupy():
        outcome["result"] = stream_speech(full_service, LONG_TEXT, "sine_mid")

    holder = threading.Thread(target=occupy)
    holder.start()
    import time

    time.sleep(0.15)
    with pytest.raises(StreamError, match="429"):
        stream_speech(full_service, "Short text.", "sine_mid")
    holder.join()


def test_client_retries_until_a_slot_frees_up(full_service):
    holder = threading.Thread(target=lambda: stream_speech(full_service, LONG_TEXT, "sine_mid"))
    holder.start()
    import time

    time.sleep(0.15)
    result = stream_speech(full_service, "Short text.", "sine_mid", retries=8)
    assert result.frame_count >= 1
    holder.join()


def test_play_without_sounddevice_fails_cleanly(monkeypatch, capsys):
    import builtins

    from kokoro_stream.client import main

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "sounddevice":
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert main(["--text", "hello", "--play"]) == 1
    assert "sounddevice" in capsys.readouterr().err


def test_cli_writes_a_wav_file(full_service, tmp_path, capsys):
    import wave

    from kokoro_stream.client import main

    output = tmp_path / "out.wav"
    assert main(["--url", full_service, "--text", "A short line to write.", "--voice", "sine_mid", "--out", str(output)]) == 0
    with wave.open(str(output)) as reader:
        assert reader.getframerate() == 24000
        assert reader.getnframes() > 0
    assert "ttfa=" in capsys.readouterr().out

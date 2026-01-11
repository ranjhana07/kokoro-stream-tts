import pytest

from kokoro_stream.config import Settings
from kokoro_stream.engine.sine import SineEngine
from kokoro_stream.service.app import create_app
from kokoro_stream.service.auth import extract_token, is_authorized


def test_extract_token_prefers_bearer():
    assert extract_token({"Authorization": "Bearer abc"}) == "abc"
    assert extract_token({"Authorization": "bearer  abc "}) == "abc"
    assert extract_token({"X-API-Key": "xyz"}) == "xyz"
    assert extract_token({"Authorization": "Basic abc"}) == ""
    assert extract_token({}) == ""


def test_is_authorized():
    assert is_authorized("k2", ["k1", "k2"])
    assert not is_authorized("k3", ["k1", "k2"])
    assert not is_authorized("", ["k1"])


@pytest.fixture
def client():
    settings = Settings(api_keys=("secret-one", "secret-two"), default_voice="sine_mid")
    return create_app(settings, SineEngine()).test_client()


def test_protected_endpoints_need_a_key(client):
    for path in ("/v1/voices",):
        assert client.get(path).status_code == 401
    assert client.post("/v1/tts", json={"text": "hi"}).status_code == 401
    assert client.post("/v1/tts/stream", json={"text": "hi"}).status_code == 401
    assert client.get("/v1/voices").headers["WWW-Authenticate"] == "Bearer"


def test_valid_keys_are_accepted(client):
    assert client.get("/v1/voices", headers={"Authorization": "Bearer secret-two"}).status_code == 200
    assert client.get("/v1/voices", headers={"X-API-Key": "secret-one"}).status_code == 200
    assert client.get("/v1/voices", headers={"Authorization": "Bearer nope"}).status_code == 401


def test_health_and_metrics_stay_open(client):
    assert client.get("/healthz").status_code == 200
    assert client.get("/metrics").status_code == 200


def test_no_keys_configured_means_open_access():
    client = create_app(Settings(default_voice="sine_mid"), SineEngine()).test_client()
    assert client.get("/v1/voices").status_code == 200

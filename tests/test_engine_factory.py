import json

import pytest

from kokoro_stream.config import Settings
from kokoro_stream.engine.base import EngineError
from kokoro_stream.engine.factory import build_engine
from kokoro_stream.engine.kokoro import load_vocab, select_providers
from kokoro_stream.engine.sine import SineEngine


def test_factory_builds_sine_engine():
    engine = build_engine(Settings(engine="sine", sample_rate=16000))
    assert isinstance(engine, SineEngine)
    assert engine.sample_rate == 16000


def test_factory_rejects_unknown_engine():
    with pytest.raises(EngineError):
        build_engine(Settings(engine="mystery"))


def test_select_providers_keeps_requested_order_and_adds_cpu():
    available = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    assert select_providers(["CUDAExecutionProvider"], available) == [
        "CUDAExecutionProvider",
        "CPUExecutionProvider",
    ]


def test_select_providers_drops_unavailable():
    assert select_providers(["CoreMLExecutionProvider"], ["CPUExecutionProvider"]) == [
        "CPUExecutionProvider"
    ]


def test_load_vocab(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"vocab": {"a": 43, "ˈ": 156}}), encoding="utf-8")
    assert load_vocab(path) == {"a": 43, "ˈ": 156}


def test_load_vocab_requires_vocab_key(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(EngineError):
        load_vocab(path)

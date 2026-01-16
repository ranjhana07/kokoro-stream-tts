import threading
import time

import pytest

from kokoro_stream.engine.base import EngineError
from kokoro_stream.engine.phonemize import EspeakPhonemizer, MisakiPhonemizer, build_phonemizer


class GuardedBackend:
    def __init__(self):
        self.inside = 0
        self.overlaps = 0
        self.guard = threading.Lock()

    def phonemize(self, texts):
        with self.guard:
            self.inside += 1
            if self.inside > 1:
                self.overlaps += 1
        time.sleep(0.005)
        with self.guard:
            self.inside -= 1
        return ["  həlˈoʊ   wˈɝːld "]


def make_espeak(backend):
    phonemizer = EspeakPhonemizer.__new__(EspeakPhonemizer)
    phonemizer._backend = backend
    phonemizer._lock = threading.Lock()
    return phonemizer


def test_espeak_output_is_whitespace_normalized():
    assert make_espeak(GuardedBackend()).phonemize("hello world") == "həlˈoʊ wˈɝːld"


def test_espeak_backend_is_never_entered_concurrently():
    backend = GuardedBackend()
    phonemizer = make_espeak(backend)
    threads = [threading.Thread(target=lambda: [phonemizer.phonemize("hi") for _ in range(10)]) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert backend.overlaps == 0


def test_unknown_preference_is_rejected():
    with pytest.raises(EngineError):
        build_phonemizer("festival")


def test_missing_misaki_raises_engine_error(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "misaki":
            raise ImportError("no misaki")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(EngineError):
        MisakiPhonemizer()

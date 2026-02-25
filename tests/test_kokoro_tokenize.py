import threading
from collections import OrderedDict

from kokoro_stream.engine import kokoro
from kokoro_stream.engine.kokoro import KokoroEngine


class CountingPhonemizer:
    def __init__(self):
        self.calls = 0

    def phonemize(self, text):
        self.calls += 1
        return "ab c?"


def make_engine(phonemizer):
    engine = KokoroEngine.__new__(KokoroEngine)
    engine._phonemizer = phonemizer
    engine._vocab = {"a": 1, "b": 2, " ": 16, "c": 3}
    engine._token_cache = OrderedDict()
    engine._token_lock = threading.Lock()
    return engine


def test_tokens_use_the_vocabulary_and_skip_unknown_symbols():
    assert make_engine(CountingPhonemizer()).tokenize("anything") == [1, 2, 16, 3]


def test_repeated_text_is_phonemized_once():
    phonemizer = CountingPhonemizer()
    engine = make_engine(phonemizer)
    first = engine.tokenize("same text")
    second = engine.tokenize("same text")
    assert first == second
    assert phonemizer.calls == 1


def test_cached_tokens_cannot_be_mutated_by_callers():
    engine = make_engine(CountingPhonemizer())
    engine.tokenize("x").append(99)
    assert engine.tokenize("x") == [1, 2, 16, 3]


def test_cache_is_bounded(monkeypatch):
    monkeypatch.setattr(kokoro, "TOKEN_CACHE_SIZE", 3)
    engine = make_engine(CountingPhonemizer())
    for index in range(10):
        engine.tokenize(f"text {index}")
    assert len(engine._token_cache) == 3
    assert "text 9" in engine._token_cache


def test_tokens_are_truncated_to_the_model_limit(monkeypatch):
    monkeypatch.setattr(kokoro, "MAX_TOKENS", 2)
    assert make_engine(CountingPhonemizer()).tokenize("long") == [1, 2]

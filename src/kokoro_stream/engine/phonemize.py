from __future__ import annotations

import re
import threading
from typing import Protocol

from kokoro_stream.engine.base import EngineError

WHITESPACE = re.compile(r"\s+")


class Phonemizer(Protocol):
    def phonemize(self, text: str) -> str: ...


class MisakiPhonemizer:
    def __init__(self, british: bool = False) -> None:
        try:
            from misaki import en, espeak
        except ImportError as error:
            raise EngineError("misaki is not installed") from error
        fallback = espeak.EspeakFallback(british=british)
        self._g2p = en.G2P(trf=False, british=british, fallback=fallback)
        self._lock = threading.Lock()

    def phonemize(self, text: str) -> str:
        with self._lock:
            phonemes, _ = self._g2p(text)
        return WHITESPACE.sub(" ", phonemes).strip()


class EspeakPhonemizer:
    def __init__(self, language: str = "en-us") -> None:
        try:
            from phonemizer.backend import EspeakBackend
        except ImportError as error:
            raise EngineError("phonemizer is not installed") from error
        self._configure_library()
        self._lock = threading.Lock()
        self._backend = EspeakBackend(
            language, preserve_punctuation=True, with_stress=True, language_switch="remove-flags"
        )

    @staticmethod
    def _configure_library() -> None:
        try:
            import espeakng_loader
            from phonemizer.backend.espeak.wrapper import EspeakWrapper
        except ImportError:
            return
        EspeakWrapper.set_library(espeakng_loader.get_library_path())
        EspeakWrapper.set_data_path(espeakng_loader.get_data_path())

    def phonemize(self, text: str) -> str:
        with self._lock:
            phonemes = self._backend.phonemize([text.strip()])[0]
        return WHITESPACE.sub(" ", phonemes).strip()


def build_phonemizer(preference: str = "auto") -> Phonemizer:
    preference = preference.lower()
    if preference == "misaki":
        return MisakiPhonemizer()
    if preference == "espeak":
        return EspeakPhonemizer()
    if preference != "auto":
        raise EngineError(f"unknown phonemizer: {preference}")
    failures: list[str] = []
    for factory in (MisakiPhonemizer, EspeakPhonemizer):
        try:
            return factory()
        except Exception as error:
            failures.append(f"{factory.__name__}: {error}")
    raise EngineError("no phonemizer available (" + "; ".join(failures) + ")")

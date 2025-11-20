from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

import numpy as np

from kokoro_stream.engine.base import EngineError
from kokoro_stream.engine.phonemize import Phonemizer, build_phonemizer

MAX_TOKENS = 510
SAMPLE_RATE = 24000


def select_providers(requested: Sequence[str], available: Sequence[str]) -> list[str]:
    chosen = [name for name in requested if name in available]
    if "CPUExecutionProvider" not in chosen:
        chosen.append("CPUExecutionProvider")
    return chosen


def load_vocab(path: Path) -> dict[str, int]:
    with path.open(encoding="utf-8") as handle:
        config = json.load(handle)
    vocab = config.get("vocab")
    if not isinstance(vocab, dict) or not vocab:
        raise EngineError(f"no vocab found in {path}")
    return {symbol: int(index) for symbol, index in vocab.items()}


class KokoroEngine:
    sample_rate = SAMPLE_RATE

    def __init__(
        self,
        model_path: str,
        voices_path: str,
        vocab_path: str,
        providers: Sequence[str] = ("CPUExecutionProvider",),
        intra_op_threads: int = 2,
        phonemizer: Phonemizer | None = None,
        phonemizer_preference: str = "auto",
    ) -> None:
        try:
            import onnxruntime
        except ImportError as error:
            raise EngineError("onnxruntime is not installed") from error
        for label, path in (("model", model_path), ("voices", voices_path), ("vocab", vocab_path)):
            if not Path(path).is_file():
                raise EngineError(f"{label} file not found: {path}")
        options = onnxruntime.SessionOptions()
        options.intra_op_num_threads = intra_op_threads
        options.inter_op_num_threads = 1
        options.execution_mode = onnxruntime.ExecutionMode.ORT_SEQUENTIAL
        options.graph_optimization_level = onnxruntime.GraphOptimizationLevel.ORT_ENABLE_ALL
        self.providers = select_providers(providers, onnxruntime.get_available_providers())
        self._session = onnxruntime.InferenceSession(
            model_path, sess_options=options, providers=self.providers
        )
        input_names = {entry.name for entry in self._session.get_inputs()}
        self._token_input = "tokens" if "tokens" in input_names else "input_ids"
        with np.load(voices_path) as archive:
            self._voices = {name: archive[name] for name in archive.files}
        self._vocab = load_vocab(Path(vocab_path))
        self._phonemizer = phonemizer or build_phonemizer(phonemizer_preference)

    def voices(self) -> list[str]:
        return sorted(self._voices)

    def tokenize(self, text: str) -> list[int]:
        phonemes = self._phonemizer.phonemize(text)
        tokens = [self._vocab[symbol] for symbol in phonemes if symbol in self._vocab]
        return tokens[:MAX_TOKENS]

    def synthesize(self, text: str, voice: str, speed: float = 1.0) -> np.ndarray:
        if voice not in self._voices:
            raise EngineError(f"unknown voice: {voice}")
        tokens = self.tokenize(text)
        if not tokens:
            return np.zeros(0, dtype=np.float32)
        style = self._voices[voice][len(tokens)].astype(np.float32)
        inputs = {
            self._token_input: np.array([[0, *tokens, 0]], dtype=np.int64),
            "style": style.reshape(1, -1),
            "speed": np.array([speed], dtype=np.float32),
        }
        audio = self._session.run(None, inputs)[0]
        return np.asarray(audio, dtype=np.float32).reshape(-1)

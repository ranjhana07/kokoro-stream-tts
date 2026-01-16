import pytest

from kokoro_stream.config import Settings


def test_defaults_are_valid():
    assert Settings().validate() is not None
    assert Settings.from_env({}).prefetch_depth == 3


def test_environment_overrides():
    settings = Settings.from_env(
        {
            "KOKORO_ENGINE": "kokoro",
            "KOKORO_PROVIDERS": "CUDAExecutionProvider, CPUExecutionProvider",
            "PREFETCH_DEPTH": "5",
            "CROSSFADE_MS": "40",
            "WARMUP": "0",
        }
    )
    assert settings.engine == "kokoro"
    assert settings.providers == ("CUDAExecutionProvider", "CPUExecutionProvider")
    assert settings.prefetch_depth == 5
    assert settings.crossfade_ms == 40
    assert settings.warmup is False


def test_blank_values_fall_back_to_defaults():
    assert Settings.from_env({"PREFETCH_DEPTH": "  "}).prefetch_depth == 3


@pytest.mark.parametrize(
    "environ",
    [
        {"KOKORO_ENGINE": "mystery"},
        {"PREFETCH_DEPTH": "0"},
        {"CROSSFADE_MS": "-1"},
        {"FIRST_CHUNK_CHARS": "500", "MAX_CHUNK_CHARS": "100"},
        {"SAMPLE_RATE": "0"},
    ],
)
def test_invalid_values_are_rejected(environ):
    with pytest.raises(ValueError):
        Settings.from_env(environ)


def test_non_numeric_value_raises():
    with pytest.raises(ValueError):
        Settings.from_env({"PREFETCH_DEPTH": "many"})


def test_phonemizer_choice_is_validated():
    assert Settings.from_env({"KOKORO_PHONEMIZER": "espeak"}).phonemizer == "espeak"
    with pytest.raises(ValueError):
        Settings.from_env({"KOKORO_PHONEMIZER": "festival"})

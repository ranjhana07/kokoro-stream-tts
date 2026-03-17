import pytest

from kokoro_stream.engine.voice_info import describe_voice


@pytest.mark.parametrize(
    "name, language, gender",
    [
        ("af_heart", "en-US", "female"),
        ("am_adam", "en-US", "male"),
        ("bf_emma", "en-GB", "female"),
        ("bm_george", "en-GB", "male"),
        ("jf_alpha", "ja", "female"),
        ("zm_yunxi", "zh", "male"),
    ],
)
def test_kokoro_voice_names_are_decoded(name, language, gender):
    assert describe_voice(name) == {"name": name, "language": language, "gender": gender}


@pytest.mark.parametrize("name", ["sine_mid", "custom", "xx_unknown", "af_"])
def test_other_names_only_report_the_name(name):
    assert describe_voice(name) == {"name": name}

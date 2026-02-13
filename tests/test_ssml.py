import pytest

from kokoro_stream.text.ssml import (
    PauseSegment,
    SpeechSegment,
    SSMLError,
    is_ssml,
    parse_ssml,
    parse_time,
)


def texts(segments):
    return [segment.text for segment in segments if isinstance(segment, SpeechSegment)]


def test_plain_text_is_one_segment():
    assert parse_ssml("I owe you 5 dollars") == [SpeechSegment("I owe you five dollars")]


def test_is_ssml_detection():
    assert is_ssml("  <speak>hi</speak>")
    assert not is_ssml("a < b")


def test_sentence_and_paragraph_pauses():
    segments = parse_ssml("<speak><p><s>One.</s><s>Two.</s></p><p>Three.</p></speak>")
    assert segments == [
        SpeechSegment("One."),
        PauseSegment(250),
        SpeechSegment("Two."),
        PauseSegment(600),
        SpeechSegment("Three."),
    ]


def test_trailing_pause_is_dropped():
    assert parse_ssml("<speak>Hello<break time='1s'/></speak>") == [SpeechSegment("Hello")]


@pytest.mark.parametrize(
    "value, expected",
    [("500ms", 500), ("1.5s", 1500), ("2", 2000), ("20000ms", 10000)],
)
def test_parse_time(value, expected):
    assert parse_time(value) == expected


def test_parse_time_rejects_garbage():
    with pytest.raises(SSMLError):
        parse_time("soon")


def test_break_strength():
    segments = parse_ssml('<speak>a<break strength="strong"/>b</speak>')
    assert segments == [SpeechSegment("a"), PauseSegment(700), SpeechSegment("b")]


def test_break_defaults_to_medium():
    segments = parse_ssml("<speak>a<break/>b</speak>")
    assert segments[1] == PauseSegment(400)


def test_unknown_strength_raises():
    with pytest.raises(SSMLError):
        parse_ssml('<speak>a<break strength="huge"/>b</speak>')


def test_prosody_rate_keyword_and_percent():
    segments = parse_ssml(
        '<speak>a <prosody rate="slow">b</prosody> <prosody rate="+20%">c</prosody></speak>'
    )
    assert [(segment.text, segment.speed) for segment in segments] == [
        ("a", 1.0),
        ("b", 0.75),
        ("c", pytest.approx(1.2)),
    ]


def test_nested_prosody_multiplies_and_clamps():
    segments = parse_ssml(
        '<speak><prosody rate="x-fast"><prosody rate="x-fast">hi</prosody></prosody></speak>'
    )
    assert segments[0].speed == 2.0


def test_emphasis_slows_speech():
    segment = parse_ssml('<speak><emphasis level="strong">now</emphasis></speak>')[0]
    assert segment.speed < 1.0


def test_sub_uses_alias():
    segments = parse_ssml('<speak><sub alias="World Health Organization">WHO</sub></speak>')
    assert texts(segments) == ["World Health Organization"]


def test_say_as_variants():
    markup = (
        "<speak>"
        '<say-as interpret-as="cardinal">1,204</say-as> '
        '<say-as interpret-as="ordinal">3</say-as> '
        '<say-as interpret-as="digits">2057</say-as>'
        "</speak>"
    )
    assert texts(parse_ssml(markup)) == [
        "one thousand two hundred four third two zero five seven"
    ]


def test_say_as_date_and_telephone():
    markup = (
        '<speak><say-as interpret-as="date" format="dmy">05/06/2024</say-as>. '
        '<say-as interpret-as="telephone">555-0142</say-as></speak>'
    )
    assert texts(parse_ssml(markup)) == [
        "fifth June twenty twenty four. five five five, oh one four two"
    ]


def test_say_as_currency():
    markup = '<speak><say-as interpret-as="currency">$12.50</say-as></speak>'
    assert texts(parse_ssml(markup)) == ["twelve dollars and fifty cents"]


def test_say_as_requires_interpret_as():
    with pytest.raises(SSMLError):
        parse_ssml("<speak><say-as>3</say-as></speak>")


def test_say_as_bad_value():
    with pytest.raises(SSMLError):
        parse_ssml('<speak><say-as interpret-as="cardinal">abc</say-as></speak>')


def test_malformed_markup():
    with pytest.raises(SSMLError):
        parse_ssml("<speak><p>unclosed</speak>")


def test_text_is_normalized_around_elements():
    segments = parse_ssml("<speak>It is 3:30 pm <break time='1s'/> see you.</speak>")
    assert texts(segments) == ["It is three thirty p m", "see you."]


def test_blank_lines_in_plain_text_become_paragraph_pauses():
    segments = parse_ssml("First paragraph.\n\nSecond paragraph.\n   \nThird.")
    assert segments == [
        SpeechSegment("First paragraph."),
        PauseSegment(600),
        SpeechSegment("Second paragraph."),
        PauseSegment(600),
        SpeechSegment("Third."),
    ]


def test_single_newlines_stay_inside_one_segment():
    assert parse_ssml("line one\nline two") == [SpeechSegment("line one line two")]


def test_voice_element_sets_voice_for_its_content():
    segments = parse_ssml('<speak>Hello. <voice name="am_adam">Switched.</voice> Back again.</speak>')
    assert [(segment.text, segment.voice) for segment in segments] == [
        ("Hello.", None),
        ("Switched.", "am_adam"),
        ("Back again.", None),
    ]


def test_nested_voice_uses_innermost_name():
    segments = parse_ssml('<speak><voice name="a">x <voice name="b">y</voice> z</voice></speak>')
    assert [segment.voice for segment in segments] == ["a", "b", "a"]


def test_voice_without_name_is_an_error():
    with pytest.raises(SSMLError):
        parse_ssml("<speak><voice>oops</voice></speak>")


def test_prosody_inside_voice_keeps_both():
    segment = parse_ssml('<speak><voice name="a"><prosody rate="slow">hi</prosody></voice></speak>')[0]
    assert (segment.voice, segment.speed) == ("a", 0.75)


def test_phoneme_becomes_inline_pronunciation_markup():
    markup = '<speak>Say <phoneme alphabet="ipa" ph="təmeɪɾoʊ">tomato</phoneme> twice.</speak>'
    assert texts(parse_ssml(markup)) == ["Say [tomato](/təmeɪɾoʊ/) twice."]


def test_phoneme_defaults_to_ipa():
    assert texts(parse_ssml('<speak><phoneme ph="kət">cat</phoneme></speak>')) == ["[cat](/kət/)"]


@pytest.mark.parametrize(
    "markup",
    [
        '<speak><phoneme alphabet="x-sampa" ph="kQt">cat</phoneme></speak>',
        "<speak><phoneme>cat</phoneme></speak>",
        '<speak><phoneme ph="a/b">cat</phoneme></speak>',
        '<speak><phoneme ph="a)b">cat</phoneme></speak>',
    ],
)
def test_bad_phoneme_elements_are_rejected(markup):
    with pytest.raises(SSMLError):
        parse_ssml(markup)

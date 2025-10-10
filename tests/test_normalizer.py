import pytest

from kokoro_stream.text.normalizer import normalize_text


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("I have 3 cats", "I have three cats"),
        ("about 1,250 people", "about one thousand two hundred fifty people"),
        ("pi is 3.14", "pi is three point one four"),
        ("it was -4 outside", "it was minus four outside"),
        ("room 007", "room oh oh seven"),
        ("It costs $5.", "It costs five dollars."),
        ("only $1", "only one dollar"),
        ("a $12.50 fee", "a twelve dollars and fifty cents fee"),
        ("$0.99 each", "ninety nine cents each"),
        ("worth $2.5 million", "worth two point five million dollars"),
        ("£3.01", "three pounds and one penny"),
        ("₹250", "two hundred fifty rupees"),
        ("up 12%", "up twelve percent"),
        ("down 0.5%", "down zero point five percent"),
        ("grew 7 %", "grew seven percent"),
    ],
)
def test_normalize(raw, expected):
    assert normalize_text(raw) == expected

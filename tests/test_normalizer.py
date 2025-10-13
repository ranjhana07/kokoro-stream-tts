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
def test_numbers_and_money(raw, expected):
    assert normalize_text(raw) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Dr. Smith met Mrs. Jones", "Doctor Smith met Missus Jones"),
        ("fruit, e.g. apples", "fruit, for example apples"),
        ("apples, pears, etc. Next", "apples, pears, et cetera. Next"),
        ("salt & pepper", "salt and pepper"),
        ("ticket #42", "ticket number forty two"),
    ],
)
def test_abbreviations_and_symbols(raw, expected):
    assert normalize_text(raw) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("meet at 3:45 pm", "meet at three forty five p m"),
        ("at 9 a.m. sharp", "at nine a m sharp"),
        ("until 5 p.m.", "until five p m."),
        ("at 10:05 PM", "at ten oh five p m"),
        ("train at 14:30", "train at fourteen thirty"),
        ("at 14:00", "at fourteen hundred"),
        ("at 7:00", "at seven o'clock"),
    ],
)
def test_times(raw, expected):
    assert normalize_text(raw) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("the 1st and 22nd", "the first and twenty second"),
        ("on March 5, 2024", "on March fifth twenty twenty four"),
        ("2024-06-05", "June fifth twenty twenty four"),
        ("back in 1999", "back in nineteen ninety nine"),
        ("music of the 1990s", "music of the nineteen nineties"),
        ("pages 10-15", "pages ten to fifteen"),
        ("2020-2021 season", "twenty twenty to twenty twenty one season"),
    ],
)
def test_ordinals_dates_and_years(raw, expected):
    assert normalize_text(raw) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("5 km", "five kilometers"),
        ("1 kg of rice", "one kilogram of rice"),
        ("2.5GB", "two point five gigabytes"),
        ("it is 21°C", "it is twenty one degrees celsius"),
        ("60 km/h", "sixty kilometers per hour"),
        ("5 more", "five more"),
    ],
)
def test_units(raw, expected):
    assert normalize_text(raw) == expected

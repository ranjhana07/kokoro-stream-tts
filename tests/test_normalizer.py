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


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Version 2.0.1 is out", "Version two point zero point one is out"),
        ("release 10.4.12.", "release ten point four point twelve."),
        ("He ran 5k and 10K.", "He ran five thousand and ten thousand."),
        ("pi is 3.14.", "pi is three point one four."),
    ],
)
def test_versions_and_thousands(raw, expected):
    assert normalize_text(raw) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("1/2 cup", "one half cup"),
        ("3/4 mile", "three quarters mile"),
        ("2/3 done", "two thirds done"),
        ("1/8 inch", "one eighth inch"),
        ("24/7 support", "twenty four seven support"),
        ("a/b stays", "a/b stays"),
        ("on 5/6/2024", "on May sixth twenty twenty four"),
        ("Call (415) 555-0142.", "Call four one five, five five five, oh one four two."),
        ("Call 1-800-555-0199 now", "Call one, eight oh oh, five five five, oh one nine nine now"),
    ],
)
def test_fractions_dates_and_phone_numbers(raw, expected):
    assert normalize_text(raw) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("raised $5m", "raised five million dollars"),
        ("a $2.5bn deal", "a two point five billion dollars deal"),
        ("fees of $300k.", "fees of three hundred thousand dollars."),
        ("worth €3 million", "worth three million euros"),
        ("only $5 more", "only five dollars more"),
        ("$12.50 each", "twelve dollars and fifty cents each"),
        ("$7 mattered", "seven dollars mattered"),
    ],
)
def test_currency_magnitude_suffixes(raw, expected):
    assert normalize_text(raw) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("see Chapter IV for details", "see Chapter four for details"),
        ("Part XII", "Part twelve"),
        ("Henry VIII ruled", "Henry the eighth ruled"),
        ("during World War II.", "during World War two."),
        ("Pope Benedict XVI", "Pope Benedict the sixteenth"),
        ("Section IIII is invalid", "Section IIII is invalid"),
        ("I think so", "I think so"),
        ("Chapter 7", "Chapter seven"),
    ],
)
def test_roman_numerals(raw, expected):
    assert normalize_text(raw) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Really?!?!", "Really?"),
        ("Stop!!!", "Stop!"),
        ("temperature +5 today", "temperature plus five today"),
        ("it went from -3 to +4", "it went from minus three to plus four"),
        ("C++ is fine", "C++ is fine"),
        ("Wait... what", "Wait... what"),
    ],
)
def test_punctuation_runs_and_plus_signs(raw, expected):
    assert normalize_text(raw) == expected

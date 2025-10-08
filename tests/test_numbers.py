import pytest

from kokoro_stream.text.numbers import cardinal, ordinal


@pytest.mark.parametrize(
    "value, expected",
    [
        (0, "zero"),
        (7, "seven"),
        (13, "thirteen"),
        (21, "twenty one"),
        (100, "one hundred"),
        (342, "three hundred forty two"),
        (1000, "one thousand"),
        (12045, "twelve thousand forty five"),
        (1000000, "one million"),
        (-8, "minus eight"),
    ],
)
def test_cardinal(value, expected):
    assert cardinal(value) == expected


@pytest.mark.parametrize(
    "value, expected",
    [
        (1, "first"),
        (2, "second"),
        (3, "third"),
        (4, "fourth"),
        (12, "twelfth"),
        (20, "twentieth"),
        (21, "twenty first"),
        (100, "one hundredth"),
        (1002, "one thousand second"),
    ],
)
def test_ordinal(value, expected):
    assert ordinal(value) == expected


from kokoro_stream.text.numbers import decimal, digits, year


def test_digits_reads_zero_as_oh():
    assert digits("2057") == "two oh five seven"


def test_digits_skips_separators():
    assert digits("555-0142") == "five five five oh one four two"


def test_decimal():
    assert decimal("3.14") == "three point one four"
    assert decimal("0.5") == "zero point five"
    assert decimal(".25") == "zero point two five"


@pytest.mark.parametrize(
    "value, expected",
    [
        (1999, "nineteen ninety nine"),
        (1905, "nineteen oh five"),
        (2000, "two thousand"),
        (2007, "two thousand seven"),
        (2024, "twenty twenty four"),
        (1900, "nineteen hundred"),
    ],
)
def test_year(value, expected):
    assert year(value) == expected

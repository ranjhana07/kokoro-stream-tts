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

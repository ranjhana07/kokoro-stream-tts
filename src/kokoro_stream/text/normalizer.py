from __future__ import annotations

import re
from typing import Callable

from kokoro_stream.text import numbers

CURRENCIES = {
    "$": ("dollar", "dollars", "cent", "cents"),
    "€": ("euro", "euros", "cent", "cents"),
    "£": ("pound", "pounds", "penny", "pence"),
    "₹": ("rupee", "rupees", "paisa", "paise"),
}

CURRENCY_PATTERN = re.compile(
    r"([$€£₹])\s?(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?(?:\s(thousand|million|billion|trillion))?(?![\w])"
)
PERCENT_PATTERN = re.compile(r"(?<![\w.])(-?\d{1,3}(?:,\d{3})+|-?\d+)(?:\.(\d+))?\s?%")
DECIMAL_PATTERN = re.compile(r"(?<![\w.])(-?)(\d+)\.(\d+)(?![\w])")
INTEGER_PATTERN = re.compile(r"(?<![\w.])(-?)(\d{1,3}(?:,\d{3})+|\d+)(?![\w])")
SPACES_PATTERN = re.compile(r"[ \t]+")


def say_integer(text: str) -> str:
    cleaned = text.replace(",", "")
    if len(cleaned) > 1 and cleaned.startswith("0"):
        return numbers.digits(cleaned)
    if len(cleaned) > 18:
        return numbers.digits(cleaned)
    return numbers.cardinal(int(cleaned))


def say_decimal(whole: str, fraction: str) -> str:
    return f"{say_integer(whole)} point {numbers.digits_plain(fraction)}"


def expand_currency(match: re.Match[str]) -> str:
    symbol, whole_text, fraction_text, magnitude = match.groups()
    singular, plural, minor_singular, minor_plural = CURRENCIES[symbol]
    if magnitude:
        amount = say_decimal(whole_text, fraction_text) if fraction_text else say_integer(whole_text)
        return f"{amount} {magnitude} {plural}"
    whole = int(whole_text.replace(",", ""))
    cents = int(fraction_text[:2].ljust(2, "0")) if fraction_text else 0
    spoken: list[str] = []
    if whole or not cents:
        spoken.append(f"{say_integer(whole_text)} {singular if whole == 1 else plural}")
    if cents:
        spoken.append(f"{numbers.cardinal(cents)} {minor_singular if cents == 1 else minor_plural}")
    return " and ".join(spoken)


def expand_percent(match: re.Match[str]) -> str:
    whole_text, fraction_text = match.groups()
    negative = whole_text.startswith("-")
    whole_text = whole_text.lstrip("-")
    amount = say_decimal(whole_text, fraction_text) if fraction_text else say_integer(whole_text)
    return f"{'minus ' if negative else ''}{amount} percent"


def expand_decimal(match: re.Match[str]) -> str:
    sign, whole, fraction = match.groups()
    return f"{'minus ' if sign else ''}{say_decimal(whole, fraction)}"


def expand_integer(match: re.Match[str]) -> str:
    sign, text = match.groups()
    return f"{'minus ' if sign else ''}{say_integer(text)}"


PASSES: tuple[Callable[[str], str], ...] = (
    lambda text: CURRENCY_PATTERN.sub(expand_currency, text),
    lambda text: PERCENT_PATTERN.sub(expand_percent, text),
    lambda text: DECIMAL_PATTERN.sub(expand_decimal, text),
    lambda text: INTEGER_PATTERN.sub(expand_integer, text),
)


def normalize_text(text: str) -> str:
    for apply_pass in PASSES:
        text = apply_pass(text)
    return SPACES_PATTERN.sub(" ", text).strip()

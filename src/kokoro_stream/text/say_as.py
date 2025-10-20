from __future__ import annotations

import re

from kokoro_stream.text import numbers
from kokoro_stream.text.normalizer import MONTHS, normalize_text, say_integer

CURRENCY_CODES = {"USD": "$", "EUR": "€", "GBP": "£", "INR": "₹"}
DATE_FIELDS = {
    "mdy": ("month", "day", "year"),
    "dmy": ("day", "month", "year"),
    "ymd": ("year", "month", "day"),
    "ym": ("year", "month"),
    "my": ("month", "year"),
    "md": ("month", "day"),
    "dm": ("day", "month"),
    "y": ("year",),
    "m": ("month",),
    "d": ("day",),
}
NUMBER_PATTERN = re.compile(r"^-?\d[\d,]*(?:\.\d+)?$")


class SayAsError(ValueError):
    pass


def read_cardinal(text: str) -> str:
    cleaned = text.strip()
    if not NUMBER_PATTERN.match(cleaned):
        raise SayAsError(f"not a number: {text!r}")
    return normalize_text(cleaned)


def read_ordinal(text: str) -> str:
    cleaned = text.strip().replace(",", "")
    if not cleaned.isdigit():
        raise SayAsError(f"not an ordinal: {text!r}")
    return numbers.ordinal(int(cleaned))


def read_digits(text: str) -> str:
    spoken = numbers.digits(text, zero="zero")
    if not spoken:
        raise SayAsError(f"no digits in {text!r}")
    return spoken


def read_telephone(text: str) -> str:
    prefix = "plus " if text.strip().startswith("+") else ""
    groups = [group for group in re.split(r"\D+", text) if group]
    if not groups:
        raise SayAsError(f"no digits in {text!r}")
    return prefix + ", ".join(numbers.digits(group) for group in groups)


def read_date(text: str, date_format: str) -> str:
    fields = DATE_FIELDS.get(date_format.lower())
    if fields is None:
        raise SayAsError(f"unknown date format: {date_format!r}")
    parts = [part for part in re.split(r"\D+", text.strip()) if part]
    if len(parts) == len(fields):
        order = fields
    elif len(parts) == 3 and len(parts[0]) == 4:
        order = DATE_FIELDS["ymd"]
    else:
        raise SayAsError(f"date {text!r} does not match format {date_format!r}")
    spoken: list[str] = []
    for field, part in zip(order, parts):
        value = int(part)
        if field == "month":
            if not 1 <= value <= 12:
                raise SayAsError(f"invalid month: {part!r}")
            spoken.append(MONTHS[value - 1])
        elif field == "day":
            spoken.append(numbers.ordinal(value))
        else:
            spoken.append(numbers.year(value) if value >= 1000 else numbers.cardinal(value))
    return " ".join(spoken)


def read_currency(text: str) -> str:
    cleaned = text.strip()
    code_match = re.match(r"^([\d,.]+)\s*([A-Z]{3})$", cleaned)
    if code_match and code_match.group(2) in CURRENCY_CODES:
        cleaned = CURRENCY_CODES[code_match.group(2)] + code_match.group(1)
    elif cleaned and cleaned[0].isdigit():
        cleaned = "$" + cleaned
    spoken = normalize_text(cleaned)
    if spoken == cleaned:
        raise SayAsError(f"not a currency amount: {text!r}")
    return spoken


def interpret(kind: str, text: str, date_format: str | None = None) -> str:
    kind = kind.lower()
    if kind == "cardinal" or kind == "number":
        return read_cardinal(text)
    if kind == "ordinal":
        return read_ordinal(text)
    if kind == "digits":
        return read_digits(text)
    if kind == "telephone":
        return read_telephone(text)
    if kind == "date":
        return read_date(text, date_format or "mdy")
    if kind == "currency":
        return read_currency(text)
    raise SayAsError(f"unsupported interpret-as: {kind!r}")

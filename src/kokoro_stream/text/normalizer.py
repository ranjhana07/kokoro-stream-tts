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

MONTHS = (
    "January", "February", "March", "April", "May", "June", "July",
    "August", "September", "October", "November", "December",
)
MONTH_NAMES = "|".join(MONTHS)
YEAR_CONTEXT = (
    "in|since|until|till|by|from|during|before|after|around|circa|of|year|through|to|"
    + MONTH_NAMES
)

ABBREVIATIONS = {
    "Dr": "Doctor",
    "Mr": "Mister",
    "Mrs": "Missus",
    "Ms": "Miss",
    "Prof": "Professor",
    "Jr": "Junior",
    "Sr": "Senior",
    "vs": "versus",
    "approx": "approximately",
    "Inc": "Incorporated",
    "Ltd": "Limited",
}
LATIN_PHRASES = {"e.g.": "for example", "i.e.": "that is", "etc.": "et cetera"}

UNITS = {
    "km/h": ("kilometer per hour", "kilometers per hour"),
    "mph": ("mile per hour", "miles per hour"),
    "khz": ("kilohertz", "kilohertz"),
    "mhz": ("megahertz", "megahertz"),
    "ghz": ("gigahertz", "gigahertz"),
    "hz": ("hertz", "hertz"),
    "kg": ("kilogram", "kilograms"),
    "mg": ("milligram", "milligrams"),
    "km": ("kilometer", "kilometers"),
    "cm": ("centimeter", "centimeters"),
    "mm": ("millimeter", "millimeters"),
    "ml": ("milliliter", "milliliters"),
    "ms": ("millisecond", "milliseconds"),
    "kb": ("kilobyte", "kilobytes"),
    "mb": ("megabyte", "megabytes"),
    "gb": ("gigabyte", "gigabytes"),
    "tb": ("terabyte", "terabytes"),
    "lbs": ("pound", "pounds"),
    "lb": ("pound", "pounds"),
    "g": ("gram", "grams"),
    "m": ("meter", "meters"),
    "l": ("liter", "liters"),
    "°c": ("degree celsius", "degrees celsius"),
    "°f": ("degree fahrenheit", "degrees fahrenheit"),
}

MAGNITUDE_SUFFIXES = {"k": "thousand", "m": "million", "b": "billion", "bn": "billion"}

CURRENCY_PATTERN = re.compile(
    r"([$€£₹])\s?(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?(?:(?:\s(thousand|million|billion|trillion))|(?:\s?(bn|[kKmMbB]))(?![\w]))?(?![\w])"
)
PERCENT_PATTERN = re.compile(r"(?<![\w.])(-?\d{1,3}(?:,\d{3})+|-?\d+)(?:\.(\d+))?\s?%")
DECIMAL_PATTERN = re.compile(r"(?<![\w.])(-?)(\d+)\.(\d+)(?![\w])")
INTEGER_PATTERN = re.compile(r"(?<![\w.])(-?)(\d{1,3}(?:,\d{3})+|\d+)(?![\w])")
SPACES_PATTERN = re.compile(r"[ \t]+")
ABBREVIATION_PATTERN = re.compile(r"\b(" + "|".join(ABBREVIATIONS) + r")\.(?=\s)")
LATIN_PATTERN = re.compile(r"(?<![\w.])(e\.g\.|i\.e\.|etc\.)", re.IGNORECASE)
REPEATED_PUNCTUATION_PATTERN = re.compile(r"([!?])[!?]+")
PLUS_NUMBER_PATTERN = re.compile(r"(?<![\w+])\+(\d)")
AMPERSAND_PATTERN = re.compile(r"\s&\s")
HASH_PATTERN = re.compile(r"#(\d+)")
LONG_DATE_PATTERN = re.compile(
    rf"\b({MONTH_NAMES})\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})(?![\w])"
)
ISO_DATE_PATTERN = re.compile(r"(?<![\w-])(\d{4})-(\d{2})-(\d{2})(?![\w-])")
MERIDIEM_TIME_PATTERN = re.compile(
    r"(?<![\w:.])(\d{1,2})(?::(\d{2}))?\s?([ap])(?:\.m|m)(?![\w])(?:\.(?=\s+[a-z0-9]))?",
    re.IGNORECASE,
)
CLOCK_TIME_PATTERN = re.compile(r"(?<![\w:.])([01]?\d|2[0-3]):([0-5]\d)(?![\w:])")
ORDINAL_PATTERN = re.compile(r"(?<![\w.])(\d+)(?:st|nd|rd|th)\b", re.IGNORECASE)
DECADE_PATTERN = re.compile(r"(?<![\w.])(1\d{3}|20\d{2})s\b")
YEAR_PATTERN = re.compile(
    rf"\b({YEAR_CONTEXT})(\s+)(1\d{{3}}|20\d{{2}})(?![\w%]|[.,]\d)", re.IGNORECASE
)
UNIT_PATTERN = re.compile(
    r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?\s?("
    + "|".join(re.escape(unit) for unit in UNITS)
    + r")(?![\w/])",
    re.IGNORECASE,
)
SECTION_ROMAN_PATTERN = re.compile(r"\b(Chapter|Part|Section|Act|Book|Volume|Vol\.|Appendix|Phase|Level)\s+([IVXLCDM]{1,8})\b")
ROYAL_ROMAN_PATTERN = re.compile(
    r"\b(Henry|Louis|George|Charles|Edward|Elizabeth|Richard|William|James|John|Pope [A-Z][a-z]+|World War|Super Bowl)\s+([IVXLCDM]{1,8})\b"
)
RANGE_PATTERN = re.compile(r"(?<![\w.-])(\d+)\s?[-–]\s?(\d+)(?![\w-])")
FRACTION_PATTERN = re.compile(r"(?<![\w./])(\d{1,2})/(\d{1,2})(?![\w/]|\.\d)")
PHONE_PATTERN = re.compile(r"(?<![\w-])(\+?1[-. ])?\(?(\d{3})\)?[-. ](\d{3})[-. ](\d{4})(?![\w-])")
SLASH_DATE_PATTERN = re.compile(r"(?<![\w/])(\d{1,2})/(\d{1,2})/(\d{4})(?![\w/])")
VERSION_PATTERN =re.compile(r"(?<![\w.])(\d+(?:\.\d+){2,})(?![\w.]\d|\w)")
THOUSANDS_PATTERN = re.compile(r"(?<![\w.])(\d+)\s?[kK](?![\w])")


def say_integer(text: str) -> str:
    cleaned = text.replace(",", "")
    if len(cleaned) > 1 and cleaned.startswith("0"):
        return numbers.digits(cleaned)
    if len(cleaned) > 18:
        return numbers.digits(cleaned)
    return numbers.cardinal(int(cleaned))


def say_decimal(whole: str, fraction: str) -> str:
    return f"{say_integer(whole)} point {numbers.digits_plain(fraction)}"


def say_time(hour: int, minute: int, meridiem: str | None) -> str:
    minute_words = f"oh {numbers.cardinal(minute)}" if minute < 10 else numbers.cardinal(minute)
    if meridiem:
        suffix = f" {meridiem} m"
        if minute == 0:
            return f"{numbers.cardinal(hour)}{suffix}"
        return f"{numbers.cardinal(hour)} {minute_words}{suffix}"
    if minute == 0:
        if hour == 0:
            return "midnight"
        if hour == 12:
            return "noon"
        if hour < 12:
            return f"{numbers.cardinal(hour)} o'clock"
        return f"{numbers.cardinal(hour)} hundred"
    return f"{numbers.cardinal(hour)} {minute_words}"


def expand_abbreviation(match: re.Match[str]) -> str:
    return ABBREVIATIONS[match.group(1)]


def expand_latin(match: re.Match[str]) -> str:
    key = match.group(1).lower()
    spoken = LATIN_PHRASES[key]
    remainder = match.string[match.end():]
    ends_sentence = not remainder.strip() or (
        remainder[:1].isspace() and remainder.strip()[:1].isupper()
    )
    if key == "etc." and ends_sentence:
        return f"{spoken}."
    return spoken


def expand_long_date(match: re.Match[str]) -> str:
    month, day, year_text = match.groups()
    return f"{month} {numbers.ordinal(int(day))} {numbers.year(int(year_text))}"


def expand_iso_date(match: re.Match[str]) -> str:
    year_text, month_text, day_text = match.groups()
    month_index, day = int(month_text), int(day_text)
    if not (1 <= month_index <= 12 and 1 <= day <= 31):
        return match.group(0)
    return f"{MONTHS[month_index - 1]} {numbers.ordinal(day)} {numbers.year(int(year_text))}"


def expand_currency(match: re.Match[str]) -> str:
    symbol, whole_text, fraction_text, magnitude_word, magnitude_suffix = match.groups()
    singular, plural, minor_singular, minor_plural = CURRENCIES[symbol]
    magnitude = magnitude_word or MAGNITUDE_SUFFIXES.get((magnitude_suffix or "").lower())
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


def expand_meridiem_time(match: re.Match[str]) -> str:
    hour_text, minute_text, meridiem = match.groups()
    hour = int(hour_text)
    if not 1 <= hour <= 12:
        return match.group(0)
    return say_time(hour, int(minute_text or 0), meridiem.lower())


def expand_clock_time(match: re.Match[str]) -> str:
    return say_time(int(match.group(1)), int(match.group(2)), None)


def expand_ordinal(match: re.Match[str]) -> str:
    return numbers.ordinal(int(match.group(1)))


def expand_decade(match: re.Match[str]) -> str:
    spoken = numbers.year(int(match.group(1)))
    if spoken.endswith("y"):
        return spoken[:-1] + "ies"
    return spoken + "s"


def expand_year(match: re.Match[str]) -> str:
    context, spacing, year_text = match.groups()
    return f"{context}{spacing}{numbers.year(int(year_text))}"


def expand_unit(match: re.Match[str]) -> str:
    whole_text, fraction_text, unit_text = match.groups()
    singular, plural = UNITS[unit_text.lower()]
    amount = say_decimal(whole_text, fraction_text) if fraction_text else say_integer(whole_text)
    is_one = whole_text == "1" and not fraction_text
    return f"{amount} {singular if is_one else plural}"


def expand_fraction(match: re.Match[str]) -> str:
    numerator, denominator = int(match.group(1)), int(match.group(2))
    if not 0 < numerator < denominator <= 10 or denominator == 1:
        return f"{say_integer(match.group(1))} {say_integer(match.group(2))}"
    if denominator == 2:
        return "one half" if numerator == 1 else f"{numbers.cardinal(numerator)} halves"
    if denominator == 4:
        return "one quarter" if numerator == 1 else f"{numbers.cardinal(numerator)} quarters"
    name = numbers.ordinal(denominator)
    return f"{numbers.cardinal(numerator)} {name}" if numerator == 1 else f"{numbers.cardinal(numerator)} {name}s"


def expand_phone(match: re.Match[str]) -> str:
    country, area, exchange, line = match.groups()
    prefix = "one, " if country else ""
    return f"{prefix}{numbers.digits(area)}, {numbers.digits(exchange)}, {numbers.digits(line)}"


def expand_slash_date(match: re.Match[str]) -> str:
    month, day, year_text = (int(group) for group in match.groups())
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return match.group(0)
    return f"{MONTHS[month - 1]} {numbers.ordinal(day)} {numbers.year(year_text)}"


def expand_section_roman(match: re.Match[str]) -> str:
    label, numeral = match.groups()
    try:
        return f"{label} {numbers.cardinal(numbers.roman_to_int(numeral))}"
    except ValueError:
        return match.group(0)


def expand_royal_roman(match: re.Match[str]) -> str:
    name, numeral = match.groups()
    try:
        value = numbers.roman_to_int(numeral)
    except ValueError:
        return match.group(0)
    if name in ("World War", "Super Bowl"):
        return f"{name} {numbers.cardinal(value)}"
    return f"{name} the {numbers.ordinal(value)}"


def expand_version(match: re.Match[str]) -> str:
    return " point ".join(say_integer(part) for part in match.group(1).split("."))


def expand_thousands(match: re.Match[str]) -> str:
    return f"{say_integer(match.group(1))} thousand"


def expand_range(match: re.Match[str]) -> str:
    start_text, end_text = match.groups()
    if start_text.startswith("0") or end_text.startswith("0"):
        return match.group(0)
    start, end = int(start_text), int(end_text)
    both_years = (
        len(start_text) == 4
        and len(end_text) == 4
        and 1000 <= start <= 2099
        and 1000 <= end <= 2099
    )
    if both_years:
        return f"{numbers.year(start)} to {numbers.year(end)}"
    return f"{say_integer(start_text)} to {say_integer(end_text)}"


def expand_decimal(match: re.Match[str]) -> str:
    sign, whole, fraction = match.groups()
    return f"{'minus ' if sign else ''}{say_decimal(whole, fraction)}"


def expand_integer(match: re.Match[str]) -> str:
    sign, text = match.groups()
    return f"{'minus ' if sign else ''}{say_integer(text)}"


PASSES: tuple[Callable[[str], str], ...] = (
    lambda text: LATIN_PATTERN.sub(expand_latin, text),
    lambda text: ABBREVIATION_PATTERN.sub(expand_abbreviation, text),
    lambda text: REPEATED_PUNCTUATION_PATTERN.sub(lambda match: match.group(1), text),
    lambda text: PLUS_NUMBER_PATTERN.sub(lambda match: "plus " + match.group(1), text),
    lambda text: AMPERSAND_PATTERN.sub(" and ", text),
    lambda text: HASH_PATTERN.sub(lambda match: f"number {say_integer(match.group(1))}", text),
    lambda text: SECTION_ROMAN_PATTERN.sub(expand_section_roman, text),
    lambda text: ROYAL_ROMAN_PATTERN.sub(expand_royal_roman, text),
    lambda text: LONG_DATE_PATTERN.sub(expand_long_date, text),
    lambda text: ISO_DATE_PATTERN.sub(expand_iso_date, text),
    lambda text: CURRENCY_PATTERN.sub(expand_currency, text),
    lambda text: PERCENT_PATTERN.sub(expand_percent, text),
    lambda text: MERIDIEM_TIME_PATTERN.sub(expand_meridiem_time, text),
    lambda text: CLOCK_TIME_PATTERN.sub(expand_clock_time, text),
    lambda text: ORDINAL_PATTERN.sub(expand_ordinal, text),
    lambda text: DECADE_PATTERN.sub(expand_decade, text),
    lambda text: YEAR_PATTERN.sub(expand_year, text),
    lambda text: SLASH_DATE_PATTERN.sub(expand_slash_date, text),
    lambda text: PHONE_PATTERN.sub(expand_phone, text),
    lambda text: FRACTION_PATTERN.sub(expand_fraction, text),
    lambda text: VERSION_PATTERN.sub(expand_version, text),
    lambda text: UNIT_PATTERN.sub(expand_unit, text),
    lambda text: THOUSANDS_PATTERN.sub(expand_thousands, text),
    lambda text: RANGE_PATTERN.sub(expand_range, text),
    lambda text: DECIMAL_PATTERN.sub(expand_decimal, text),
    lambda text: INTEGER_PATTERN.sub(expand_integer, text),
)


def normalize_text(text: str) -> str:
    for apply_pass in PASSES:
        text = apply_pass(text)
    return SPACES_PATTERN.sub(" ", text).strip()

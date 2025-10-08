from __future__ import annotations

ONES = (
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
    "seventeen", "eighteen", "nineteen",
)
TENS = ("", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety")
SCALES = ("", "thousand", "million", "billion", "trillion", "quadrillion")

ORDINAL_IRREGULAR = {
    "one": "first",
    "two": "second",
    "three": "third",
    "five": "fifth",
    "eight": "eighth",
    "nine": "ninth",
    "twelve": "twelfth",
}


def _below_thousand(value: int) -> str:
    words: list[str] = []
    hundreds, remainder = divmod(value, 100)
    if hundreds:
        words.append(f"{ONES[hundreds]} hundred")
    if remainder:
        if remainder < 20:
            words.append(ONES[remainder])
        else:
            tens, ones = divmod(remainder, 10)
            words.append(TENS[tens] if ones == 0 else f"{TENS[tens]} {ONES[ones]}")
    return " ".join(words)


def cardinal(value: int) -> str:
    if value < 0:
        return f"minus {cardinal(-value)}"
    if value == 0:
        return ONES[0]
    groups: list[str] = []
    scale_index = 0
    while value > 0:
        value, group = divmod(value, 1000)
        if group:
            spoken = _below_thousand(group)
            scale = SCALES[scale_index]
            groups.append(f"{spoken} {scale}" if scale else spoken)
        scale_index += 1
        if scale_index >= len(SCALES) and value > 0:
            raise ValueError("number too large")
    return " ".join(reversed(groups))


def ordinal(value: int) -> str:
    words = cardinal(value).split(" ")
    last = words[-1]
    if last in ORDINAL_IRREGULAR:
        words[-1] = ORDINAL_IRREGULAR[last]
    elif last.endswith("y"):
        words[-1] = last[:-1] + "ieth"
    else:
        words[-1] = last + "th"
    return " ".join(words)


def digits(text: str) -> str:
    spoken: list[str] = []
    for char in text:
        if char.isdigit():
            spoken.append("oh" if char == "0" else ONES[int(char)])
    return " ".join(spoken)


def decimal(text: str) -> str:
    whole, _, fraction = text.partition(".")
    whole_words = cardinal(int(whole)) if whole else ONES[0]
    if not fraction:
        return whole_words
    fraction_words = " ".join(ONES[int(char)] for char in fraction if char.isdigit())
    return f"{whole_words} point {fraction_words}"


def year(value: int) -> str:
    if 2000 <= value <= 2009:
        return cardinal(value)
    if value % 100 == 0 and value >= 1000:
        return cardinal(value)
    high, low = divmod(value, 100)
    if low == 0:
        return f"{cardinal(high)} hundred"
    low_words = f"oh {ONES[low]}" if low < 10 else cardinal(low)
    return f"{cardinal(high)} {low_words}"

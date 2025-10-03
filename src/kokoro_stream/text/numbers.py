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

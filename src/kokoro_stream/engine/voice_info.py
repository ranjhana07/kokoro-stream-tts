from __future__ import annotations

ACCENTS = {
    "a": "en-US",
    "b": "en-GB",
    "e": "es",
    "f": "fr",
    "h": "hi",
    "i": "it",
    "j": "ja",
    "p": "pt-BR",
    "z": "zh",
}
GENDERS = {"f": "female", "m": "male"}


def describe_voice(name: str) -> dict[str, str]:
    prefix, _, label = name.partition("_")
    info = {"name": name}
    if len(prefix) == 2 and prefix[0] in ACCENTS and prefix[1] in GENDERS and label:
        info["language"] = ACCENTS[prefix[0]]
        info["gender"] = GENDERS[prefix[1]]
    return info

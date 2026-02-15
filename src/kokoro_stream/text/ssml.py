from __future__ import annotations

import re
import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass, replace
from typing import Union

from kokoro_stream.text import say_as
from kokoro_stream.text.normalizer import normalize_text

BREAK_STRENGTH_MS = {
    "none": 0,
    "x-weak": 100,
    "weak": 200,
    "medium": 400,
    "strong": 700,
    "x-strong": 1000,
}
SENTENCE_PAUSE_MS = 250
PARAGRAPH_PAUSE_MS = 600
MAX_BREAK_MS = 10_000

RATE_KEYWORDS = {"x-slow": 0.5, "slow": 0.75, "medium": 1.0, "fast": 1.25, "x-fast": 1.5}
EMPHASIS_SPEED = {"strong": 0.88, "moderate": 0.94, "none": 1.0, "reduced": 1.06}
MIN_SPEED = 0.5
MAX_SPEED = 2.0

TIME_PATTERN = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(ms|s)?\s*$", re.IGNORECASE)
WHITESPACE_PATTERN = re.compile(r"\s+")
PARAGRAPH_PATTERN = re.compile(r"\n\s*\n")


class SSMLError(ValueError):
    pass


@dataclass(frozen=True)
class SpeechSegment:
    text: str
    speed: float = 1.0
    voice: str | None = None


@dataclass(frozen=True)
class PauseSegment:
    duration_ms: int


Segment = Union[SpeechSegment, PauseSegment]


@dataclass(frozen=True)
class Context:
    speed: float = 1.0
    voice: str | None = None


def is_ssml(text: str) -> bool:
    return text.lstrip().startswith("<speak")


def parse_time(value: str) -> int:
    match = TIME_PATTERN.match(value)
    if not match:
        raise SSMLError(f"invalid break time: {value!r}")
    amount = float(match.group(1))
    unit = (match.group(2) or "s").lower()
    milliseconds = amount if unit == "ms" else amount * 1000
    return min(int(round(milliseconds)), MAX_BREAK_MS)


def parse_rate(value: str) -> float:
    cleaned = value.strip().lower()
    if cleaned in RATE_KEYWORDS:
        return RATE_KEYWORDS[cleaned]
    if cleaned.endswith("%"):
        try:
            amount = float(cleaned[:-1])
        except ValueError as error:
            raise SSMLError(f"invalid prosody rate: {value!r}") from error
        if cleaned[0] in "+-":
            return 1.0 + amount / 100.0
        return amount / 100.0
    raise SSMLError(f"invalid prosody rate: {value!r}")


def clamp_speed(speed: float) -> float:
    return max(MIN_SPEED, min(MAX_SPEED, speed))


class SegmentBuilder:
    def __init__(self) -> None:
        self.segments: list[Segment] = []
        self._pending: list[str] = []
        self._pending_context = Context()

    def add_text(self, text: str | None, context: Context) -> None:
        if not text:
            return
        if self._pending and context != self._pending_context:
            self.flush()
        self._pending_context = context
        self._pending.append(text)

    def add_pause(self, duration_ms: int) -> None:
        self.flush()
        if duration_ms <= 0:
            return
        if self.segments and isinstance(self.segments[-1], PauseSegment):
            previous = self.segments[-1]
            self.segments[-1] = PauseSegment(max(previous.duration_ms, duration_ms))
            return
        self.segments.append(PauseSegment(duration_ms))

    def flush(self) -> None:
        if not self._pending:
            return
        joined = WHITESPACE_PATTERN.sub(" ", "".join(self._pending)).strip()
        self._pending = []
        spoken = normalize_text(joined)
        if spoken:
            self.segments.append(
                SpeechSegment(spoken, self._pending_context.speed, self._pending_context.voice)
            )

    def finish(self) -> list[Segment]:
        self.flush()
        while self.segments and isinstance(self.segments[-1], PauseSegment):
            self.segments.pop()
        return self.segments


def walk(element: ElementTree.Element, context: Context, builder: SegmentBuilder) -> None:
    tag = element.tag.lower()
    if tag == "break":
        builder.add_pause(break_duration(element))
        return
    if tag == "sub":
        builder.add_text(element.get("alias", "".join(element.itertext())), context)
        return
    if tag == "phoneme":
        builder.add_text(read_phoneme(element), context)
        return
    if tag == "say-as":
        builder.add_text(read_say_as(element), context)
        return
    inner = context
    if tag == "prosody" and element.get("rate"):
        inner = replace(context, speed=clamp_speed(context.speed * parse_rate(element.get("rate", ""))))
    elif tag == "voice":
        name = element.get("name")
        if not name:
            raise SSMLError("voice requires a name")
        inner = replace(context, voice=name)
    elif tag == "emphasis":
        level = element.get("level", "moderate").lower()
        if level not in EMPHASIS_SPEED:
            raise SSMLError(f"unknown emphasis level: {level!r}")
        inner = replace(context, speed=clamp_speed(context.speed * EMPHASIS_SPEED[level]))
    builder.add_text(element.text, inner)
    for child in element:
        walk(child, inner, builder)
        builder.add_text(child.tail, inner)
    if tag == "s":
        builder.add_pause(SENTENCE_PAUSE_MS)
    elif tag == "p":
        builder.add_pause(PARAGRAPH_PAUSE_MS)


def read_phoneme(element: ElementTree.Element) -> str:
    alphabet = element.get("alphabet", "ipa").lower()
    if alphabet != "ipa":
        raise SSMLError(f"unsupported phoneme alphabet: {alphabet!r}")
    phonemes = element.get("ph", "").strip()
    if not phonemes or any(char in phonemes for char in "()[]/"):
        raise SSMLError("phoneme requires a plain ph attribute")
    word = "".join(element.itertext()).strip() or "word"
    return f"[{word}](/{phonemes}/)"


def read_say_as(element: ElementTree.Element) -> str:
    kind = element.get("interpret-as")
    if not kind:
        raise SSMLError("say-as requires interpret-as")
    content = "".join(element.itertext())
    try:
        return say_as.interpret(kind, content, element.get("format"))
    except say_as.SayAsError as error:
        raise SSMLError(str(error)) from error


def break_duration(element: ElementTree.Element) -> int:
    time_value = element.get("time")
    if time_value is not None:
        return parse_time(time_value)
    strength = element.get("strength", "medium").lower()
    if strength not in BREAK_STRENGTH_MS:
        raise SSMLError(f"unknown break strength: {strength!r}")
    return BREAK_STRENGTH_MS[strength]


def parse_plain(text: str) -> list[Segment]:
    builder = SegmentBuilder()
    paragraphs = PARAGRAPH_PATTERN.split(text)
    for index, paragraph in enumerate(paragraphs):
        builder.add_text(paragraph, Context())
        if index < len(paragraphs) - 1:
            builder.add_pause(PARAGRAPH_PAUSE_MS)
    return builder.finish()


def parse_ssml(markup: str) -> list[Segment]:
    if not is_ssml(markup):
        return parse_plain(markup)
    try:
        root = ElementTree.fromstring(markup.strip())
    except ElementTree.ParseError as error:
        raise SSMLError(f"malformed SSML: {error}") from error
    if root.tag.lower() != "speak":
        raise SSMLError("root element must be <speak>")
    builder = SegmentBuilder()
    walk(root, Context(), builder)
    return builder.finish()

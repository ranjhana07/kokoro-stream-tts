from __future__ import annotations

import re
from dataclasses import dataclass, replace

from kokoro_stream.text.ssml import PauseSegment, Segment

SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+|(?<=[.!?][\"')”])\s+")
CLAUSE_BREAK = re.compile(r"(?<=[,;:—])\s+")
INITIAL_ENDING = re.compile(r"(?:^|\s)[A-Z]\.$")


@dataclass(frozen=True)
class Chunk:
    text: str
    speed: float = 1.0
    pause_ms: int = 0


def split_sentences(text: str) -> list[str]:
    sentences: list[str] = []
    for piece in SENTENCE_BREAK.split(text.strip()):
        piece = piece.strip()
        if not piece:
            continue
        if sentences and INITIAL_ENDING.search(sentences[-1]):
            sentences[-1] = f"{sentences[-1]} {piece}"
        else:
            sentences.append(piece)
    return sentences


def split_words(text: str, limit: int) -> list[str]:
    pieces: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if len(candidate) <= limit or not current:
            current = candidate
        else:
            pieces.append(current)
            current = word
    if current:
        pieces.append(current)
    return pieces


def split_long_sentence(sentence: str, limit: int) -> list[str]:
    if len(sentence) <= limit:
        return [sentence]
    pieces: list[str] = []
    current = ""
    for clause in CLAUSE_BREAK.split(sentence):
        candidate = f"{current} {clause}".strip()
        if len(candidate) <= limit:
            current = candidate
            continue
        if current:
            pieces.append(current)
        if len(clause) <= limit:
            current = clause
        else:
            pieces.extend(split_words(clause, limit))
            current = ""
    if current:
        pieces.append(current)
    return pieces


def pack_pieces(pieces: list[str], limit: int) -> list[str]:
    packed: list[str] = []
    current = ""
    for piece in pieces:
        candidate = f"{current} {piece}".strip()
        if len(candidate) <= limit:
            current = candidate
        else:
            if current:
                packed.append(current)
            current = piece
    if current:
        packed.append(current)
    return packed


def split_text(text: str, max_chars: int) -> list[str]:
    pieces: list[str] = []
    for sentence in split_sentences(text):
        pieces.extend(split_long_sentence(sentence, max_chars))
    return pack_pieces(pieces, max_chars)


def plan_chunks(segments: list[Segment], max_chars: int = 220) -> list[Chunk]:
    chunks: list[Chunk] = []
    for segment in segments:
        if isinstance(segment, PauseSegment):
            if chunks:
                last = chunks[-1]
                chunks[-1] = replace(last, pause_ms=last.pause_ms + segment.duration_ms)
            else:
                chunks.append(Chunk("", pause_ms=segment.duration_ms))
            continue
        for text in split_text(segment.text, max_chars):
            chunks.append(Chunk(text, speed=segment.speed))
    return chunks

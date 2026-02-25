from __future__ import annotations

import math
import re
from dataclasses import dataclass, replace

from kokoro_stream.text.ssml import PauseSegment, Segment

SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+|(?<=[.!?][\"')”])\s+")
CLAUSE_BREAK = re.compile(r"(?<=[,;:—])\s+")
INITIAL_ENDING = re.compile(r"(?:^|\s)[A-Z]\.$")


PHONEMES_PER_CHAR = 1.2


@dataclass(frozen=True)
class ChunkBudget:
    first_chars: int = 60
    max_chars: int = 220
    max_phonemes: int = 400

    @property
    def char_limit(self) -> int:
        return max(1, min(self.max_chars, int(self.max_phonemes / PHONEMES_PER_CHAR)))


def estimate_phonemes(text: str) -> int:
    return math.ceil(len(text) * PHONEMES_PER_CHAR)


@dataclass(frozen=True)
class Chunk:
    text: str
    speed: float = 1.0
    pause_ms: int = 0
    voice: str | None = None


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


DANGLING_WORDS = frozenset(
    "a an the and or but of to in on at for with from by as that which who is are was were be".split()
)


def split_words(text: str, limit: int) -> list[str]:
    words = text.split()
    pieces: list[list[str]] = []
    current: list[str] = []
    for word in words:
        candidate = " ".join([*current, word])
        if len(candidate) <= limit or not current:
            current.append(word)
        else:
            pieces.append(current)
            current = [word]
    if current:
        pieces.append(current)
    for index in range(len(pieces) - 1):
        tail = pieces[index]
        while len(tail) > 1 and tail[-1].lower().strip(".,;:!?\"'") in DANGLING_WORDS:
            carried = tail.pop()
            if len(" ".join([carried, *pieces[index + 1]])) > limit:
                tail.append(carried)
                break
            pieces[index + 1].insert(0, carried)
    return [" ".join(piece) for piece in pieces if piece]


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


def split_text(text: str, budget: ChunkBudget, first_chunk: bool) -> list[str]:
    limit = budget.char_limit
    sentences = split_sentences(text)
    if not sentences:
        return []
    if not first_chunk:
        pieces: list[str] = []
        for sentence in sentences:
            pieces.extend(split_long_sentence(sentence, limit))
        return pack_pieces(pieces, limit)
    head_limit = min(budget.first_chars, limit)
    pieces = split_long_sentence(sentences[0], head_limit)
    for sentence in sentences[1:]:
        pieces.extend(split_long_sentence(sentence, limit))
    head = pieces[0]
    consumed = 1
    while consumed < len(pieces) and len(f"{head} {pieces[consumed]}") <= head_limit:
        head = f"{head} {pieces[consumed]}"
        consumed += 1
    return [head] + pack_pieces(pieces[consumed:], limit)


def plan_chunks(segments: list[Segment], budget: ChunkBudget | None = None) -> list[Chunk]:
    budget = budget or ChunkBudget()
    chunks: list[Chunk] = []
    spoken_any = False
    for segment in segments:
        if isinstance(segment, PauseSegment):
            if chunks:
                last = chunks[-1]
                chunks[-1] = replace(last, pause_ms=last.pause_ms + segment.duration_ms)
            else:
                chunks.append(Chunk("", pause_ms=segment.duration_ms))
            continue
        for text in split_text(segment.text, budget, first_chunk=not spoken_any):
            chunks.append(Chunk(text, speed=segment.speed, voice=segment.voice))
            spoken_any = True
    return chunks

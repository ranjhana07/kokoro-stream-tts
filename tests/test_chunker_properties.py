import random

import pytest

from kokoro_stream.text.chunker import ChunkBudget, estimate_phonemes, plan_chunks
from kokoro_stream.text.ssml import SpeechSegment

WORDS = "the quick brown fox jumps over a lazy dog while seven small birds sing loudly near an old stone bridge".split()
ENDINGS = [".", "!", "?", ",", ";", ""]


def random_text(rng):
    sentences = []
    for _ in range(rng.randint(1, 15)):
        words = [rng.choice(WORDS) for _ in range(rng.randint(1, 40))]
        sentences.append(" ".join(words) + rng.choice([".", "!", "?"]))
    return " ".join(sentences)


@pytest.mark.parametrize("seed", range(25))
def test_chunks_keep_every_word_in_order_within_budget(seed):
    rng = random.Random(seed)
    text = random_text(rng)
    first = rng.choice([20, 40, 60])
    maximum = rng.choice([80, 120, 220])
    budget = ChunkBudget(first_chars=first, max_chars=maximum, max_phonemes=400)
    chunks = plan_chunks([SpeechSegment(text)], budget)
    assert " ".join(chunk.text for chunk in chunks).split() == text.split()
    assert len(chunks[0].text) <= max(first, max(len(word) for word in text.split()))
    for chunk in chunks:
        assert len(chunk.text) <= maximum
        assert estimate_phonemes(chunk.text) <= 400 + 12


@pytest.mark.parametrize("seed", range(10))
def test_comma_heavy_text_without_sentence_ends(seed):
    rng = random.Random(100 + seed)
    words = [rng.choice(WORDS) + rng.choice(ENDINGS[3:5] + ["", ""]) for _ in range(rng.randint(30, 120))]
    text = " ".join(words)
    chunks = plan_chunks([SpeechSegment(text)], ChunkBudget(first_chars=30, max_chars=90))
    assert " ".join(chunk.text for chunk in chunks).split() == text.split()
    assert all(len(chunk.text) <= 90 for chunk in chunks)

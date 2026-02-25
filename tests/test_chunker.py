from kokoro_stream.text.chunker import (
    Chunk,
    ChunkBudget,
    estimate_phonemes,
    plan_chunks,
    split_sentences,
)
from kokoro_stream.text.ssml import PauseSegment, SpeechSegment, parse_ssml


def test_split_sentences_basic():
    assert split_sentences("One. Two! Three? Four") == ["One.", "Two!", "Three?", "Four"]


def test_split_sentences_keeps_initials_together():
    assert split_sentences("J. R. Tolkien wrote it. Fine.") == ["J. R. Tolkien wrote it.", "Fine."]


def test_split_sentences_handles_closing_quotes():
    assert split_sentences('He said "stop." Then left.') == ['He said "stop."', "Then left."]


def test_first_chunk_stays_short():
    text = "Hello there. " + "This second sentence is a lot longer than the first one. " * 3
    chunks = plan_chunks([SpeechSegment(text.strip())], ChunkBudget(first_chars=30, max_chars=200))
    assert chunks[0].text == "Hello there."
    assert len(chunks) == 2


def test_first_chunk_is_split_at_clause_when_too_long():
    text = "Well, this opening sentence runs on quite a bit, and then it keeps going for a while."
    chunks = plan_chunks([SpeechSegment(text)], ChunkBudget(first_chars=30, max_chars=200))
    assert len(chunks[0].text) <= 30
    assert chunks[0].text.endswith(",")
    assert " ".join(chunk.text for chunk in chunks) == text


def test_chunks_respect_max_chars():
    sentences = " ".join(f"Sentence number {index} is of a modest length." for index in range(20))
    chunks = plan_chunks([SpeechSegment(sentences)], ChunkBudget(first_chars=40, max_chars=100))
    assert all(len(chunk.text) <= 100 for chunk in chunks)
    assert " ".join(chunk.text for chunk in chunks) == sentences


def test_long_sentence_without_punctuation_is_split_on_words():
    text = " ".join(["word"] * 100)
    chunks = plan_chunks([SpeechSegment(text)], ChunkBudget(first_chars=50, max_chars=80))
    assert all(len(chunk.text) <= 80 for chunk in chunks)
    assert " ".join(chunk.text for chunk in chunks) == text


def test_phoneme_budget_lowers_char_limit():
    budget = ChunkBudget(first_chars=60, max_chars=500, max_phonemes=120)
    assert budget.char_limit == 100
    text = " ".join(["word"] * 80)
    chunks = plan_chunks([SpeechSegment(text)], budget)
    assert all(estimate_phonemes(chunk.text) <= 120 for chunk in chunks)


def test_pauses_attach_to_previous_chunk():
    segments = [SpeechSegment("Hello."), PauseSegment(500), SpeechSegment("World.")]
    assert plan_chunks(segments) == [Chunk("Hello.", pause_ms=500), Chunk("World.")]


def test_leading_pause_becomes_silence_chunk():
    chunks = plan_chunks([PauseSegment(300), SpeechSegment("Go.")])
    assert chunks == [Chunk("", pause_ms=300), Chunk("Go.")]


def test_speed_is_carried_per_segment():
    segments = parse_ssml('<speak>Normal. <prosody rate="fast">Quick one.</prosody></speak>')
    chunks = plan_chunks(segments)
    assert [chunk.speed for chunk in chunks] == [1.0, 1.25]


def test_only_first_speech_chunk_uses_short_limit():
    segments = [SpeechSegment("A short opening."), SpeechSegment("x " * 60)]
    chunks = plan_chunks(segments, ChunkBudget(first_chars=20, max_chars=200))
    assert len(chunks) == 2
    assert len(chunks[1].text) > 20


def test_forced_word_split_does_not_leave_a_dangling_article():
    text = "Thanks for calling the support line and thanks for waiting"
    chunks = plan_chunks([SpeechSegment(text)], ChunkBudget(first_chars=22, max_chars=22))
    assert chunks[0].text == "Thanks for calling"
    assert " ".join(chunk.text for chunk in chunks) == text


def test_dangling_word_stays_when_moving_it_would_overflow():
    text = "alpha beta the gamma"
    chunks = plan_chunks([SpeechSegment(text)], ChunkBudget(first_chars=14, max_chars=14))
    assert " ".join(chunk.text for chunk in chunks) == text
    assert all(len(chunk.text) <= 14 for chunk in chunks)

import pytest

from kokoro_stream.config import Settings
from kokoro_stream.engine.sine import SineEngine
from kokoro_stream.streaming.pipeline import StreamingSynthesizer
from kokoro_stream.streaming.prefetch import PrefetchPool


@pytest.fixture
def settings():
    return Settings(first_chunk_chars=40, max_chunk_chars=120, prefetch_depth=3, crossfade_ms=60)


@pytest.fixture
def engine(settings):
    return SineEngine(sample_rate=settings.sample_rate)


@pytest.fixture
def pool():
    pool = PrefetchPool(workers=4)
    yield pool
    pool.shutdown()


@pytest.fixture
def synthesizer(engine, pool, settings):
    return StreamingSynthesizer(engine, pool, settings)

import threading

import numpy as np

from kokoro_stream.streaming.cache import ChunkCache


def audio(length, value=0.1):
    return np.full(length, value, dtype=np.float32)


def test_miss_then_hit():
    cache = ChunkCache(max_bytes=10_000)
    assert cache.get("a") is None
    cache.put("a", audio(100))
    assert np.array_equal(cache.get("a"), audio(100))
    assert (cache.hits, cache.misses) == (1, 1)


def test_evicts_least_recently_used():
    cache = ChunkCache(max_bytes=1200)
    for key in "abc":
        cache.put(key, audio(100))
    cache.get("a")
    cache.put("d", audio(100))
    assert cache.get("b") is None
    assert cache.get("a") is not None
    assert cache.get("d") is not None
    assert cache.size_bytes <= 1200


def test_oversized_entries_are_not_stored():
    cache = ChunkCache(max_bytes=100)
    cache.put("big", audio(1000))
    assert len(cache) == 0


def test_replacing_a_key_updates_size():
    cache = ChunkCache(max_bytes=10_000)
    cache.put("a", audio(100))
    cache.put("a", audio(50))
    assert cache.size_bytes == 200
    assert len(cache) == 1


def test_cached_audio_is_isolated_from_the_caller():
    cache = ChunkCache(max_bytes=10_000)
    original = audio(10)
    cache.put("a", original)
    original[:] = 9.0
    assert cache.get("a")[0] == np.float32(0.1)
    assert not cache.get("a").flags.writeable


def test_concurrent_access_keeps_size_consistent():
    cache = ChunkCache(max_bytes=4000)

    def hammer(offset):
        for index in range(200):
            cache.put((offset, index % 20), audio(50))
            cache.get((offset, (index + 3) % 20))

    threads = [threading.Thread(target=hammer, args=(offset,)) for offset in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert cache.size_bytes == sum(entry.nbytes for entry in cache._entries.values())
    assert cache.size_bytes <= 4000

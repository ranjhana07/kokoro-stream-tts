import random
import threading
import time

import pytest

from kokoro_stream.streaming.prefetch import PrefetchPool, StreamPrefetcher


@pytest.fixture
def pool():
    pool = PrefetchPool(workers=4)
    yield pool
    pool.shutdown()


def test_results_come_back_in_submission_order(pool):
    rng = random.Random(3)
    delays = {index: rng.uniform(0, 0.02) for index in range(30)}

    def work(index):
        time.sleep(delays[index])
        return index

    results = list(StreamPrefetcher(pool, range(30), work, depth=5))
    assert results == list(range(30))


def test_prefetch_runs_ahead_of_consumer(pool):
    started = []
    lock = threading.Lock()

    def work(index):
        with lock:
            started.append(index)
        return index

    prefetcher = StreamPrefetcher(pool, range(10), work, depth=3)
    deadline = time.time() + 2
    while len(started) < 3 and time.time() < deadline:
        time.sleep(0.005)
    assert sorted(started) == [0, 1, 2]
    next(prefetcher)
    deadline = time.time() + 2
    while len(started) < 4 and time.time() < deadline:
        time.sleep(0.005)
    assert 3 in started
    prefetcher.close()


def test_depth_bounds_work_in_flight(pool):
    gate = threading.Event()
    started = []
    lock = threading.Lock()

    def work(index):
        with lock:
            started.append(index)
        gate.wait(2)
        return index

    prefetcher = StreamPrefetcher(pool, range(20), work, depth=2)
    time.sleep(0.1)
    assert len(started) <= 2
    gate.set()
    assert list(prefetcher) == list(range(20))


def test_worker_exception_surfaces_at_its_position(pool):
    def work(index):
        if index == 2:
            raise RuntimeError("synthesis failed")
        return index

    prefetcher = StreamPrefetcher(pool, range(5), work, depth=3)
    assert next(prefetcher) == 0
    assert next(prefetcher) == 1
    with pytest.raises(RuntimeError, match="synthesis failed"):
        next(prefetcher)
    prefetcher.close()


def test_close_cancels_queued_work():
    pool = PrefetchPool(workers=1)
    gate = threading.Event()
    ran = []

    def work(index):
        gate.wait(2)
        ran.append(index)
        return index

    prefetcher = StreamPrefetcher(pool, range(10), work, depth=5)
    time.sleep(0.05)
    prefetcher.close()
    gate.set()
    pool.shutdown()
    assert len(ran) < 5


def test_empty_input_stops_immediately(pool):
    assert list(StreamPrefetcher(pool, [], lambda item: item)) == []


def test_pool_rejects_zero_workers():
    with pytest.raises(ValueError):
        PrefetchPool(0)


def test_streams_share_pool_without_mixing_results(pool):
    def make(offset):
        return StreamPrefetcher(pool, range(offset, offset + 15), lambda value: value * 2, depth=3)

    outputs = {}

    def consume(offset):
        outputs[offset] = list(make(offset))

    threads = [threading.Thread(target=consume, args=(offset,)) for offset in (0, 100, 200, 300)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    for offset, values in outputs.items():
        assert values == [value * 2 for value in range(offset, offset + 15)]


def test_head_priority_runs_before_queued_body_work():
    pool = PrefetchPool(workers=1)
    gate = threading.Event()
    order = []
    blocker = pool.submit(lambda: gate.wait(2))
    time.sleep(0.05)
    body = [pool.submit(order.append, f"body-{index}") for index in range(3)]
    head = pool.submit(order.append, "head", priority=0)
    gate.set()
    for future in [blocker, head, *body]:
        future.result(timeout=2)
    pool.shutdown()
    assert order == ["head", "body-0", "body-1", "body-2"]


def test_new_stream_first_chunk_is_not_stuck_behind_older_streams():
    pool = PrefetchPool(workers=1)
    gate = threading.Event()
    order = []

    def work(label):
        gate.wait(2)
        order.append(label)
        return label

    old_stream = StreamPrefetcher(pool, ["old-0", "old-1", "old-2", "old-3"], work, depth=4)
    time.sleep(0.05)
    new_stream = StreamPrefetcher(pool, ["new-0", "new-1"], work, depth=2)
    gate.set()
    list(old_stream)
    list(new_stream)
    pool.shutdown()
    assert order.index("new-0") < order.index("old-2")


def test_shutdown_cancels_pending_and_rejects_new_work():
    pool = PrefetchPool(workers=1)
    gate = threading.Event()
    running = pool.submit(lambda: gate.wait(2))
    time.sleep(0.05)
    pending = pool.submit(lambda: "never")
    gate.set()
    pool.shutdown()
    assert running.done()
    assert pending.cancelled() or pending.result(timeout=1) == "never"
    with pytest.raises(RuntimeError):
        pool.submit(lambda: 1)

from kokoro_stream.service.limits import ReleasingIterator, StreamLimiter


def test_limiter_rejects_beyond_capacity():
    limiter = StreamLimiter(2)
    assert limiter.try_acquire()
    assert limiter.try_acquire()
    assert not limiter.try_acquire()
    limiter.release()
    assert limiter.try_acquire()


def test_zero_means_unlimited():
    limiter = StreamLimiter(0)
    assert all(limiter.try_acquire() for _ in range(1000))
    limiter.release()
    assert limiter.active == 0


def test_release_never_goes_negative():
    limiter = StreamLimiter(1)
    limiter.release()
    limiter.release()
    assert limiter.active == 0
    assert limiter.try_acquire()


def test_iterator_releases_when_exhausted():
    released = []
    stream = ReleasingIterator(iter([b"a", b"b"]), lambda: released.append(1))
    assert list(stream) == [b"a", b"b"]
    assert released == [1]


def test_iterator_releases_when_closed_before_start():
    released = []

    def frames():
        yield b"a"

    stream = ReleasingIterator(frames(), lambda: released.append(1))
    stream.close()
    stream.close()
    assert released == [1]


def test_iterator_releases_on_source_error():
    released = []

    def broken():
        yield b"a"
        raise RuntimeError("boom")

    stream = ReleasingIterator(broken(), lambda: released.append(1))
    next(stream)
    try:
        next(stream)
    except RuntimeError:
        pass
    assert released == [1]

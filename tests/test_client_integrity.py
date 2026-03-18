import numpy as np
import pytest

from kokoro_stream.client import StreamError, stream_speech
from kokoro_stream.streaming.frames import encode_audio, encode_end, encode_error


class FakeResponse:
    status_code = 200
    headers = {}

    def __init__(self, payload):
        self._payload = payload

    def iter_content(self, chunk_size=None):
        for index in range(0, len(self._payload), 13):
            yield self._payload[index : index + 13]

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeSession:
    def __init__(self, payload):
        self.payload = payload

    def post(self, *args, **kwargs):
        return FakeResponse(self.payload)


def audio(sequence, length=480):
    return encode_audio(sequence, np.zeros(length, dtype=np.float32), 24000)


def test_well_formed_stream_is_accepted():
    payload = audio(0) + audio(1) + encode_end(2, 24000)
    result = stream_speech("http://x", "hi", session=FakeSession(payload))
    assert (result.frame_count, result.sample_count, result.sample_rate) == (2, 960, 24000)


def test_missing_frame_is_detected():
    payload = audio(0) + audio(2) + encode_end(2, 24000)
    with pytest.raises(StreamError, match="expected"):
        stream_speech("http://x", "hi", session=FakeSession(payload))


def test_end_frame_count_mismatch_is_detected():
    payload = audio(0) + encode_end(3, 24000)
    with pytest.raises(StreamError, match="end frame"):
        stream_speech("http://x", "hi", session=FakeSession(payload))


def test_error_frame_raises_with_its_message():
    payload = audio(0) + encode_error(1, "EngineError: boom")
    with pytest.raises(StreamError, match="boom"):
        stream_speech("http://x", "hi", session=FakeSession(payload))


def test_truncated_stream_is_reported():
    with pytest.raises(StreamError, match="without an end frame"):
        stream_speech("http://x", "hi", session=FakeSession(audio(0)))

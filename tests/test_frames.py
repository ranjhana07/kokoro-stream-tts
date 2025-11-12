import struct

import numpy as np
import pytest

from kokoro_stream.streaming.frames import (
    HEADER_SIZE,
    MAGIC,
    Frame,
    FrameDecoder,
    FrameError,
    FrameType,
    decode_all,
    encode_audio,
    encode_end,
    encode_error,
    encode_frame,
    float_to_pcm16,
    pcm16_to_float,
)


def test_header_size_is_twenty_bytes():
    assert HEADER_SIZE == 20
    assert encode_end(0, 24000).startswith(MAGIC)
    assert len(encode_end(0, 24000)) == HEADER_SIZE


def test_audio_round_trip():
    samples = np.array([0, 1, -1, 32767, -32767, 1234], dtype="<i2")
    frames = decode_all(encode_audio(7, samples, 24000))
    assert len(frames) == 1
    frame = frames[0]
    assert frame.frame_type is FrameType.AUDIO
    assert frame.sequence == 7
    assert frame.sample_rate == 24000
    assert frame.channels == 1
    assert np.array_equal(frame.samples(), samples)


def test_float_input_is_converted_and_clipped():
    frames = decode_all(encode_audio(0, np.array([0.0, 0.5, 2.0, -2.0], dtype=np.float32), 16000))
    assert frames[0].samples().tolist() == [0, 16384, 32767, -32767]


def test_pcm_conversion_round_trip_is_close():
    original = np.linspace(-1, 1, 101, dtype=np.float32)
    restored = pcm16_to_float(float_to_pcm16(original))
    assert np.max(np.abs(restored - original)) < 1e-4


def test_end_and_error_frames():
    data = encode_audio(0, np.zeros(4, dtype=np.float32), 24000) + encode_end(1, 24000)
    data += encode_error(2, "boom")
    frames = decode_all(data)
    assert [frame.frame_type for frame in frames] == [FrameType.AUDIO, FrameType.END, FrameType.ERROR]
    assert frames[2].message() == "boom"
    assert frames[1].payload == b""


def test_decoder_handles_byte_by_byte_feed():
    stream = b"".join(
        encode_audio(index, np.full(10, index, dtype="<i2"), 24000) for index in range(5)
    ) + encode_end(5, 24000)
    decoder = FrameDecoder()
    frames: list[Frame] = []
    for byte in stream:
        frames.extend(decoder.feed(bytes([byte])))
    assert [frame.sequence for frame in frames] == [0, 1, 2, 3, 4, 5]
    assert decoder.pending_bytes == 0


def test_decoder_handles_arbitrary_split_points():
    stream = b"".join(encode_audio(i, np.arange(50, dtype="<i2"), 24000) for i in range(4))
    for split in (1, 19, 20, 21, 57, 150):
        decoder = FrameDecoder()
        frames = decoder.feed(stream[:split]) + decoder.feed(stream[split:])
        assert len(frames) == 4


def test_bad_magic_rejected():
    data = bytearray(encode_end(0, 24000))
    data[0:4] = b"NOPE"
    with pytest.raises(FrameError):
        decode_all(bytes(data))


def test_bad_version_rejected():
    data = bytearray(encode_end(0, 24000))
    data[4] = 9
    with pytest.raises(FrameError):
        decode_all(bytes(data))


def test_unknown_frame_type_rejected():
    data = bytearray(encode_end(0, 24000))
    data[5] = 77
    with pytest.raises(FrameError):
        decode_all(bytes(data))


def test_oversized_declared_payload_rejected():
    header = struct.pack(">4sBBIIHI", MAGIC, 1, 1, 0, 24000, 1, 1 << 30)
    with pytest.raises(FrameError):
        FrameDecoder().feed(header)


def test_trailing_bytes_detected():
    with pytest.raises(FrameError):
        decode_all(encode_end(0, 24000) + b"\x00\x01")


def test_samples_only_on_audio_frames():
    with pytest.raises(FrameError):
        Frame(FrameType.END, 0, 24000, 1).samples()


def test_encode_frame_header_fields_are_big_endian():
    data = encode_frame(Frame(FrameType.AUDIO, 258, 24000, 2, b"\x00\x00"))
    assert data[6:10] == (258).to_bytes(4, "big")
    assert data[14:16] == (2).to_bytes(2, "big")
    assert data[16:20] == (2).to_bytes(4, "big")

import numpy as np

from kokoro_stream.streaming.frames import FrameDecoder, FrameType, encode_audio, encode_end, encode_error


def build_stream(rng, count):
    stream = b""
    expected = []
    for sequence in range(count):
        samples = rng.integers(-32767, 32767, size=int(rng.integers(0, 400)), dtype=np.int16).astype("<i2")
        stream += encode_audio(sequence, samples, 24000)
        expected.append(samples)
    return stream, expected


def test_random_split_points_never_change_the_decoded_frames():
    rng = np.random.default_rng(11)
    for _ in range(40):
        stream, expected = build_stream(rng, int(rng.integers(1, 12)))
        stream += encode_end(len(expected), 24000)
        cuts = sorted(int(cut) for cut in rng.integers(0, len(stream) + 1, size=int(rng.integers(1, 8))))
        decoder = FrameDecoder()
        frames = []
        previous = 0
        for cut in cuts + [len(stream)]:
            frames.extend(decoder.feed(stream[previous:cut]))
            previous = cut
        assert decoder.pending_bytes == 0
        assert [frame.sequence for frame in frames] == list(range(len(expected) + 1))
        for frame, samples in zip(frames[:-1], expected):
            assert np.array_equal(frame.samples(), samples)
        assert frames[-1].frame_type is FrameType.END


def test_error_message_survives_a_split_utf8_payload():
    message = "synthesis failed — voice not found"
    data = encode_error(3, message)
    decoder = FrameDecoder()
    frames = []
    for index in range(0, len(data), 7):
        frames.extend(decoder.feed(data[index : index + 7]))
    assert frames[0].message() == message

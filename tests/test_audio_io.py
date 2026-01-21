import struct
import wave

import numpy as np

from kokoro_stream.audio_io import WavFileWriter, encode_wav, streaming_wav_header


def test_streaming_header_layout():
    header = streaming_wav_header(24000)
    assert len(header) == 44
    assert header[:4] == b"RIFF"
    assert header[8:16] == b"WAVEfmt "
    audio_format, channels, rate, byte_rate, block_align, bits = struct.unpack("<HHIIHH", header[20:36])
    assert (audio_format, channels, rate, byte_rate, block_align, bits) == (1, 1, 24000, 48000, 2, 16)
    assert header[36:40] == b"data"
    assert struct.unpack("<I", header[40:44])[0] == 0xFFFFFFFF


def test_encode_wav_round_trip(tmp_path):
    samples = np.sin(np.linspace(0, 20, 2400)).astype(np.float32) * 0.5
    path = tmp_path / "x.wav"
    path.write_bytes(encode_wav(samples, 16000))
    with wave.open(str(path)) as reader:
        assert reader.getframerate() == 16000
        restored = np.frombuffer(reader.readframes(reader.getnframes()), dtype="<i2") / 32767.0
    assert np.max(np.abs(restored - samples)) < 1e-4


def test_wav_file_writer_tracks_duration(tmp_path):
    with WavFileWriter(tmp_path / "w.wav", 8000) as writer:
        writer.write_float(np.zeros(4000, dtype=np.float32))
        writer.write_float(np.zeros(4000, dtype=np.float32))
        assert writer.duration == 1.0
    with wave.open(str(tmp_path / "w.wav")) as reader:
        assert reader.getnframes() == 8000

# kokoro-stream-tts

A streaming text-to-speech service built on Kokoro (ONNX Runtime). A request is split into sentence-aware chunks, the chunks are synthesized ahead of playback on a thread pool, and the audio goes out over chunked HTTP as small binary PCM frames. The client can start playing after the first short chunk instead of waiting for the whole utterance.

The service is a Flask app served by Gunicorn with threaded workers. Long documents can be submitted as asynchronous jobs through Kafka, and a worker writes WAV files to a directory or an S3 prefix.

## How it works

```
                        +-----------------------------------------------+
  POST /v1/tts/stream   |                 Flask / Gunicorn              |
  ------------------->  |  parse + validate request                     |
                        |  SSML parser -> normalizer -> chunker         |
                        |        |                                      |
                        |        v     chunk 0 (short)  chunk 1 ... N   |
                        |  +--------------------------------------+    |
                        |  | per-stream prefetcher (bounded)      |    |
                        |  | submits chunk N+1..N+k to the pool   |    |
                        |  +------------------+-------------------+    |
                        |                     |                        |
                        |        +------------v-----------+            |
                        |        |  shared priority pool  |            |
                        |        |  (engine.synthesize)   |            |
                        |        +------------+-----------+            |
                        |                     | float32 audio          |
                        |        +------------v-----------+            |
                        |        | 60 ms equal-power      |            |
                        |        | crossfade, hold tail   |            |
                        |        +------------+-----------+            |
                        |                     | int16 PCM              |
  chunked HTTP frames   |        +------------v-----------+            |
  <-------------------  |        | frame encoder (KSTF)   |            |
                        |        +------------------------+            |
                        +-----------------------------------------------+

  POST /v1/jobs ---> Kafka (tts.jobs.requests) ---> worker ---> WAV in output dir / S3
                                                       |
  GET /v1/jobs/<id> <--- status files <----------------+---> Kafka (tts.jobs.status)
```

Text pipeline:

1. `text/ssml.py` parses `speak`, `p`, `s`, `break`, `prosody` (rate), `say-as`, `sub` and `emphasis` into a list of speech and pause segments. Input that is not SSML is treated as plain text, with blank lines becoming paragraph pauses.
2. `text/normalizer.py` expands integers, decimals, ordinals, currency, percentages, years, dates, clock times, units and abbreviations into words. It is hand written, there is no dependency on a normalization library.
3. `text/chunker.py` splits on sentence boundaries, keeps the first chunk short so audio can start early, and caps every chunk by a character and phoneme budget.

Synthesis and streaming:

- `engine/kokoro.py` wraps `kokoro-v1.0.onnx` with ONNX Runtime. Phonemes come from `misaki`, falling back to `phonemizer` with espeak.
- `engine/sine.py` is a deterministic fake engine used by the tests and for running the service without model weights.
- `streaming/prefetch.py` runs a priority thread pool. Each stream keeps a bounded window of chunks in flight, and the first chunk of a stream is scheduled ahead of background chunks from older streams.
- `streaming/crossfade.py` holds back the last 60 ms of each chunk and blends it into the start of the next one with an equal-power curve.
- `streaming/frames.py` encodes and decodes the wire format described below.

## Frame format

Every response frame has a fixed 20 byte header followed by the payload. All header fields are big-endian. Audio payloads are little-endian signed 16-bit PCM.

| Offset | Size | Field          | Description                                        |
|-------:|-----:|----------------|----------------------------------------------------|
| 0      | 4    | magic          | ASCII `KSTF`                                       |
| 4      | 1    | version        | `1`                                                |
| 5      | 1    | frame type     | `1` audio, `2` end, `3` error                      |
| 6      | 4    | sequence       | frame counter starting at 0; on `end`, total audio frames |
| 10     | 4    | sample rate    | Hz                                                 |
| 14     | 2    | channels       | `1`                                                |
| 16     | 4    | payload length | bytes that follow the header                       |
| 20     | n    | payload        | int16 PCM for audio, empty for end, UTF-8 text for error |

A healthy stream is zero or more audio frames followed by one end frame. A failure after the response has started is reported as an error frame, since the HTTP status line is already sent.

## Setup

```
python -m venv .venv
.venv/bin/pip install -e ".[dev,serve]"
make test
```

To run with real weights, install the model extras and download the model files into `models/`:

```
pip install -e ".[kokoro]"
```

The service needs three files: `kokoro-v1.0.onnx` (or the `fp16`/`int8` variant) and `voices-v1.0.bin` from the kokoro-onnx model release, and `config.json` from the `hexgrad/Kokoro-82M` repository, which holds the phoneme vocabulary. Point `KOKORO_MODEL_PATH`, `KOKORO_VOICES_PATH` and `KOKORO_VOCAB_PATH` at them and set `KOKORO_ENGINE=kokoro`.

Run locally with the fake engine:

```
make run
```

Or with Gunicorn:

```
KOKORO_ENGINE=kokoro gunicorn -c gunicorn.conf.py kokoro_stream.wsgi:app
```

Docker, with Kafka in KRaft mode, the API and one worker:

```
make up
```

## Configuration

Everything is read from environment variables. `.env.example` lists them all.

| Variable | Default | Meaning |
|----------|---------|---------|
| `KOKORO_ENGINE` | `sine` | `kokoro` or `sine` |
| `KOKORO_MODEL_PATH` | `models/kokoro-v1.0.onnx` | ONNX model |
| `KOKORO_VOICES_PATH` | `models/voices-v1.0.bin` | voices archive |
| `KOKORO_VOCAB_PATH` | `models/config.json` | file with the phoneme vocabulary |
| `KOKORO_PHONEMIZER` | `auto` | `misaki`, `espeak` or `auto` (misaki first, espeak as fallback) |
| `KOKORO_PROVIDERS` | `CPUExecutionProvider` | comma separated ONNX Runtime providers |
| `KOKORO_INTRA_OP_THREADS` | `2` | ONNX Runtime intra-op threads per session |
| `FIRST_CHUNK_CHARS` | `60` | character budget for the first chunk |
| `MAX_CHUNK_CHARS` | `220` | character budget for the other chunks |
| `PREFETCH_DEPTH` | `3` | chunks synthesized ahead per stream |
| `PREFETCH_WORKERS` | `4` | threads in the shared synthesis pool |
| `CROSSFADE_MS` | `60` | crossfade length between chunks |
| `TRIM_SILENCE` | `1` | trim leading and trailing silence from each synthesized chunk |
| `CHUNK_CACHE_MB` | `32` | LRU cache of synthesized chunks, `0` disables it |
| `MAX_STREAMS` | `64` | concurrent streams before the service answers `429`, `0` for no limit |
| `API_KEYS` | empty | comma separated keys; when set, requests need `Authorization: Bearer <key>` or `X-API-Key` |
| `WARMUP` | `1` | run two short syntheses before accepting traffic |
| `MAX_TEXT_CHARS` | `5000` | request size limit for streaming and WAV endpoints |
| `KAFKA_BOOTSTRAP` | empty | broker address, jobs are disabled when empty |
| `JOB_MAX_ATTEMPTS` | `3` | delivery attempts before a job is failed and dead-lettered |
| `WORKER_METRICS_PORT` | `9100` | Prometheus port of the worker, `0` disables it |
| `JOB_OUTPUT` | `output/audio` | directory or `s3://bucket/prefix` for finished jobs |
| `WEB_THREADS` | `32` | Gunicorn threads per worker |

## API

Stream audio and write it to a WAV file with the bundled client:

```
kokoro-client --url http://localhost:8000 --text "Hello there. This is streamed." --out hello.wav
```

Plain curl returns the raw frames:

```
curl -sN -X POST localhost:8000/v1/tts/stream \
  -H 'Content-Type: application/json' \
  -d '{"text": "Hello there. This is streamed.", "voice": "af_heart"}' \
  --output frames.bin
```

Full WAV in one response:

```
curl -X POST localhost:8000/v1/tts -H 'Content-Type: application/json' \
  -d '{"text": "Call me at <say-as interpret-as=\"telephone\">555-0142</say-as>."}' \
  --output out.wav
```

SSML works on both endpoints when the text starts with `<speak>`:

```
<speak>
  <p>The total is <say-as interpret-as="currency">$12.50</say-as>.</p>
  <break time="400ms"/>
  <prosody rate="slow">Please wait.</prosody>
</speak>
```

Other endpoints:

| Endpoint | Purpose |
|----------|---------|
| `GET /v1/voices` | list voices and the default |
| `GET /healthz` | liveness and engine name |
| `GET /metrics` | Prometheus metrics: `tts_time_to_first_audio_seconds`, `tts_active_streams`, `tts_chunk_synthesis_seconds` |
| `POST /v1/jobs` | queue a long-form job, returns `202` with a job id |
| `GET /v1/jobs/<id>` | job state: `queued`, `running`, `done`, `failed` |

Request fields for `/v1/tts` and `/v1/tts/stream`: `text` (plain text or SSML), `voice`, `speed` (0.5 to 2.0) and `sample_rate` (8000 to 48000, the audio is resampled on the service side).

`/v1/tts/stream` also accepts `format`: `frames` (default, the framed protocol above), `pcm` (raw int16 little-endian samples, rate in the `Content-Type`) or `wav` (a WAV header with unknown length followed by PCM, playable by `ffplay` or a browser). The last two have no way to report an error after the response has started, so the connection is simply closed.

Jobs that fail with a transient error are put back on the request topic with an incremented attempt counter. After `JOB_MAX_ATTEMPTS` the job is marked `failed` and the request is published to the dead-letter topic with the failure reason. A redelivered message for a job that is already `done` is ignored.

Python client:

```python
from kokoro_stream.client import stream_speech

result = stream_speech("http://localhost:8000", "Hello there. This is streamed.", on_audio=lambda samples, rate: ...)
print(result.time_to_first_audio, result.real_time_factor)
```

Load test with 25 concurrent streams:

```
kokoro-loadtest --url http://localhost:8000 --streams 25 --json load.json
```

## Project layout

```
src/kokoro_stream/
  config.py            settings from the environment
  audio_io.py          WAV encoding and an incremental WAV writer
  client.py            streaming client and CLI
  loadtest.py          concurrent stream load test
  text/                ssml, normalizer, say-as, number words, chunker
  engine/              Kokoro ONNX engine, phonemizers, sine engine, factory
  streaming/           frames, crossfade, prefetch pool, pipeline
  service/             Flask app and Prometheus metrics
  jobs/                Kafka publisher/consumer, worker, status store, sinks
tests/                 pytest suite, runs without weights, Kafka or network
```

## Testing

```
make test
```

The tests use the sine engine and in-memory fakes for Kafka and S3. The frame codec, crossfade math, prefetch ordering and the Flask streaming endpoint are all covered without model weights. The live-server tests bind to a loopback port only.

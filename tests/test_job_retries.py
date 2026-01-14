import json

import numpy as np
import pytest

from kokoro_stream.jobs.kafka_io import KafkaJobPublisher
from kokoro_stream.jobs.models import JobRequest, JobState, new_job_id
from kokoro_stream.jobs.sinks import LocalSink
from kokoro_stream.jobs.store import FileJobStore
from kokoro_stream.jobs.worker import JobWorker
from kokoro_stream.streaming.pipeline import StreamingSynthesizer


class FlakyEngine:
    sample_rate = 24000

    def __init__(self, failures):
        self.failures = failures
        self.calls = 0

    def voices(self):
        return ["v"]

    def synthesize(self, text, voice, speed=1.0):
        self.calls += 1
        if self.failures > 0:
            self.failures -= 1
            raise ConnectionError("model server unreachable")
        return np.full(4800, 0.2, dtype=np.float32)


class RecordingPublisher:
    def __init__(self):
        self.statuses = []
        self.requests = []
        self.dead = []

    def submit(self, request):
        self.requests.append(request)

    def publish_status(self, status):
        self.statuses.append(status)

    def dead_letter(self, request, reason):
        self.dead.append((request, reason))


def build_worker(tmp_path, pool, settings, failures, max_attempts=3):
    engine = FlakyEngine(failures)
    synthesizer = StreamingSynthesizer(engine, pool, settings)
    publisher = RecordingPublisher()
    worker = JobWorker(
        synthesizer,
        FileJobStore(tmp_path / "status"),
        LocalSink(tmp_path / "audio"),
        publisher,
        tmp_path / "tmp",
        max_attempts=max_attempts,
    )
    return worker, publisher


def test_transient_failure_is_requeued_with_incremented_attempts(tmp_path, pool, settings):
    worker, publisher = build_worker(tmp_path, pool, settings, failures=10)
    request = JobRequest(new_job_id(), "Hello there.", "v")
    status = worker.process(request)
    assert status.state is JobState.QUEUED
    assert "retry 1 of 2" in status.detail
    assert [queued.attempts for queued in publisher.requests] == [1]
    assert publisher.requests[0].job_id == request.job_id
    assert publisher.dead == []


def test_job_succeeds_on_a_later_attempt(tmp_path, pool, settings):
    worker, publisher = build_worker(tmp_path, pool, settings, failures=1)
    request = JobRequest(new_job_id(), "Hello there.", "v")
    worker.process(request)
    retry = publisher.requests[0]
    status = worker.process(retry)
    assert status.state is JobState.DONE
    assert (tmp_path / "audio" / f"{request.job_id}.wav").exists()


def test_exhausted_attempts_fail_and_dead_letter(tmp_path, pool, settings):
    worker, publisher = build_worker(tmp_path, pool, settings, failures=100, max_attempts=2)
    request = JobRequest(new_job_id(), "Hello there.", "v", attempts=1)
    status = worker.process(request)
    assert status.state is JobState.FAILED
    assert "ConnectionError" in status.detail
    assert publisher.requests == []
    assert len(publisher.dead) == 1
    assert publisher.dead[0][0].job_id == request.job_id


def test_permanent_errors_are_not_retried(tmp_path, pool, settings):
    worker, publisher = build_worker(tmp_path, pool, settings, failures=0)
    status = worker.process(JobRequest(new_job_id(), "   ", "v"))
    assert status.state is JobState.FAILED
    assert publisher.requests == []
    assert publisher.dead == []


class FakeProducer:
    def __init__(self):
        self.messages = []

    def produce(self, topic, key=None, value=None, on_delivery=None):
        self.messages.append((topic, key, value))

    def poll(self, timeout):
        return 0


def test_kafka_dead_letter_carries_failure_reason():
    producer = FakeProducer()
    publisher = KafkaJobPublisher("b:9092", "req", "status", producer=producer, dead_letter_topic="dead")
    request = JobRequest(new_job_id(), "Hi.", "v", attempts=2)
    publisher.dead_letter(request, "ConnectionError: gone")
    topic, key, value = producer.messages[0]
    assert topic == "dead"
    assert key == request.job_id.encode()
    payload = json.loads(value)
    assert payload["failure"] == "ConnectionError: gone"
    assert payload["attempts"] == 2


def test_worker_metrics_count_outcomes(tmp_path, pool, settings):
    from kokoro_stream.jobs.metrics import JobMetrics
    from prometheus_client import generate_latest

    metrics = JobMetrics()
    engine = FlakyEngine(failures=1)
    publisher = RecordingPublisher()
    worker = JobWorker(
        StreamingSynthesizer(engine, pool, settings),
        FileJobStore(tmp_path / "status"),
        LocalSink(tmp_path / "audio"),
        publisher,
        tmp_path / "tmp",
        metrics=metrics,
    )
    request = JobRequest(new_job_id(), "Hello there.", "v")
    worker.process(request)
    worker.process(publisher.requests[0])
    worker.process(JobRequest(new_job_id(), "  ", "v"))
    text = generate_latest(metrics.registry).decode()
    assert 'tts_jobs_finished_total{state="done"} 1.0' in text
    assert 'tts_jobs_finished_total{state="failed"} 1.0' in text
    assert "tts_jobs_retried_total 1.0" in text
    assert "tts_job_audio_seconds_total" in text

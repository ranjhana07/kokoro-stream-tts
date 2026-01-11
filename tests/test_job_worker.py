import threading
import wave

import pytest

from kokoro_stream.jobs.models import JobRequest, JobState, new_job_id
from kokoro_stream.jobs.sinks import LocalSink
from kokoro_stream.jobs.store import FileJobStore
from kokoro_stream.jobs.worker import JobWorker

LONG_TEXT = " ".join(f"This is sentence number {index} of a long form document." for index in range(12))


class RecordingPublisher:
    def __init__(self):
        self.statuses = []
        self.requests = []

    def submit(self, request):
        self.requests.append(request)

    def publish_status(self, status):
        self.statuses.append(status)


class FakeMessage:
    def __init__(self, value, error=None):
        self._value = value
        self._error = error

    def value(self):
        return self._value

    def error(self):
        return self._error


class FakeConsumer:
    def __init__(self, messages, stop):
        self.messages = list(messages)
        self.committed = []
        self.closed = False
        self.stop = stop

    def poll(self, timeout):
        if not self.messages:
            self.stop.set()
            return None
        return self.messages.pop(0)

    def commit(self, message=None, asynchronous=True):
        self.committed.append(message)

    def close(self):
        self.closed = True


@pytest.fixture
def worker(tmp_path, synthesizer):
    publisher = RecordingPublisher()
    return JobWorker(
        synthesizer=synthesizer,
        store=FileJobStore(tmp_path / "status"),
        sink=LocalSink(tmp_path / "audio"),
        publisher=publisher,
        work_dir=tmp_path / "tmp",
    )


def test_process_writes_wav_and_reports_done(worker, tmp_path):
    request = JobRequest(new_job_id(), LONG_TEXT, "sine_mid")
    status = worker.process(request)
    assert status.state is JobState.DONE
    output = tmp_path / "audio" / f"{request.job_id}.wav"
    assert output.exists()
    with wave.open(str(output)) as reader:
        assert reader.getframerate() == 24000
        assert reader.getnframes() / 24000 == pytest.approx(status.duration, abs=0.001)
    assert status.duration > 5
    assert list((tmp_path / "tmp").iterdir()) == []


def test_status_transitions_are_published_and_stored(worker):
    request = JobRequest(new_job_id(), "Short text here.", "sine_low")
    worker.process(request)
    states = [status.state for status in worker.publisher.statuses]
    assert states == [JobState.RUNNING, JobState.DONE]
    assert worker.store.get(request.job_id).state is JobState.DONE


def test_unknown_voice_fails_job(worker, tmp_path):
    request = JobRequest(new_job_id(), LONG_TEXT, "no_such_voice")
    status = worker.process(request)
    assert status.state is JobState.FAILED
    assert "no_such_voice" in status.detail
    assert list((tmp_path / "tmp").iterdir()) == []
    assert worker.store.get(request.job_id).state is JobState.FAILED


def test_empty_text_fails_job(worker):
    status = worker.process(JobRequest(new_job_id(), "   ", "sine_low"))
    assert status.state is JobState.FAILED
    assert "speakable" in status.detail


def test_malformed_message_is_dropped(worker):
    assert worker.handle_message(b"not json") is None
    assert worker.handle_message(b'{"job_id": "x"}') is None
    assert worker.publisher.statuses == []


def test_run_consumes_commits_and_closes(worker):
    stop = threading.Event()
    good = JobRequest(new_job_id(), "Hello from the queue.", "sine_mid")
    messages = [
        FakeMessage(b"garbage"),
        FakeMessage(None, error="broker down"),
        FakeMessage(good.to_json()),
    ]
    consumer = FakeConsumer(messages, stop)
    worker.run(consumer, stop)
    assert consumer.closed
    assert len(consumer.committed) == 2
    assert worker.store.get(good.job_id).state is JobState.DONE


def test_redelivered_finished_job_is_not_synthesized_again(worker, tmp_path):
    request = JobRequest(new_job_id(), LONG_TEXT, "sine_mid")
    first = worker.process(request)
    output = tmp_path / "audio" / f"{request.job_id}.wav"
    output.write_bytes(b"marker")
    published_before = len(worker.publisher.statuses)
    second = worker.process(request)
    assert second == first
    assert output.read_bytes() == b"marker"
    assert len(worker.publisher.statuses) == published_before

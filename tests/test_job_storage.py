import json

import pytest

from kokoro_stream.jobs.kafka_io import KafkaJobPublisher
from kokoro_stream.jobs.models import (
    JobRequest,
    JobState,
    JobStatus,
    is_valid_job_id,
    new_job_id,
)
from kokoro_stream.jobs.sinks import LocalSink, S3Sink, sink_for
from kokoro_stream.jobs.store import FileJobStore


def test_job_ids_are_valid_and_unique():
    first, second = new_job_id(), new_job_id()
    assert first != second
    assert is_valid_job_id(first)
    assert not is_valid_job_id("../etc/passwd")
    assert not is_valid_job_id(first.upper())


def test_request_round_trip():
    request = JobRequest(new_job_id(), "Hello there.", "af_heart", 1.2)
    assert JobRequest.from_json(request.to_json()) == request


def test_request_rejects_bad_job_id():
    payload = json.dumps({"job_id": "nope", "text": "hi", "voice": "v"})
    with pytest.raises(ValueError):
        JobRequest.from_json(payload)


def test_status_round_trip():
    status = JobStatus(new_job_id(), JobState.DONE, output="out/a.wav", duration=3.5)
    assert JobStatus.from_json(status.to_json()) == status
    assert status.to_dict()["state"] == "done"


def test_file_store_put_and_get(tmp_path):
    store = FileJobStore(tmp_path / "status")
    job_id = new_job_id()
    assert store.get(job_id) is None
    store.put(JobStatus(job_id, JobState.QUEUED))
    store.put(JobStatus(job_id, JobState.RUNNING))
    assert store.get(job_id).state is JobState.RUNNING
    assert list((tmp_path / "status").glob("*.tmp")) == []


def test_file_store_rejects_traversal(tmp_path):
    store = FileJobStore(tmp_path)
    assert store.get("../../secret") is None
    with pytest.raises(ValueError):
        store.put(JobStatus("../evil", JobState.QUEUED))


def test_local_sink_moves_file(tmp_path):
    source = tmp_path / "work.wav"
    source.write_bytes(b"RIFF")
    sink = LocalSink(tmp_path / "audio")
    location = sink.publish(source, "result.wav")
    assert not source.exists()
    assert (tmp_path / "audio" / "result.wav").read_bytes() == b"RIFF"
    assert location.endswith("result.wav")


class FakeS3:
    def __init__(self):
        self.uploads = []

    def upload_file(self, path, bucket, key, ExtraArgs=None):
        self.uploads.append((path, bucket, key, ExtraArgs))


def test_s3_sink_uploads_and_cleans_up(tmp_path):
    source = tmp_path / "work.wav"
    source.write_bytes(b"RIFF")
    client = FakeS3()
    location = S3Sink("tts-bucket", "/renders/", client=client).publish(source, "a.wav")
    assert location == "s3://tts-bucket/renders/a.wav"
    assert client.uploads[0][1:3] == ("tts-bucket", "renders/a.wav")
    assert not source.exists()


def test_sink_for_picks_implementation(tmp_path):
    assert isinstance(sink_for(str(tmp_path / "out")), LocalSink)


def test_sink_for_requires_bucket():
    with pytest.raises(ValueError):
        sink_for("s3://")


class FakeProducer:
    def __init__(self):
        self.messages = []

    def produce(self, topic, key=None, value=None, on_delivery=None):
        self.messages.append((topic, key, value))

    def poll(self, timeout):
        return 0

    def flush(self, timeout):
        return 0


def test_kafka_publisher_uses_job_id_as_key():
    producer = FakeProducer()
    publisher = KafkaJobPublisher("broker:9092", "requests", "status", producer=producer)
    request = JobRequest(new_job_id(), "Hi.", "af_heart")
    publisher.submit(request)
    publisher.publish_status(JobStatus(request.job_id, JobState.QUEUED))
    assert [message[0] for message in producer.messages] == ["requests", "status"]
    assert all(message[1] == request.job_id.encode() for message in producer.messages)
    assert JobRequest.from_json(producer.messages[0][2]) == request

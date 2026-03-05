from kokoro_stream.config import Settings
from kokoro_stream.engine.sine import SineEngine
from kokoro_stream.jobs.models import JobState, JobStatus, new_job_id
from kokoro_stream.jobs.store import FileJobStore
from kokoro_stream.service.app import create_app


class RecordingPublisher:
    def __init__(self, fail=False):
        self.requests = []
        self.fail = fail

    def submit(self, request):
        if self.fail:
            raise RuntimeError("broker unavailable")
        self.requests.append(request)

    def publish_status(self, status):
        pass


def make_client(tmp_path, publisher):
    settings = Settings(default_voice="sine_mid", output_dir=str(tmp_path))
    app = create_app(
        settings,
        SineEngine(sample_rate=settings.sample_rate),
        publisher=publisher,
        job_store=FileJobStore(tmp_path / "status"),
    )
    return app.test_client()


def test_submit_job_enqueues_and_returns_202(tmp_path):
    publisher = RecordingPublisher()
    client = make_client(tmp_path, publisher)
    response = client.post("/v1/jobs", json={"text": "A long document.", "voice": "sine_low", "speed": 1.1})
    assert response.status_code == 202
    body = response.json
    assert body["state"] == "queued"
    assert body["status_url"] == f"/v1/jobs/{body['job_id']}"
    assert len(publisher.requests) == 1
    queued = publisher.requests[0]
    assert (queued.job_id, queued.voice, queued.speed) == (body["job_id"], "sine_low", 1.1)


def test_status_reflects_store(tmp_path):
    client = make_client(tmp_path, RecordingPublisher())
    job_id = client.post("/v1/jobs", json={"text": "Hello."}).json["job_id"]
    assert client.get(f"/v1/jobs/{job_id}").json["state"] == "queued"
    FileJobStore(tmp_path / "status").put(JobStatus(job_id, JobState.DONE, output="out.wav", duration=2.5))
    done = client.get(f"/v1/jobs/{job_id}").json
    assert done["state"] == "done"
    assert done["output"] == "out.wav"


def test_unknown_job_is_404(tmp_path):
    client = make_client(tmp_path, RecordingPublisher())
    assert client.get(f"/v1/jobs/{new_job_id()}").status_code == 404
    assert client.get("/v1/jobs/not-a-job-id").status_code == 404


def test_jobs_unavailable_without_publisher(tmp_path):
    client = make_client(tmp_path, None)
    assert client.post("/v1/jobs", json={"text": "Hello."}).status_code == 503


def test_enqueue_failure_marks_job_failed(tmp_path):
    client = make_client(tmp_path, RecordingPublisher(fail=True))
    response = client.post("/v1/jobs", json={"text": "Hello."})
    assert response.status_code == 503
    stored = list((tmp_path / "status").glob("*.json"))
    assert len(stored) == 1
    assert FileJobStore(tmp_path / "status").get(stored[0].stem).state is JobState.FAILED


def test_invalid_job_body_is_rejected(tmp_path):
    client = make_client(tmp_path, RecordingPublisher())
    assert client.post("/v1/jobs", json={"voice": "sine_low"}).status_code == 400


def make_client_with_output(tmp_path):
    settings = Settings(default_voice="sine_mid", output_dir=str(tmp_path), job_output=str(tmp_path / "audio"))
    app = create_app(
        settings,
        SineEngine(sample_rate=settings.sample_rate),
        publisher=RecordingPublisher(),
        job_store=FileJobStore(tmp_path / "status"),
    )
    return app.test_client(), FileJobStore(tmp_path / "status")


def test_finished_job_audio_can_be_downloaded(tmp_path):
    client, store = make_client_with_output(tmp_path)
    (tmp_path / "audio").mkdir()
    job_id = new_job_id()
    target = tmp_path / "audio" / f"{job_id}.wav"
    target.write_bytes(b"RIFFdata")
    store.put(JobStatus(job_id, JobState.DONE, output=str(target), duration=1.0))
    response = client.get(f"/v1/jobs/{job_id}/audio")
    assert response.status_code == 200
    assert response.mimetype == "audio/wav"
    assert response.data == b"RIFFdata"


def test_audio_is_not_served_before_the_job_is_done(tmp_path):
    client, store = make_client_with_output(tmp_path)
    job_id = new_job_id()
    store.put(JobStatus(job_id, JobState.RUNNING))
    assert client.get(f"/v1/jobs/{job_id}/audio").status_code == 409
    assert client.get(f"/v1/jobs/{new_job_id()}/audio").status_code == 404


def test_audio_outside_the_output_directory_is_refused(tmp_path):
    client, store = make_client_with_output(tmp_path)
    secret = tmp_path / "secret.txt"
    secret.write_text("nope")
    job_id = new_job_id()
    store.put(JobStatus(job_id, JobState.DONE, output=str(secret)))
    assert client.get(f"/v1/jobs/{job_id}/audio").status_code == 404


def test_s3_outputs_are_reported_as_locations(tmp_path):
    client, store = make_client_with_output(tmp_path)
    job_id = new_job_id()
    store.put(JobStatus(job_id, JobState.DONE, output="s3://bucket/a.wav"))
    assert client.get(f"/v1/jobs/{job_id}/audio").json == {"location": "s3://bucket/a.wav"}


def test_queued_job_can_be_cancelled(tmp_path):
    client, store = make_client_with_output(tmp_path)
    job_id = client.post("/v1/jobs", json={"text": "Hello there."}).json["job_id"]
    response = client.delete(f"/v1/jobs/{job_id}")
    assert response.status_code == 200
    assert response.json["state"] == "cancelled"
    assert store.get(job_id).state is JobState.CANCELLED


def test_running_and_finished_jobs_cannot_be_cancelled(tmp_path):
    client, store = make_client_with_output(tmp_path)
    for state in (JobState.RUNNING, JobState.DONE, JobState.FAILED):
        job_id = new_job_id()
        store.put(JobStatus(job_id, state))
        assert client.delete(f"/v1/jobs/{job_id}").status_code == 409


def test_cancelling_an_unknown_job_is_404(tmp_path):
    client, _ = make_client_with_output(tmp_path)
    assert client.delete(f"/v1/jobs/{new_job_id()}").status_code == 404

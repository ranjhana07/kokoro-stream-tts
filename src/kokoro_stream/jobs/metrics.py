from __future__ import annotations

from prometheus_client import CollectorRegistry, Counter, Histogram, start_http_server

JOB_BUCKETS = (0.5, 1, 2, 5, 10, 30, 60, 120, 300, 600)


class JobMetrics:
    def __init__(self, registry: CollectorRegistry | None = None) -> None:
        self.registry = registry or CollectorRegistry()
        self.finished = Counter(
            "tts_jobs_finished_total", "Jobs by final state", ["state"], registry=self.registry
        )
        self.retried = Counter("tts_jobs_retried_total", "Jobs put back on the queue", registry=self.registry)
        self.duration = Histogram(
            "tts_job_seconds", "Wall time spent on a job", buckets=JOB_BUCKETS, registry=self.registry
        )
        self.audio_seconds = Counter(
            "tts_job_audio_seconds_total", "Seconds of audio written by finished jobs", registry=self.registry
        )

    def serve(self, port: int) -> None:
        start_http_server(port, registry=self.registry)

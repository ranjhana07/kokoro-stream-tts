from __future__ import annotations

import json
import logging
import signal
import threading
from dataclasses import replace
from pathlib import Path
from typing import Any

from kokoro_stream.audio_io import WavFileWriter
from kokoro_stream.config import Settings
from kokoro_stream.engine.base import EngineError
from kokoro_stream.engine.factory import build_engine
from kokoro_stream.jobs.kafka_io import JobPublisher, KafkaJobPublisher, build_consumer
from kokoro_stream.jobs.models import JobRequest, JobState, JobStatus
from kokoro_stream.jobs.sinks import OutputSink, sink_for
from kokoro_stream.jobs.store import FileJobStore, JobStore
from kokoro_stream.streaming.pipeline import StreamingSynthesizer
from kokoro_stream.streaming.prefetch import PrefetchPool
from kokoro_stream.text.ssml import SSMLError

logger = logging.getLogger(__name__)

PERMANENT_ERRORS = (ValueError, EngineError, SSMLError)


class JobWorker:
    def __init__(
        self,
        synthesizer: StreamingSynthesizer,
        store: JobStore,
        sink: OutputSink,
        publisher: JobPublisher,
        work_dir: Path,
        max_attempts: int = 3,
    ) -> None:
        self.max_attempts = max_attempts
        self.synthesizer = synthesizer
        self.store = store
        self.sink = sink
        self.publisher = publisher
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)

    def _report(self, status: JobStatus) -> JobStatus:
        self.store.put(status)
        try:
            self.publisher.publish_status(status)
        except Exception:
            logger.exception("could not publish status for %s", status.job_id)
        return status

    def process(self, request: JobRequest) -> JobStatus:
        existing = self.store.get(request.job_id)
        if existing is not None and existing.state is JobState.DONE:
            logger.info("job %s already done, skipping redelivery", request.job_id)
            return existing
        self._report(JobStatus(request.job_id, JobState.RUNNING))
        temporary = self.work_dir / f"{request.job_id}.wav"
        try:
            chunks = self.synthesizer.prepare(request.text)
            if not chunks:
                raise ValueError("no speakable text")
            with WavFileWriter(temporary, self.synthesizer.engine.sample_rate) as writer:
                for audio in self.synthesizer.render(chunks, request.voice, request.speed):
                    writer.write_float(audio)
            location = self.sink.publish(temporary, f"{request.job_id}.wav")
            return self._report(
                JobStatus(request.job_id, JobState.DONE, output=location, duration=writer.duration)
            )
        except Exception as error:
            temporary.unlink(missing_ok=True)
            logger.exception("job %s failed", request.job_id)
            return self._handle_failure(request, error)

    def _handle_failure(self, request: JobRequest, error: Exception) -> JobStatus:
        detail = f"{type(error).__name__}: {error}"
        transient = not isinstance(error, PERMANENT_ERRORS)
        next_attempt = request.attempts + 1
        if transient and next_attempt < self.max_attempts:
            self.publisher.submit(replace(request, attempts=next_attempt))
            return self._report(
                JobStatus(
                    request.job_id,
                    JobState.QUEUED,
                    detail=f"retry {next_attempt} of {self.max_attempts - 1} after {detail}",
                )
            )
        if transient:
            try:
                self.publisher.dead_letter(request, detail)
            except Exception:
                logger.exception("could not dead-letter %s", request.job_id)
        return self._report(JobStatus(request.job_id, JobState.FAILED, detail=detail))

    def handle_message(self, raw: bytes) -> JobStatus | None:
        try:
            request = JobRequest.from_json(raw)
        except (KeyError, ValueError, TypeError, json.JSONDecodeError):
            logger.warning("dropping malformed job message")
            return None
        return self.process(request)

    def run(self, consumer: Any, stop: threading.Event) -> None:
        try:
            while not stop.is_set():
                message = consumer.poll(1.0)
                if message is None:
                    continue
                if message.error():
                    logger.error("consumer error: %s", message.error())
                    continue
                self.handle_message(message.value())
                consumer.commit(message=message, asynchronous=False)
        finally:
            consumer.close()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = Settings.from_env()
    engine = build_engine(settings)
    pool = PrefetchPool(settings.prefetch_workers)
    synthesizer = StreamingSynthesizer(engine, pool, settings)
    output = Path(settings.output_dir)
    worker = JobWorker(
        synthesizer=synthesizer,
        store=FileJobStore(output / "status"),
        sink=sink_for(settings.job_output),
        publisher=KafkaJobPublisher(
            settings.kafka_bootstrap,
            settings.kafka_request_topic,
            settings.kafka_status_topic,
            dead_letter_topic=settings.kafka_dead_letter_topic,
        ),
        work_dir=output / "tmp",
        max_attempts=settings.job_max_attempts,
    )
    consumer = build_consumer(settings.kafka_bootstrap, settings.kafka_group, settings.kafka_request_topic)
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    logger.info("worker started, topic=%s", settings.kafka_request_topic)
    worker.run(consumer, stop)
    pool.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

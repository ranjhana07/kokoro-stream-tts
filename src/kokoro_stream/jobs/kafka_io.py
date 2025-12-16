from __future__ import annotations

import logging
from typing import Any, Protocol

from kokoro_stream.jobs.models import JobRequest, JobStatus

logger = logging.getLogger(__name__)


class JobPublisher(Protocol):
    def submit(self, request: JobRequest) -> None: ...

    def publish_status(self, status: JobStatus) -> None: ...


class KafkaJobPublisher:
    def __init__(
        self,
        bootstrap: str,
        request_topic: str,
        status_topic: str,
        producer: Any | None = None,
    ) -> None:
        if producer is None:
            from confluent_kafka import Producer

            producer = Producer(
                {
                    "bootstrap.servers": bootstrap,
                    "enable.idempotence": True,
                    "linger.ms": 5,
                    "client.id": "kokoro-stream-tts",
                }
            )
        self.request_topic = request_topic
        self.status_topic = status_topic
        self._producer = producer

    def submit(self, request: JobRequest) -> None:
        self._produce(self.request_topic, request.job_id, request.to_json())

    def publish_status(self, status: JobStatus) -> None:
        self._produce(self.status_topic, status.job_id, status.to_json())

    def flush(self, timeout: float = 10.0) -> int:
        return self._producer.flush(timeout)

    def _produce(self, topic: str, key: str, value: bytes) -> None:
        self._producer.produce(topic, key=key.encode("utf-8"), value=value, on_delivery=self._on_delivery)
        self._producer.poll(0)

    @staticmethod
    def _on_delivery(error: Any, message: Any) -> None:
        if error is not None:
            logger.error("kafka delivery failed: %s", error)


def build_consumer(bootstrap: str, group: str, topic: str) -> Any:
    from confluent_kafka import Consumer

    consumer = Consumer(
        {
            "bootstrap.servers": bootstrap,
            "group.id": group,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
            "max.poll.interval.ms": 900_000,
            "session.timeout.ms": 30_000,
        }
    )
    consumer.subscribe([topic])
    return consumer

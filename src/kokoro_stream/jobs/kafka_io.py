from __future__ import annotations

import json
import logging
from typing import Any, Protocol

from kokoro_stream.jobs.models import JobRequest, JobStatus

logger = logging.getLogger(__name__)


class JobPublisher(Protocol):
    def submit(self, request: JobRequest) -> None: ...

    def publish_status(self, status: JobStatus) -> None: ...

    def dead_letter(self, request: JobRequest, reason: str) -> None: ...


class KafkaJobPublisher:
    def __init__(
        self,
        bootstrap: str,
        request_topic: str,
        status_topic: str,
        producer: Any | None = None,
        dead_letter_topic: str = "tts.jobs.dead",
        client_config: dict[str, Any] | None = None,
    ) -> None:
        if producer is None:
            from confluent_kafka import Producer

            producer = Producer(
                {
                    "bootstrap.servers": bootstrap,
                    "enable.idempotence": True,
                    "linger.ms": 5,
                    "client.id": "kokoro-stream-tts",
                    **(client_config or {}),
                }
            )
        self.request_topic = request_topic
        self.status_topic = status_topic
        self.dead_letter_topic = dead_letter_topic
        self._producer = producer

    def submit(self, request: JobRequest) -> None:
        self._produce(self.request_topic, request.job_id, request.to_json())

    def publish_status(self, status: JobStatus) -> None:
        self._produce(self.status_topic, status.job_id, status.to_json())

    def dead_letter(self, request: JobRequest, reason: str) -> None:
        payload = json.loads(request.to_json())
        payload["failure"] = reason
        self._produce(self.dead_letter_topic, request.job_id, json.dumps(payload).encode("utf-8"))

    def flush(self, timeout: float = 10.0) -> int:
        return self._producer.flush(timeout)

    def _produce(self, topic: str, key: str, value: bytes) -> None:
        self._producer.produce(topic, key=key.encode("utf-8"), value=value, on_delivery=self._on_delivery)
        self._producer.poll(0)

    @staticmethod
    def _on_delivery(error: Any, message: Any) -> None:
        if error is not None:
            logger.error("kafka delivery failed: %s", error)


def parse_client_config(raw: str) -> dict[str, Any]:
    if not raw.strip():
        return {}
    config = json.loads(raw)
    if not isinstance(config, dict):
        raise ValueError("KAFKA_CLIENT_CONFIG must be a JSON object")
    return config


def build_consumer(
    bootstrap: str, group: str, topic: str, client_config: dict[str, Any] | None = None
) -> Any:
    from confluent_kafka import Consumer

    consumer = Consumer(
        {
            "bootstrap.servers": bootstrap,
            "group.id": group,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
            "max.poll.interval.ms": 900_000,
            "session.timeout.ms": 30_000,
            **(client_config or {}),
        }
    )
    consumer.subscribe([topic])
    return consumer

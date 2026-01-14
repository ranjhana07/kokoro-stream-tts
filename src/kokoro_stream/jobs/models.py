from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum

JOB_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")


class JobState(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


def new_job_id() -> str:
    return uuid.uuid4().hex


def is_valid_job_id(value: str) -> bool:
    return bool(JOB_ID_PATTERN.match(value))


@dataclass(frozen=True)
class JobRequest:
    job_id: str
    text: str
    voice: str
    speed: float = 1.0
    created_at: float = field(default_factory=time.time)
    attempts: int = 0

    def to_json(self) -> bytes:
        return json.dumps(asdict(self)).encode("utf-8")

    @classmethod
    def from_json(cls, raw: bytes | str) -> "JobRequest":
        data = json.loads(raw)
        job_id = str(data["job_id"])
        if not is_valid_job_id(job_id):
            raise ValueError(f"invalid job id: {job_id!r}")
        return cls(
            job_id=job_id,
            text=str(data["text"]),
            voice=str(data["voice"]),
            speed=float(data.get("speed", 1.0)),
            created_at=float(data.get("created_at", time.time())),
            attempts=int(data.get("attempts", 0)),
        )


@dataclass(frozen=True)
class JobStatus:
    job_id: str
    state: JobState
    updated_at: float = field(default_factory=time.time)
    detail: str = ""
    output: str = ""
    duration: float = 0.0

    def to_json(self) -> bytes:
        payload = asdict(self)
        payload["state"] = self.state.value
        return json.dumps(payload).encode("utf-8")

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["state"] = self.state.value
        return payload

    @classmethod
    def from_json(cls, raw: bytes | str) -> "JobStatus":
        data = json.loads(raw)
        return cls(
            job_id=str(data["job_id"]),
            state=JobState(data["state"]),
            updated_at=float(data.get("updated_at", 0.0)),
            detail=str(data.get("detail", "")),
            output=str(data.get("output", "")),
            duration=float(data.get("duration", 0.0)),
        )

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Protocol

from kokoro_stream.jobs.models import JobStatus, is_valid_job_id


class JobStore(Protocol):
    def put(self, status: JobStatus) -> None: ...

    def get(self, job_id: str) -> JobStatus | None: ...


class FileJobStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, job_id: str) -> Path:
        if not is_valid_job_id(job_id):
            raise ValueError(f"invalid job id: {job_id!r}")
        return self.root / f"{job_id}.json"

    def put(self, status: JobStatus) -> None:
        target = self._path(status.job_id)
        descriptor, temporary = tempfile.mkstemp(dir=self.root, suffix=".tmp")
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(status.to_json())
        os.replace(temporary, target)

    def get(self, job_id: str) -> JobStatus | None:
        try:
            path = self._path(job_id)
        except ValueError:
            return None
        try:
            return JobStatus.from_json(path.read_bytes())
        except FileNotFoundError:
            return None

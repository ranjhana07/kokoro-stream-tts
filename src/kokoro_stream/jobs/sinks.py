from __future__ import annotations

import shutil
from pathlib import Path
from typing import Protocol


class OutputSink(Protocol):
    def publish(self, local_path: Path, name: str) -> str: ...


class LocalSink:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def publish(self, local_path: Path, name: str) -> str:
        destination = self.root / name
        shutil.move(str(local_path), destination)
        return str(destination)


class S3Sink:
    def __init__(self, bucket: str, prefix: str = "", client: object | None = None) -> None:
        if client is None:
            import boto3

            client = boto3.client("s3")
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self._client = client

    def publish(self, local_path: Path, name: str) -> str:
        key = f"{self.prefix}/{name}" if self.prefix else name
        self._client.upload_file(str(local_path), self.bucket, key, ExtraArgs={"ContentType": "audio/wav"})
        local_path.unlink(missing_ok=True)
        return f"s3://{self.bucket}/{key}"


def sink_for(destination: str) -> OutputSink:
    if destination.startswith("s3://"):
        remainder = destination[len("s3://") :]
        bucket, _, prefix = remainder.partition("/")
        if not bucket:
            raise ValueError("s3 destination needs a bucket")
        return S3Sink(bucket, prefix)
    return LocalSink(Path(destination))

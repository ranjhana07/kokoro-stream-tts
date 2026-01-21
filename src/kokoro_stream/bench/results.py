from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Sequence

from kokoro_stream.bench import hostinfo


def write_results(
    directory: Path,
    name: str,
    rows: Sequence[dict[str, Any]],
    summary: dict[str, Any],
    settings: dict[str, Any],
    arguments: dict[str, Any],
) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    json_path = directory / f"{name}.json"
    csv_path = directory / f"{name}.csv"
    document = {
        "name": name,
        "host": hostinfo.collect(),
        "settings": settings,
        "arguments": arguments,
        "summary": summary,
        "rows": list(rows),
    }
    json_path.write_text(json.dumps(document, indent=2, default=str), encoding="utf-8")
    columns: list[str] = []
    for row in rows:
        for column in row:
            if column not in columns:
                columns.append(column)
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    return json_path, csv_path

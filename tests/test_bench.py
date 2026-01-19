import json

from kokoro_stream.bench.results import write_results
from kokoro_stream.bench.scenarios import (
    run_concurrency,
    run_ttfa_comparison,
    running_service,
    summarize_concurrency,
    summarize_ttfa,
)
from kokoro_stream.config import Settings
from kokoro_stream.engine.sine import SineEngine

PROMPTS = {
    "short": "A short sentence for the benchmark.",
    "medium": "The first sentence is short. The second sentence is a little longer than the first. The third one finishes the paragraph.",
}


def make_settings():
    return Settings(default_voice="sine_mid", warmup=False, chunk_cache_mb=0, first_chunk_chars=40, max_chunk_chars=100)


def test_ttfa_comparison_rows_and_summary():
    engine = SineEngine(latency_per_char=0.0004)
    with running_service(make_settings(), engine) as url:
        rows = run_ttfa_comparison(url, PROMPTS, repetitions=2, voice="sine_mid")
    assert len(rows) == 2 * 2 * 2
    assert {row["mode"] for row in rows} == {"full", "stream"}
    summary = summarize_ttfa(rows)
    medium_full = summary["medium/full"]["ttfa_ms_median"]
    medium_stream = summary["medium/stream"]["ttfa_ms_median"]
    assert medium_stream < medium_full


def test_concurrency_rows_and_summary():
    with running_service(make_settings(), SineEngine(latency_per_char=0.0002)) as url:
        rows = run_concurrency(url, PROMPTS["medium"], "medium", [1, 3], rounds=2, voice="sine_mid")
    assert len(rows) == (1 + 3) * 2
    assert all(row["error"] == "" for row in rows)
    summary = summarize_concurrency(rows)
    assert set(summary) == {"1", "3"}
    assert summary["3"]["streams"] == 6
    assert summary["3"]["errors"] == 0


def test_results_are_written_as_json_and_csv(tmp_path):
    rows = [{"scenario": "ttfa", "mode": "full", "ttfa_ms": 10.5}, {"scenario": "ttfa", "mode": "stream", "ttfa_ms": 2.5, "extra": 1}]
    json_path, csv_path = write_results(tmp_path, "sample", rows, {"k": 1}, {"engine": "sine"}, {"repetitions": 2})
    document = json.loads(json_path.read_text(encoding="utf-8"))
    assert document["summary"] == {"k": 1}
    assert document["host"]["logical_cores"] >= 1
    assert len(document["rows"]) == 2
    header = csv_path.read_text(encoding="utf-8").splitlines()[0]
    assert header == "scenario,mode,ttfa_ms,extra"

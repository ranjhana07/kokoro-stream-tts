from kokoro_stream.bench import report
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

TEXT = "A first sentence for the report. A second sentence follows it. A third sentence ends it."


def settings():
    return Settings(default_voice="sine_mid", warmup=False, chunk_cache_mb=0, first_chunk_chars=40, max_chunk_chars=100)


def test_ttfa_report_has_one_row_per_prompt_and_mode(tmp_path):
    with running_service(settings(), SineEngine()) as url:
        rows = run_ttfa_comparison(url, {"short": TEXT}, 2, "sine_mid")
    path, _ = write_results(tmp_path, "ttfa-test", rows, summarize_ttfa(rows), {"engine": "sine"}, {"model_file": "none"})
    text = report.render(report.load(path))
    assert "| short | full | 2 |" in text
    assert "| short | stream | 2 |" in text
    assert text.startswith("ttfa-test:")
    assert "engine=sine" in text


def test_concurrency_report_lists_stream_counts_in_numeric_order(tmp_path):
    with running_service(settings(), SineEngine()) as url:
        rows = run_concurrency(url, TEXT, "short", [10, 2], 1, "sine_mid")
    path, _ = write_results(tmp_path, "conc-test", rows, summarize_concurrency(rows), {"engine": "sine"}, {})
    text = report.render(report.load(path))
    lines = [line for line in text.splitlines() if line.startswith("| ") and line[2].isdigit()]
    assert [line.split("|")[1].strip() for line in lines] == ["2", "10"]
    assert "ttfa p95 ms" in text


def test_main_prints_every_file(tmp_path, capsys):
    rows = [{"scenario": "ttfa", "prompt": "p", "mode": "stream", "ttfa_ms": 5.0}]
    summary = {"p/stream": {"runs": 1, "ttfa_ms_median": 5.0, "ttfa_ms_min": 5.0, "ttfa_ms_max": 5.0}}
    first, _ = write_results(tmp_path, "one", rows, summary, {}, {})
    second, _ = write_results(tmp_path, "two", rows, summary, {}, {})
    assert report.main([str(first), str(second)]) == 0
    output = capsys.readouterr().out
    assert "one:" in output and "two:" in output

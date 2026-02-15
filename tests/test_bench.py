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


def test_cli_runs_a_sine_scenario_and_writes_files(tmp_path, capsys):
    from kokoro_stream.bench.cli import main

    prompts = tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "tiny.txt").write_text("One short line.\nAnd a second line right after it.\n", encoding="utf-8")
    code = main(
        [
            "--scenario", "ttfa", "--engine", "sine", "--name", "cli-test",
            "--out-dir", str(tmp_path / "out"), "--prompts-dir", str(prompts),
            "--prompts", "tiny", "--repetitions", "1",
        ]
    )
    assert code == 0
    assert (tmp_path / "out" / "cli-test.json").exists()
    assert (tmp_path / "out" / "cli-test.csv").exists()
    assert "tiny/stream" in capsys.readouterr().out


def test_settings_from_args_applies_overrides():
    from kokoro_stream.bench.cli import build_parser, settings_from_args

    args = build_parser().parse_args(
        ["--scenario", "ttfa", "--name", "x", "--engine", "sine", "--depth", "5", "--workers", "9", "--first-chunk-chars", "30", "--no-trim"]
    )
    settings = settings_from_args(args)
    assert (settings.prefetch_depth, settings.prefetch_workers, settings.first_chunk_chars) == (5, 9, 30)
    assert settings.trim_silence is False
    assert settings.chunk_cache_mb == 0
    assert settings.max_streams == 0


def test_cache_is_only_enabled_on_request():
    from kokoro_stream.bench.cli import build_parser, settings_from_args

    args = build_parser().parse_args(["--scenario", "ttfa", "--name", "x", "--engine", "sine", "--cache"])
    assert settings_from_args(args).chunk_cache_mb > 0


def test_ttfa_modes_can_be_limited_to_streaming():
    with running_service(make_settings(), SineEngine()) as url:
        rows = run_ttfa_comparison(url, {"short": PROMPTS["short"]}, repetitions=2, voice="sine_mid", modes=("stream",))
    assert {row["mode"] for row in rows} == {"stream"}
    assert len(rows) == 2

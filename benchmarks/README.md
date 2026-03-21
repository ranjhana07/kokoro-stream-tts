# Benchmarks

`prompts/` holds the three texts used by the runs (`short`, `medium`, `long`). `results/` holds one JSON and one CSV per run.

Every JSON file contains the host description (CPU model, logical cores, OS, Python, numpy, onnxruntime, flask and the CPU utilization measured right before the run), the full service settings, the command line arguments, a summary and every raw row. The CSV has the same rows for spreadsheets.

| File | Scenario |
|------|----------|
| `ttfa-full-vs-stream.*` | time to first audio of `POST /v1/tts` against `POST /v1/tts/stream`, three prompts, three repetitions |
| `concurrency-medium.*` | 1, 5, 10 and 25 streams started together, medium prompt |
| `ablation-*.*` | streaming only, medium prompt, five repetitions, one setting changed at a time |

Render any of them as markdown:

```
python -m kokoro_stream.bench.report benchmarks/results/concurrency-medium.json
```

Rerun a scenario with `python -m kokoro_stream.bench --help` for the options. The chunk cache is off unless `--cache` is passed, otherwise repeated prompts would measure cache hits. On a shared machine pass `--high-priority` and check `cpu_utilization_before_run_percent` in the result before trusting the absolute numbers.

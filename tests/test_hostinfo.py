from kokoro_stream.bench import hostinfo


def test_collect_has_the_fields_the_readme_reports():
    info = hostinfo.collect()
    for key in ("cpu", "logical_cores", "os", "python", "numpy", "onnxruntime"):
        assert key in info
    assert info["logical_cores"] >= 1
    assert info["cpu"]


def test_cpu_utilization_is_a_percentage_or_unknown():
    value = hostinfo.cpu_utilization(0.05)
    assert value is None or 0.0 <= value <= 100.0


def test_raise_priority_reports_success_or_failure():
    assert isinstance(hostinfo.raise_priority(), bool)

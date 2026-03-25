import tomllib
from pathlib import Path

from kokoro_stream import __version__
from kokoro_stream.config import Settings
from kokoro_stream.engine.sine import SineEngine
from kokoro_stream.service.app import create_app


def test_package_and_project_versions_agree():
    root = Path(__file__).resolve().parents[1]
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert project["version"] == __version__


def test_healthz_reports_the_version():
    client = create_app(Settings(default_voice="sine_mid"), SineEngine()).test_client()
    assert client.get("/healthz").json["version"] == __version__

"""Web layer tests. Skip cleanly if the [web] extra isn't installed —
the core suite must remain runnable in a zero-dependency environment."""

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from foundry import __version__  # noqa: E402
from foundry import webauth  # noqa: E402
from foundry.mission_control import _test_count  # noqa: E402
from foundry.web import app  # noqa: E402


@pytest.fixture(autouse=True)
def auth_env(monkeypatch, tmp_path):
    """Pages require a session; mint one for these tests. Each test
    gets its own (empty) event log so no state leaks between them."""
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "test-publishable-key")
    monkeypatch.setenv("FOUNDRY_ALLOWED_EMAIL", "cparkerbrads@gmail.com")
    monkeypatch.setenv("SESSION_SECRET", "unit-test-secret-0123456789abcdef")
    monkeypatch.setenv("APP_BASE_URL", "http://testserver")
    monkeypatch.setenv("FOUNDRY_DATA_PATH", str(tmp_path / "events.jsonl"))


def client() -> TestClient:
    c = TestClient(app)
    c.cookies.set(webauth.SESSION_COOKIE, webauth.session_token(
        "cparkerbrads@gmail.com", webauth.load_config()))
    return c


def test_health_returns_ok_json():
    r = TestClient(app).get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["service"] == "foundry"
    assert body["version"] == __version__


def test_home_renders_mission_control_even_on_an_empty_log():
    """A fresh deployment with zero events must render, honestly empty
    — the graceful degenerate case, not an error page."""
    r = client().get("/")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    html = r.text
    assert "MISSION CONTROL" in html
    assert "FLIGHT PLAN" in html
    assert "NO ACTIVE MISSION" in html
    assert "HASH CHAIN OK" in html  # the system-health footer is always present


def test_home_reports_real_test_count():
    n = _test_count()
    assert n is not None and n >= 1
    assert f">{n}<" in client().get("/").text  # the TESTS footer item


def test_security_headers_on_authenticated_pages():
    r = client().get("/")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["Referrer-Policy"] == "no-referrer"
    assert "default-src 'none'" in r.headers["Content-Security-Policy"]
    assert r.headers["Cache-Control"] == "no-store"
    # /health stays cacheable for the platform health checker:
    health = TestClient(app).get("/health")
    assert health.headers.get("Cache-Control") != "no-store"


def test_core_import_does_not_require_fastapi():
    """The invariant: importing foundry must not import the web layer.
    The child interpreter is pointed at the same package location this
    test imported foundry from, so the check also passes in
    path-injected (non-installed) environments."""
    import subprocess, sys
    from pathlib import Path

    import foundry
    src_dir = str(Path(foundry.__file__).resolve().parents[1])
    code = (
        "import sys; import foundry; "
        "sys.exit(1 if 'fastapi' in sys.modules else 0)"
    )
    # cwd, not PYTHONPATH: `python -c` puts the working directory on
    # sys.path, and unlike PYTHONPATH it survives directory names
    # containing path-separator characters.
    assert subprocess.run([sys.executable, "-c", code], cwd=src_dir).returncode == 0

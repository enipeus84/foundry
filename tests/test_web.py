"""Web layer tests. Skip cleanly if the [web] extra isn't installed —
the core suite must remain runnable in a zero-dependency environment."""

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from foundry import __version__  # noqa: E402
from foundry import webauth  # noqa: E402
from foundry.web import app, _test_count  # noqa: E402


@pytest.fixture(autouse=True)
def auth_env(monkeypatch):
    """The status page now requires a session; mint one for these tests."""
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "test-publishable-key")
    monkeypatch.setenv("FOUNDRY_ALLOWED_EMAIL", "cparkerbrads@gmail.com")
    monkeypatch.setenv("SESSION_SECRET", "unit-test-secret-0123456789abcdef")
    monkeypatch.setenv("APP_BASE_URL", "http://testserver")


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


def test_status_page_renders():
    r = client().get("/")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    html = r.text
    assert f"Foundry V{__version__}" in html
    assert "Durable organisational intelligence across AI models" in html
    assert "System operational" in html
    assert "docs/architecture.md" in html
    assert "RUNBOOK_V1.md" in html
    assert "docs/roadmap.md" in html


def test_status_page_reports_real_test_count():
    n = _test_count()
    assert n is not None and n >= 1
    assert f"{n} passing" in client().get("/").text


def test_core_import_does_not_require_fastapi():
    """The invariant: importing foundry must not import the web layer."""
    import subprocess, sys
    code = (
        "import sys; import foundry; "
        "sys.exit(1 if 'fastapi' in sys.modules else 0)"
    )
    assert subprocess.run([sys.executable, "-c", code]).returncode == 0

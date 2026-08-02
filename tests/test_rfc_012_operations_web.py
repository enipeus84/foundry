"""RFC-012 Phase 1B Operations Console security and parity tests."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from foundry import webauth  # noqa: E402
from foundry.web import app  # noqa: E402


ALLOWED = "cparkerbrads@gmail.com"


@pytest.fixture(autouse=True)
def environment(monkeypatch, tmp_path):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "test-key")
    monkeypatch.setenv("FOUNDRY_ALLOWED_EMAIL", ALLOWED)
    monkeypatch.setenv("SESSION_SECRET", "unit-test-secret-0123456789abcdef")
    monkeypatch.setenv("APP_BASE_URL", "http://testserver")
    monkeypatch.setenv("FOUNDRY_DATA_PATH", str(tmp_path / "events.jsonl"))
    monkeypatch.setenv("FOUNDRY_EVIDENCE_VAULT_PATH", str(tmp_path / "vault"))


def _client() -> TestClient:
    client = TestClient(app, follow_redirects=False)
    client.cookies.set(webauth.SESSION_COOKIE,
                       webauth.session_token(ALLOWED, webauth.load_config()))
    return client


def test_operations_console_requires_authentication():
    assert TestClient(app, follow_redirects=False).get("/operations").status_code == 303


def test_operations_capture_requires_body_only_signed_csrf():
    client = _client()
    assert client.post("/operations/capture", params={"csrf": "forged"}).status_code == 403
    csrf = webauth.csrf_token(ALLOWED, webauth.load_config(), "rfc012-capture")
    assert client.post("/operations/capture", params={"csrf": csrf}).status_code == 403


def test_existing_acquisition_inbox_remains_available():
    response = _client().get("/acquisition/inbox")
    assert response.status_code == 200
    assert "ACQUISITION INBOX" in response.text

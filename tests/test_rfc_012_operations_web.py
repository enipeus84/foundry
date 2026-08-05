"""RFC-012 Phase 1B Operations Console security and parity tests."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from foundry import webauth  # noqa: E402
from foundry.core.acquisition import ProposalInbox, TelemetryStream, TelemetryStreamRegistry  # noqa: E402
from foundry.core.entities import declare_party  # noqa: E402
from foundry.eventlog import EventLog  # noqa: E402
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


def test_guided_capture_uses_application_shell_and_existing_confirmation_gate(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    household = declare_party(log, "household")
    TelemetryStreamRegistry(log).declare(TelemetryStream(
        id="brokerage-units", subject_id="holding-1", property="units", channel="manual",
        refresh_policy="monthly", confirmation_policy="review_each",
        source_identity="user:reviewer", unit_or_currency="GBP",
        validation_contract="numeric", household_id=household.id,
        expected_cadence="monthly"))
    client = _client()
    dashboard = client.get("/operations")
    assert dashboard.status_code == 200
    assert "FOUNDRY · OPERATIONS" in dashboard.text
    assert 'href="/operations" class="active"' in dashboard.text
    assert "CAPTURE NEW INFORMATION" in dashboard.text

    capture = client.get("/operations/capture")
    assert capture.status_code == 200
    assert "What do you want to record?" in capture.text
    assert "Record an investment purchase, sale or RSU vest" in capture.text
    assert "TECHNICAL DETAILS" in capture.text
    csrf = webauth.csrf_token(ALLOWED, webauth.load_config(), "rfc012-capture")
    submitted = client.post("/operations/capture", data={
        "csrf": csrf, "mode": "guided", "stream_id": "brokerage-units",
        "value": "12.5", "valid_at": "2026-08-05", "external_ref": "trade-123",
    })
    assert submitted.status_code == 303
    assert submitted.headers["location"] == "/acquisition/inbox"

    proposal = next(iter(ProposalInbox(log).proposals.values()))
    assert proposal.observations[0]["subject_id"] == "holding-1"
    assert proposal.draft_events[0] == {"kind": "finance.position.updated", "payload": {
        "entity_id": "holding-1", "quantity": 12.5, "valuation_date": 1_785_888_000.0,
    }}
    assert not any(event["kind"].startswith("finance.") for event in log.events())


def test_retired_manual_streams_are_absent_from_guided_and_technical_selection(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    household = declare_party(log, "household")
    TelemetryStreamRegistry(log).declare(TelemetryStream(
        id="retired-units", subject_id="holding-1", property="units", channel="manual",
        refresh_policy="monthly", confirmation_policy="review_each",
        source_identity="user:reviewer", unit_or_currency="GBP",
        validation_contract="numeric", household_id=household.id,
        expected_cadence="monthly"))
    log.append("core.telemetry_stream.retired", {
        "stream_id": "retired-units", "reason": "superseded", "retired_at": 1.0,
    })

    response = _client().get("/operations/capture")
    assert response.status_code == 200
    assert "Record an investment purchase, sale or RSU vest" not in response.text
    assert "retired-units" not in response.text

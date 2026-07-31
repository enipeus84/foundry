"""Authenticated RFC-011 confirmation inbox regression tests."""

from __future__ import annotations

from itertools import count

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from foundry import webauth  # noqa: E402
from foundry.core.acquisition import TelemetryStream, TelemetryStreamRegistry  # noqa: E402
from foundry.core.entities import declare_party  # noqa: E402
from foundry.eventlog import EventLog  # noqa: E402
from foundry.web import app  # noqa: E402


ALLOWED = "cparkerbrads@gmail.com"


@pytest.fixture(autouse=True)
def environment(monkeypatch, tmp_path):
    clock = count(2_000.0)
    monkeypatch.setattr("foundry.eventlog.time.time", clock.__next__)
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "test-key")
    monkeypatch.setenv("FOUNDRY_ALLOWED_EMAIL", ALLOWED)
    monkeypatch.setenv("SESSION_SECRET", "unit-test-secret-0123456789abcdef")
    monkeypatch.setenv("APP_BASE_URL", "http://testserver")
    monkeypatch.setenv("FOUNDRY_DATA_PATH", str(tmp_path / "events.jsonl"))
    return tmp_path


def _client() -> TestClient:
    client = TestClient(app, follow_redirects=False)
    client.cookies.set(webauth.SESSION_COOKIE, webauth.session_token(ALLOWED, webauth.load_config()))
    return client


def _pending_proposal(path):
    log = EventLog(path / "events.jsonl")
    household = declare_party(log, "household")
    streams = TelemetryStreamRegistry(log)
    streams.declare(TelemetryStream(
        id="units", subject_id="holding", property="units", channel="manual",
        refresh_policy="monthly", confirmation_policy="review_each",
        source_identity="user:reviewer", unit_or_currency="GBP",
        validation_contract="numeric", household_id=household.id,
        expected_cadence="monthly"))
    log.append("core.telemetry_envelope.declared", {
        "id": "envelope-1", "stream_id": "units", "channel": "manual",
        "source_identity": "user:reviewer", "received_at": 1_990.0,
        "payload_hash": "a" * 64, "payload_ref": "vault:" + "a" * 64,
        "payload_media_type": "application/json", "external_ref": "statement-1",
        "evidence_grade": "declared"})
    log.append("core.observation_proposal.declared", {
        "id": "proposal-1", "evidence_id": "a" * 64, "envelope_id": "envelope-1",
        "household_id": household.id, "interpreter_id": "manual-json",
        "interpreter_version": "1", "interpreter_class": "deterministic",
        "stream_id": "units", "draft_events": [{"kind": "finance.position.updated",
            "payload": {"entity_id": "holding", "quantity": 4.0}}],
        "observations": [{"stream_id": "units", "subject_id": "holding", "kind": "units",
            "value": 4.0, "valid_at": 1_980.0, "observed_at": 1_981.0,
            "external_document_ref": "statement-1"}], "resolutions": [],
        "evidence_grade": "declared", "notes": "<script>hostile</script>"})
    return log


def test_inbox_requires_session_csrf_escapes_content_and_confirms(environment):
    log = _pending_proposal(environment)
    anonymous = TestClient(app, follow_redirects=False)
    assert anonymous.get("/acquisition/inbox").status_code == 303
    client = _client()
    page = client.get("/acquisition/inbox")
    assert page.status_code == 200
    assert "ACQUISITION INBOX" in page.text
    assert "&lt;script&gt;" not in page.text  # notes are not rendered as trusted HTML
    assert client.post("/acquisition/proposals/proposal-1/confirm").status_code == 403
    csrf = webauth.csrf_token(ALLOWED, webauth.load_config(), "rfc011-confirmation")
    confirmed = client.post("/acquisition/proposals/proposal-1/confirm", params={"csrf": csrf})
    assert confirmed.status_code == 303
    assert any(event["kind"] == "finance.position.updated" for event in log.events())
    assert any(event["kind"] == "core.observation_proposal.updated" and
               event["payload"]["resolution"] == "confirmed" for event in log.events())


def test_inbox_rejects_cross_household_proposal(environment):
    log = _pending_proposal(environment)
    for event in log.events():
        if event["kind"] == "core.observation_proposal.declared":
            proposal_id = event["payload"]["id"]
            break
    else:  # pragma: no cover - fixture contract
        raise AssertionError("proposal missing")
    # A second household proposal is not discoverable through the current scope.
    log.append("core.observation_proposal.declared", {
        "id": "other-proposal", "evidence_id": "b" * 64, "envelope_id": "missing",
        "household_id": "other", "interpreter_id": "manual-json", "interpreter_version": "1",
        "interpreter_class": "deterministic", "stream_id": "units", "draft_events": [],
        "observations": [], "resolutions": [], "evidence_grade": "declared"})
    csrf = webauth.csrf_token(ALLOWED, webauth.load_config(), "rfc011-confirmation")
    response = _client().post("/acquisition/proposals/other-proposal/reject", params={"csrf": csrf})
    assert response.status_code == 404
    assert proposal_id == "proposal-1"

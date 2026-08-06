"""Authenticated RFC-011 confirmation inbox regression tests."""

from __future__ import annotations

from itertools import count
from copy import deepcopy

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from foundry import webauth  # noqa: E402
from foundry.core.acquisition import (  # noqa: E402
    AssetRegistration, AssetRegistry, EvidenceVault, TelemetryStream, TelemetryStreamRegistry,
)
from foundry.core.entities import declare_party  # noqa: E402
from foundry.eventlog import EventLog  # noqa: E402
from foundry.finance import entities as finance  # noqa: E402
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
    monkeypatch.setenv("FOUNDRY_EVIDENCE_VAULT_PATH", str(tmp_path / "vault"))
    return tmp_path


def _client() -> TestClient:
    client = TestClient(app, follow_redirects=False)
    client.cookies.set(webauth.SESSION_COOKIE, webauth.session_token(ALLOWED, webauth.load_config()))
    return client


def _pending_proposal(path, payload=None):
    log = EventLog(path / "events.jsonl")
    vault = EvidenceVault(path / "vault", authorized=lambda actor: actor == ALLOWED)
    payload = payload or b'{"evidence_marker":"captured evidence for proposal-1","observations":[{"quantity":4.0}]}'
    payload_hash, payload_ref = vault.put(payload, ALLOWED)
    household = declare_party(log, "household")
    account = finance.declare_account(log, "checking", "GBP", name="Canonical account")
    AssetRegistry(log, entity_exists=lambda subject_id: subject_id == account.id).register(
        AssetRegistration(account.id, "finance", household.id))
    streams = TelemetryStreamRegistry(log)
    streams.declare(TelemetryStream(
        id="units", subject_id=account.id, property="units", channel="manual",
        refresh_policy="monthly", confirmation_policy="review_each",
        source_identity="user:reviewer", unit_or_currency="GBP",
        validation_contract="numeric", household_id=household.id,
        expected_cadence="monthly"))
    log.append("core.telemetry_envelope.declared", {
        "id": "envelope-1", "stream_id": "units", "channel": "manual",
        "source_identity": "user:reviewer", "received_at": 1_990.0,
        "payload_hash": payload_hash, "payload_ref": payload_ref,
        "payload_media_type": "application/json", "external_ref": "statement-1",
        "evidence_grade": "declared"})
    log.append("core.observation_proposal.declared", {
        "id": "proposal-1", "evidence_id": payload_hash, "envelope_id": "envelope-1",
        "household_id": household.id, "interpreter_id": "manual-json",
        "interpreter_version": "1", "interpreter_class": "deterministic",
        "stream_id": "units", "draft_events": [{"kind": "finance.account.reconciliation_observed",
            "payload": {"entity_id": account.id, "supplied_total": 4.0}}],
        "observations": [{"stream_id": "units", "subject_id": account.id, "kind": "units",
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
    assert "?csrf=" not in page.text
    assert 'name="csrf"' in page.text
    assert client.post("/acquisition/proposals/proposal-1/confirm").status_code == 403
    csrf = webauth.csrf_token(ALLOWED, webauth.load_config(), "rfc011-confirmation")
    assert client.post("/acquisition/proposals/proposal-1/confirm", params={"csrf": csrf}).status_code == 403
    confirmed = client.post("/acquisition/proposals/proposal-1/confirm", data={"csrf": csrf})
    assert confirmed.status_code == 303
    assert confirmed.headers["location"] == "/acquisition/proposals/proposal-1/provenance"
    provenance = client.get(confirmed.headers["location"])
    assert provenance.status_code == 200
    assert "manual-json" in provenance.text and "evidence" in provenance.text
    assert any(event["kind"] == "finance.account.reconciliation_observed" for event in log.events())
    assert any(event["kind"] == "core.observation_proposal.updated" and
               event["payload"]["resolution"] == "confirmed" for event in log.events())


def test_retired_target_is_hidden_from_action_queue_but_historical_evidence_survives(environment):
    log = _pending_proposal(environment)
    log.append("core.telemetry_stream.retired", {
        "stream_id": "units", "reason": "account closed", "retired_at": 2_001.0,
    })
    client = _client()
    csrf = webauth.csrf_token(ALLOWED, webauth.load_config(), "rfc011-confirmation")

    inbox = client.get("/acquisition/inbox")
    confirmation = client.post("/acquisition/proposals/proposal-1/confirm", data={"csrf": csrf})
    evidence = client.get("/acquisition/proposals/proposal-1/evidence")

    assert "proposal-1" not in inbox.text
    assert confirmation.status_code == 409
    assert "proposal target is retired" in confirmation.text
    assert evidence.status_code == 200
    assert any(event["kind"] == "core.telemetry_stream.retired" for event in log.events())
    assert any(event["kind"] == "core.observation_proposal.declared" for event in log.events())


def test_evidence_preview_reads_authorized_vault_artifact_and_fails_closed(environment):
    _pending_proposal(environment)
    anonymous = TestClient(app, follow_redirects=False)
    assert anonymous.get("/acquisition/proposals/proposal-1/evidence").status_code == 303
    preview = _client().get("/acquisition/proposals/proposal-1/evidence")
    assert preview.status_code == 200
    assert "captured evidence for proposal-1" in preview.text
    assert "Evidence identifier" in preview.text


def test_evidence_preview_redacts_legacy_credential_values(environment):
    _pending_proposal(environment, b'{"note":"credentials=opaque-credential","observations":[]}')
    preview = _client().get("/acquisition/proposals/proposal-1/evidence")
    assert preview.status_code == 200
    assert "opaque-credential" not in preview.text
    assert "[redacted]" in preview.text


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
    response = _client().post("/acquisition/proposals/other-proposal/reject", data={"csrf": csrf})
    assert response.status_code == 404
    assert proposal_id == "proposal-1"


def test_confirmation_refuses_an_unknown_subject_identifier(environment):
    log = _pending_proposal(environment)
    declared = next(event for event in log.events()
                    if event["kind"] == "core.observation_proposal.declared")
    payload = deepcopy(declared["payload"])
    payload["id"] = "unknown-subject-proposal"
    payload["draft_events"][0]["payload"]["entity_id"] = "unknown-subject"
    payload["observations"][0]["subject_id"] = "unknown-subject"
    log.append("core.observation_proposal.declared", payload)
    csrf = webauth.csrf_token(ALLOWED, webauth.load_config(), "rfc011-confirmation")
    assert _client().post("/acquisition/proposals/unknown-subject-proposal/confirm",
                          data={"csrf": csrf}).status_code == 404
    assert not any(event["kind"] == "core.observation_proposal.updated"
                   and event["payload"].get("entity_id") == "unknown-subject-proposal"
                   for event in log.events())


def test_confirmation_refuses_a_subject_registered_to_another_household(environment):
    log = _pending_proposal(environment)
    other_household = declare_party(log, "household")
    other_account = finance.declare_account(log, "checking", "GBP", name="Other household")
    AssetRegistry(log, entity_exists=lambda subject_id: subject_id == other_account.id).register(
        AssetRegistration(other_account.id, "finance", other_household.id))
    declared = next(event for event in log.events()
                    if event["kind"] == "core.observation_proposal.declared")
    payload = deepcopy(declared["payload"])
    payload["id"] = "cross-household-subject-proposal"
    payload["draft_events"][0]["payload"]["entity_id"] = other_account.id
    payload["observations"][0]["subject_id"] = other_account.id
    log.append("core.observation_proposal.declared", payload)
    csrf = webauth.csrf_token(ALLOWED, webauth.load_config(), "rfc011-confirmation")
    assert _client().post("/acquisition/proposals/cross-household-subject-proposal/confirm",
                          data={"csrf": csrf}).status_code == 404

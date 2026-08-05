"""RFC-013 capture-contract discovery and acquisition-boundary tests."""

from __future__ import annotations

from itertools import count

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from foundry import webauth  # noqa: E402
from foundry.capture_contracts import (  # noqa: E402
    CanonicalMapper, CaptureContract, CaptureContractRegistry, CaptureField,
    CaptureValidation, EvidencePolicy, capture_contract_registry,
)
from foundry.core.acquisition import (  # noqa: E402
    AcquisitionError, ProposalInbox, TelemetryStream, TelemetryStreamRegistry,
)
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
    monkeypatch.setenv("FOUNDRY_EVIDENCE_VAULT_PATH", str(tmp_path / "vault"))
    return tmp_path


def _client() -> TestClient:
    client = TestClient(app, follow_redirects=False)
    client.cookies.set(webauth.SESSION_COOKIE, webauth.session_token(ALLOWED, webauth.load_config()))
    return client


def test_three_production_contracts_are_discovered_with_complete_metadata():
    contracts = capture_contract_registry().discover()
    assert [contract.identifier for contract in contracts] == [
        "cash-balance-update", "pension-balance-update", "property-valuation-update",
    ]
    for contract in contracts:
        assert contract.version and contract.display_name and contract.description
        assert contract.capabilities and contract.schema and contract.validation
        assert contract.review_template and contract.evidence_policy and contract.canonical_mapper


def test_fourth_contract_is_a_registry_change_not_an_operations_change():
    fourth = CaptureContract(
        identifier="test-fourth-capture", version="1", display_name="Fourth Capture",
        description="A test extension.", capabilities=("manual_capture",),
        schema=(CaptureField("amount", "Amount", "number"),
                CaptureField("currency", "Currency", "text"),
                CaptureField("valid_at", "As at", "number")),
        validation=CaptureValidation(), review_template="Review {subject_id}",
        evidence_policy=EvidencePolicy.NONE,
        canonical_mapper=CanonicalMapper("finance.account.reconciliation_observed", "test_value", {
            "entity_id": "$subject_id", "supplied_total": "$amount", "valid_at": "$valid_at",
        }), stream_properties=("test_value",),
    )
    registry = CaptureContractRegistry(capture_contract_registry().discover())
    registry.register(fourth)
    assert registry.get("test-fourth-capture") is fourth
    assert [item.identifier for item in registry.discover()][-1] == "test-fourth-capture"


def test_required_evidence_and_canonical_mapping_are_contract_owned():
    contract = capture_contract_registry().get("property-valuation-update")
    assert contract is not None
    with pytest.raises(ValueError):
        contract.draft({"amount": "450000", "currency": "GBP", "valid_at": "100"},
                       subject_id="property-1", capture_id="capture-1")
    with pytest.raises(AcquisitionError, match="requires an evidence reference"):
        contract.draft({"amount": "450000", "currency": "GBP", "valid_at": "100",
                        "evidence_reference": ""}, subject_id="property-1", capture_id="capture-1")
    fact = contract.draft({"amount": "450000", "currency": "gbp", "valid_at": "100",
                           "evidence_reference": "valuation-2026"},
                          subject_id="property-1", capture_id="capture-1")
    assert fact["canonical_event"] == {"kind": "finance.valuation.declared", "payload": {
        "entity_id": "capture-1", "subject_id": "property-1", "amount": 450000.0,
        "currency": "GBP", "as_of": 100.0,
    }}
    cash = capture_contract_registry().get("cash-balance-update")
    assert cash is not None
    assert cash.draft({"amount": "1200", "currency": "GBP", "valid_at": "100"},
                      subject_id="cash-1", capture_id="capture-2")["canonical_event"]["kind"] == (
        "finance.account.reconciliation_observed")


def test_operations_discovers_contracts_and_creates_an_inert_property_draft(environment):
    log = EventLog(environment / "events.jsonl")
    household = declare_party(log, "household")
    streams = TelemetryStreamRegistry(log)
    streams.declare(TelemetryStream(
        id="property-value", subject_id="property-1", property="property_valuation",
        channel="manual", refresh_policy="annual", confirmation_policy="review_each",
        source_identity="user:reviewer", unit_or_currency="GBP", validation_contract="numeric",
        household_id=household.id, expected_cadence="annual"))
    client = _client()
    chooser = client.get("/operations/capture")
    assert chooser.status_code == 200
    assert "WHAT DO YOU WANT TO RECORD?" in chooser.text
    assert "Pension Balance Update" in chooser.text
    form = client.get("/operations/capture?contract=property-valuation-update")
    assert form.status_code == 200 and "Canonical event" not in form.text
    csrf = webauth.csrf_token(ALLOWED, webauth.load_config(), "rfc013-capture")
    created = client.post("/operations/capture", data={
        "csrf": csrf, "contract_id": "property-valuation-update", "stream_id": "property-value",
        "amount": "450000", "currency": "GBP", "valid_at": "1700000000",
        "evidence_reference": "valuer-report-2026",
    })
    assert created.status_code == 303 and created.headers["location"] == "/acquisition/inbox"
    assert not any(event["kind"].startswith("finance.") for event in log.events())
    proposal = next(iter(ProposalInbox(log).proposals.values()))
    assert proposal.draft_events[0]["kind"] == "finance.valuation.declared"
    assert proposal.state == "pending"
    confirmed = client.post(f"/acquisition/proposals/{proposal.id}/confirm", data={
        "csrf": webauth.csrf_token(ALLOWED, webauth.load_config(), "rfc011-confirmation"),
    })
    assert confirmed.status_code == 303
    assert any(event["kind"] == "finance.valuation.declared" for event in log.events())

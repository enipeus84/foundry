"""RFC-013 capture-contract discovery and acquisition-boundary tests."""

from __future__ import annotations

from itertools import count

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from foundry import webauth  # noqa: E402
from foundry.acquisition_web import _timestamp  # noqa: E402
from foundry.capture_contracts import (  # noqa: E402
    CanonicalMapper, CaptureContract, CaptureContractRegistry, CaptureField,
    CaptureValidation, EvidencePolicy, capture_contract_registry,
)
from foundry.core.acquisition import (  # noqa: E402
    AcquisitionError, ProposalInbox, TelemetryStream, TelemetryStreamRegistry,
)
from foundry.core.entities import declare_party  # noqa: E402
from foundry.core.entities import EntityProjection, join_household  # noqa: E402
from foundry.core.metrics import MetricRegistry, MetricRequest  # noqa: E402
from foundry.core.scope import Subject  # noqa: E402
from foundry.eventlog import EventLog  # noqa: E402
from foundry.finance import entities as finance  # noqa: E402
from foundry.finance.entities import FinanceEntityProjection  # noqa: E402
from foundry.finance.metrics import FinanceMetricProvider  # noqa: E402
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


def test_contract_without_a_stream_property_fails_closed():
    with pytest.raises(ValueError, match="stream property"):
        CaptureContract(
            identifier="unsafe-capture", version="1", display_name="Unsafe",
            description="Must not accept all streams.", capabilities=("manual_capture",),
            schema=(CaptureField("amount", "Amount", "number"),
                    CaptureField("currency", "Currency", "text"),
                    CaptureField("valid_at", "As at", "number")),
            validation=CaptureValidation(), review_template="Review {subject_id}",
            evidence_policy=EvidencePolicy.NONE,
            canonical_mapper=CanonicalMapper("finance.account.reconciliation_observed", "test_value", {
                "entity_id": "$subject_id", "supplied_total": "$amount", "valid_at": "$valid_at",
            }),
        )


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
    assert "does not update Finance balances" in cash.description
    assert "not currently consumed by the RFC-011 reconciliation lens" in cash.description
    assert cash.draft({"amount": "1200", "currency": "GBP", "valid_at": "100"},
                      subject_id="cash-1", capture_id="capture-2")["canonical_event"]["kind"] == (
        "finance.account.reconciliation_observed")
    for timestamp in ("-1", "253402300800", "1e300"):
        with pytest.raises(AcquisitionError, match="timestamp"):
            cash.draft({"amount": "1200", "currency": "GBP", "valid_at": timestamp},
                       subject_id="cash-1", capture_id="capture-2")


def test_inbox_timestamp_rendering_rejects_unrenderable_stored_values():
    assert _timestamp(1e300) == "Invalid timestamp"


def _capture_streams(path):
    log = EventLog(path / "events.jsonl")
    household = declare_party(log, "household")
    streams = TelemetryStreamRegistry(log)
    for identifier, subject_id, property_name in (
        ("pension-value", "pension-1", "pension_balance"),
        ("cash-value", "cash-1", "cash_balance"),
        ("property-value", "property-1", "property_valuation"),
    ):
        streams.declare(TelemetryStream(
            id=identifier, subject_id=subject_id, property=property_name,
            channel="manual", refresh_policy="annual", confirmation_policy="review_each",
            source_identity="user:reviewer", unit_or_currency="GBP", validation_contract="numeric",
            household_id=household.id, expected_cadence="annual"))
    return log


def _submit_capture(client, contract_id, stream_id, *, amount="450000", valid_at="1700000000",
                    evidence_reference=None):
    data = {
        "csrf": webauth.csrf_token(ALLOWED, webauth.load_config(), "rfc013-capture"),
        "contract_id": contract_id, "stream_id": stream_id,
        "amount": amount, "currency": "GBP", "valid_at": valid_at,
    }
    if evidence_reference is not None:
        data["evidence_reference"] = evidence_reference
    return client.post("/operations/capture", data=data)


@pytest.mark.parametrize(("contract_id", "stream_id", "evidence_reference"), [
    ("pension-balance-update", "pension-value", "pension-statement-2026"),
    ("cash-balance-update", "cash-value", "cash-statement-2026"),
    ("property-valuation-update", "property-value", "valuer-report-2026"),
])
def test_identical_contract_submissions_reuse_the_existing_envelope_and_proposal(
        environment, contract_id, stream_id, evidence_reference):
    log = _capture_streams(environment)
    client = _client()
    first = _submit_capture(client, contract_id, stream_id, evidence_reference=evidence_reference)
    second = _submit_capture(client, contract_id, stream_id, evidence_reference=evidence_reference)
    assert first.status_code == second.status_code == 303
    assert len(ProposalInbox(log).proposals) == 1
    assert sum(event["kind"] == "core.telemetry_envelope.declared" for event in log.events()) == 1
    assert not any(event["kind"].startswith("finance.") for event in log.events())


def test_changed_capture_values_dates_and_evidence_references_create_distinct_proposals(environment):
    log = _capture_streams(environment)
    client = _client()
    base = {"contract_id": "property-valuation-update", "stream_id": "property-value",
            "evidence_reference": "valuer-report-2026"}
    assert _submit_capture(client, **base).status_code == 303
    assert _submit_capture(client, **base, amount="451000").status_code == 303
    assert _submit_capture(client, **base, valid_at="1700000001").status_code == 303
    assert _submit_capture(client, **{**base, "evidence_reference": "valuer-report-reissue"}).status_code == 303
    assert len(ProposalInbox(log).proposals) == 4


def test_operations_discovers_contracts_and_creates_an_inert_property_draft(environment):
    log = _capture_streams(environment)
    client = _client()
    chooser = client.get("/operations/capture")
    assert chooser.status_code == 200
    assert "WHAT DO YOU WANT TO RECORD?" in chooser.text
    assert "Pension Balance Update" in chooser.text
    assert "evidence reference is recommended" in chooser.text.lower()
    assert "evidence reference is optional" in chooser.text.lower()
    form = client.get("/operations/capture?contract=property-valuation-update")
    assert form.status_code == 200 and "Canonical event" not in form.text
    created = _submit_capture(client, "property-valuation-update", "property-value",
                              evidence_reference="valuer-report-2026")
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
    duplicate = _submit_capture(client, "property-valuation-update", "property-value",
                                evidence_reference="valuer-report-2026")
    assert duplicate.status_code == 303
    assert len(ProposalInbox(log).proposals) == 1
    assert sum(event["kind"] == "finance.valuation.declared" for event in log.events()) == 1


def test_operations_reports_capture_as_unconfigured_only_without_contracts_or_guided_workflows(
        environment, monkeypatch):
    monkeypatch.setattr("foundry.operations_web.capture_contract_registry",
                        lambda: CaptureContractRegistry())
    declare_party(EventLog(environment / "events.jsonl"), "household")
    response = _client().get("/operations/capture")
    assert response.status_code == 200
    assert "Capture is not configured" in response.text


def test_operations_reports_contracts_without_compatible_targets_truthfully(environment):
    declare_party(EventLog(environment / "events.jsonl"), "household")
    response = _client().get("/operations/capture")
    assert response.status_code == 200
    assert "Capture Contracts are available" in response.text
    assert "no compatible Capture Targets are currently registered" in response.text
    assert "Capture is not configured" not in response.text


def test_operations_with_compatible_targets_shows_no_empty_state(environment):
    _capture_streams(environment)
    response = _client().get("/operations/capture")
    assert response.status_code == 200
    assert "WHAT DO YOU WANT TO RECORD?" in response.text
    assert "Capture is not configured" not in response.text
    assert "no compatible Capture Targets are currently registered" not in response.text


def test_confirmed_cash_capture_is_a_reconciliation_observation_not_a_finance_projection_update(environment):
    log = EventLog(environment / "events.jsonl")
    household = declare_party(log, "household")
    person = declare_party(log, "person")
    join_household(log, person.id, household.id)
    account = finance.declare_account(log, "checking", "GBP", liquidity_classification="liquid")
    finance.link_ownership(log, "account", account.id, "owner", person.id)
    finance.declare_transaction(log, account.id, 1_000.0, "GBP", "income", 1_000.0)
    streams = TelemetryStreamRegistry(log)
    streams.declare(TelemetryStream(
        id="cash-value", subject_id=account.id, property="cash_balance", channel="manual",
        refresh_policy="annual", confirmation_policy="review_each", source_identity="user:reviewer",
        unit_or_currency="GBP", validation_contract="numeric", household_id=household.id,
        expected_cadence="annual"))

    def cash_available():
        registry = MetricRegistry()
        registry.register(FinanceMetricProvider(FinanceEntityProjection(log), EntityProjection(log)))
        return registry.dispatch(MetricRequest("finance.cash_available", Subject("party", household.id),
                                               as_of=1_700_000_000.0))

    assert cash_available().value == 1_000.0
    client = _client()
    assert _submit_capture(client, "cash-balance-update", "cash-value", amount="1500",
                           evidence_reference="cash-statement-2026").status_code == 303
    proposal = next(iter(ProposalInbox(log).proposals.values()))
    assert client.post(f"/acquisition/proposals/{proposal.id}/confirm", data={
        "csrf": webauth.csrf_token(ALLOWED, webauth.load_config(), "rfc011-confirmation"),
    }).status_code == 303
    assert any(event["kind"] == "finance.account.reconciliation_observed" for event in log.events())
    assert cash_available().value == 1_000.0

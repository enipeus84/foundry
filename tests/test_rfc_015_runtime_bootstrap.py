"""RFC-015 Phase 2: runtime declaration of real canonical Finance entities."""

from __future__ import annotations

import pytest

from foundry.core.acquisition import AssetRegistration, TelemetryStream
from foundry.core.capture_targets import CaptureTargetRegistry
from foundry.core.entities import declare_party, join_household
from foundry.eventlog import EventLog
from foundry.finance import entities as finance
from foundry.finance.capture_targets import FinanceCaptureTargetResolver
from foundry.finance.entities import FinanceEntityProjection
from foundry.finance.mortgage_evidence import record_mortgage_evidence
from foundry.finance.runtime_bootstrap import (
    CaptureTargetBootstrapError, bootstrap_finance_capture_targets, stream_identity,
)


def _household(log):
    household, person = declare_party(log, "household"), declare_party(log, "person")
    join_household(log, person.id, household.id)
    return household, person


def _own(log, kind, entity_id, person_id, relation="owner"):
    finance.link_ownership(log, kind, entity_id, relation, person_id)


def _primary_home(log, person_id, *, primary=True):
    home = finance.declare_asset(log, "property", "GBP", name="A mutable display name")
    _own(log, "asset", home.id, person_id)
    mortgage = finance.declare_obligation(log, "mortgage", "GBP", amount=1)
    _own(log, "obligation", mortgage.id, person_id, "owes")
    finance.link_ownership(log, "obligation", mortgage.id, "secures", home.id)
    if primary:
        record_mortgage_evidence(log, mortgage.id, "property_role", "primary_residence", 1,
                                 confidence=1, source="canonical", lineage="canonical")
    return home


def _targets(log, household_id):
    return CaptureTargetRegistry(log, FinanceCaptureTargetResolver(FinanceEntityProjection(log))).for_household(household_id)


def test_bootstrap_discovers_pension_and_multiple_cash_accounts_without_names(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    household, person = _household(log)
    pension = finance.declare_account(log, "pension", "GBP", name="renamed")
    cash_one, cash_two = finance.declare_account(log, "checking", "GBP"), finance.declare_account(log, "savings", "GBP")
    brokerage = finance.declare_account(log, "brokerage", "GBP", tax_wrapper="isa")
    for account in (pension, cash_one, cash_two, brokerage):
        _own(log, "account", account.id, person.id)
    result = bootstrap_finance_capture_targets(log, household.id)
    pairs = {(target.subject_id, target.property) for target in _targets(log, household.id)}
    assert pairs == {(pension.id, "pension_balance"), (cash_one.id, "cash_balance"), (cash_two.id, "cash_balance")}
    assert result.telemetry_streams_created == 3
    assert result.ineligible_entities_skipped >= 1


def test_primary_residence_is_resolved_from_mortgage_evidence_not_name(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    household, person = _household(log)
    home = _primary_home(log, person.id)
    bootstrap_finance_capture_targets(log, household.id)
    assert {(target.subject_id, target.property) for target in _targets(log, household.id)} == {(home.id, "property_valuation")}


def test_missing_or_ambiguous_primary_residence_fails_closed(tmp_path):
    missing = EventLog(tmp_path / "missing.jsonl")
    household, person = _household(missing)
    _primary_home(missing, person.id, primary=False)
    result = bootstrap_finance_capture_targets(missing, household.id)
    assert result.telemetry_streams_created == 0

    ambiguous = EventLog(tmp_path / "ambiguous.jsonl")
    household, person = _household(ambiguous)
    _primary_home(ambiguous, person.id)
    _primary_home(ambiguous, person.id)
    with pytest.raises(CaptureTargetBootstrapError, match="primary residence is ambiguous"):
        bootstrap_finance_capture_targets(ambiguous, household.id)


def test_bootstrap_is_idempotent_and_identity_survives_replay_and_renaming(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    household, person = _household(log)
    pension = finance.declare_account(log, "pension", "GBP", name="first name")
    _own(log, "account", pension.id, person.id)
    first = bootstrap_finance_capture_targets(log, household.id)
    event_count = len(list(log.events()))
    second = bootstrap_finance_capture_targets(EventLog(log.path), household.id)
    assert first.telemetry_streams_created == 1
    assert second.telemetry_streams_created == 0
    assert second.existing_declarations_retained == 2
    assert len(list(EventLog(log.path).events())) == event_count
    assert stream_identity(household.id, pension.id, "pension_balance") == stream_identity(household.id, pension.id, "pension_balance")


def test_conflicting_declarations_and_household_mismatch_are_rejected(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    household, person = _household(log)
    other, _ = _household(log)
    cash = finance.declare_account(log, "checking", "GBP")
    _own(log, "account", cash.id, person.id)
    from foundry.core.acquisition import AssetRegistry
    AssetRegistry(log, entity_exists=lambda subject: subject == cash.id).register(
        AssetRegistration(cash.id, "finance", other.id))
    with pytest.raises(CaptureTargetBootstrapError, match="conflicting asset registration"):
        bootstrap_finance_capture_targets(log, household.id)

    with pytest.raises(CaptureTargetBootstrapError, match="active canonical household"):
        bootstrap_finance_capture_targets(log, "not-a-household")


def test_existing_equivalent_declaration_is_retained_and_conflicting_stream_rejected(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    household, person = _household(log)
    cash = finance.declare_account(log, "checking", "GBP")
    _own(log, "account", cash.id, person.id)
    bootstrap_finance_capture_targets(log, household.id)
    assert bootstrap_finance_capture_targets(log, household.id).existing_declarations_retained == 2
    stream = next(target.stream for target in _targets(log, household.id))
    conflicting = TelemetryStream(**{**stream.as_dict(), "id": "conflicting-stream", "unit_or_currency": "USD"})
    # A historical conflicting declaration must not be silently selected.
    log.append("core.telemetry_stream.declared", conflicting.as_dict())
    with pytest.raises(CaptureTargetBootstrapError, match="conflicting telemetry declaration"):
        bootstrap_finance_capture_targets(log, household.id)


def test_web_composition_bootstraps_before_operations_can_construct_its_registry(tmp_path, monkeypatch):
    log = EventLog(tmp_path / "events.jsonl")
    household, person = _household(log)
    pension = finance.declare_account(log, "pension", "GBP")
    _own(log, "account", pension.id, person.id)
    monkeypatch.setenv("FOUNDRY_DATA_PATH", str(log.path))
    from foundry.web import _bootstrap_capture_targets, _build_console
    _bootstrap_capture_targets()
    console = _build_console()
    assert {(target.subject_id, target.property) for target in _targets(console.log, household.id)} == {
        (pension.id, "pension_balance")}


def test_authenticated_operations_renders_a_runtime_discovered_target(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from foundry import webauth
    log = EventLog(tmp_path / "events.jsonl")
    household, person = _household(log)
    pension = finance.declare_account(log, "pension", "GBP", name="Current presentation name")
    _own(log, "account", pension.id, person.id)
    email = "operator@example.test"
    monkeypatch.setenv("FOUNDRY_DATA_PATH", str(log.path))
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "test-key")
    monkeypatch.setenv("FOUNDRY_ALLOWED_EMAIL", email)
    monkeypatch.setenv("SESSION_SECRET", "unit-test-secret-0123456789abcdef")
    monkeypatch.setenv("APP_BASE_URL", "http://testserver")
    from foundry.web import _bootstrap_capture_targets, app
    _bootstrap_capture_targets()
    client = TestClient(app, follow_redirects=False)
    client.cookies.set(webauth.SESSION_COOKIE, webauth.session_token(email, webauth.load_config()))
    response = client.get("/operations/capture?contract=pension-balance-update")
    assert response.status_code == 200
    assert "Current presentation name" in response.text
    assert pension.id not in response.text

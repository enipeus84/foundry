"""SAFE F1/F3 regressions for RFC-015 Phase 2A."""

from __future__ import annotations

import pytest

from foundry.core.acquisition import AssetRegistration, AssetRegistry, TelemetryStream
from foundry.core.capture_targets import CaptureTargetRegistry
from foundry.core.entities import declare_party, join_household
from foundry.core import grammar
from foundry.eventlog import EventLog
from foundry.finance import entities as finance
from foundry.finance.capture_targets import FinanceCaptureTargetResolver
from foundry.finance.entities import FinanceEntityProjection
from foundry.finance.mortgage_evidence import record_mortgage_evidence
from foundry.finance.runtime_bootstrap import CaptureTargetBootstrapError, bootstrap_finance_capture_targets, stream_identity


def _household(log):
    household, person = declare_party(log, "household"), declare_party(log, "person")
    join_household(log, person.id, household.id)
    return household, person


def _account(log, person, type_):
    account = finance.declare_account(log, type_, "GBP")
    finance.link_ownership(log, "account", account.id, "owner", person.id)
    return account


def test_validation_finishes_before_any_event_is_appended(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    household, person = _household(log)
    pension, cash = _account(log, person, "pension"), _account(log, person, "checking")
    AssetRegistry(log, entity_exists=lambda subject: subject == cash.id).register(
        AssetRegistration(cash.id, "finance", "another-household"))
    before = list(log.events())
    with pytest.raises(CaptureTargetBootstrapError, match="conflicting household"):
        bootstrap_finance_capture_targets(log, household.id)
    assert list(log.events()) == before
    assert not any(event["kind"] == "core.telemetry_stream.declared" for event in before)
    assert pension.id != cash.id


def test_startup_is_available_and_surfaces_a_safe_bootstrap_diagnostic(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from foundry import webauth
    log = EventLog(tmp_path / "events.jsonl")
    household, person = _household(log)
    cash = _account(log, person, "checking")
    AssetRegistry(log, entity_exists=lambda subject: subject == cash.id).register(
        AssetRegistration(cash.id, "finance", "another-household"))
    email = "operator@example.test"
    for key, value in {
        "FOUNDRY_DATA_PATH": str(log.path), "SUPABASE_URL": "https://example.supabase.co",
        "SUPABASE_PUBLISHABLE_KEY": "test-key", "FOUNDRY_ALLOWED_EMAIL": email,
        "SESSION_SECRET": "unit-test-secret-0123456789abcdef", "APP_BASE_URL": "http://testserver",
    }.items():
        monkeypatch.setenv(key, value)
    from foundry.web import _bootstrap_capture_targets, app
    _bootstrap_capture_targets()
    diagnostic = app.state.capture_target_bootstrap_diagnostic
    assert diagnostic is not None
    assert diagnostic.entity == cash.id and diagnostic.validation == "asset registration"
    client = TestClient(app, follow_redirects=False)
    client.cookies.set(webauth.SESSION_COOKIE, webauth.session_token(email, webauth.load_config()))
    response = client.get("/operations/capture")
    assert response.status_code == 200
    assert "Capture target bootstrap needs attention" in response.text
    assert "No new capture targets were created." in response.text


def test_success_is_idempotent_and_retains_deterministic_identity(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    household, person = _household(log)
    pension = _account(log, person, "pension")
    first = bootstrap_finance_capture_targets(log, household.id)
    count = len(list(log.events()))
    second = bootstrap_finance_capture_targets(EventLog(log.path), household.id)
    targets = CaptureTargetRegistry(log, FinanceCaptureTargetResolver(FinanceEntityProjection(log))).for_household(household.id)
    assert first.telemetry_streams_created == 1 and second.telemetry_streams_created == 0
    assert len(list(EventLog(log.path).events())) == count
    assert targets[0].id == stream_identity(household.id, pension.id, "pension_balance")


def test_competing_stream_is_rejected_before_a_new_asset_can_be_written(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    household, person = _household(log)
    pension, cash = _account(log, person, "pension"), _account(log, person, "checking")
    AssetRegistry(log, entity_exists=lambda subject: subject == cash.id).register(
        AssetRegistration(cash.id, "finance", household.id))
    existing = TelemetryStream("historical", cash.id, "cash_balance", "manual", "annual", "review_each",
                               "operator", "USD", "numeric", household.id, "annual")
    from foundry.core.acquisition import TelemetryStreamRegistry
    TelemetryStreamRegistry(log).declare(existing)
    before = list(log.events())
    with pytest.raises(CaptureTargetBootstrapError, match="conflicting active"):
        bootstrap_finance_capture_targets(log, household.id)
    assert list(log.events()) == before
    assert pension.id not in {event["payload"].get("subject_id") for event in before if event["kind"].startswith("core.")}


def test_primary_residence_is_canonical_and_retired_streams_remain_retired(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    household, person = _household(log)
    home = finance.declare_asset(log, "property", "GBP", name="A display name")
    finance.link_ownership(log, "asset", home.id, "owner", person.id)
    mortgage = finance.declare_obligation(log, "mortgage", "GBP", amount=1)
    finance.link_ownership(log, "obligation", mortgage.id, "owes", person.id)
    finance.link_ownership(log, "obligation", mortgage.id, "secures", home.id)
    record_mortgage_evidence(log, mortgage.id, "property_role", "primary_residence", 1,
                             confidence=1, source="canonical", lineage="canonical")
    bootstrap_finance_capture_targets(log, household.id)
    target = next(item for item in CaptureTargetRegistry(
        log, FinanceCaptureTargetResolver(FinanceEntityProjection(log))).for_household(household.id)
                  if item.subject_id == home.id)
    log.append("core.telemetry_stream.retired", {"stream_id": target.id, "reason": "sold", "retired_at": 2})
    second = bootstrap_finance_capture_targets(log, household.id)
    assert second.telemetry_streams_created == 0
    assert not CaptureTargetRegistry(log, FinanceCaptureTargetResolver(FinanceEntityProjection(log))).for_household(household.id)


def test_all_canonical_cash_accounts_bootstrap_but_brokerage_does_not(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    household, person = _household(log)
    checking, savings, brokerage = (_account(log, person, "checking"), _account(log, person, "savings"),
                                    _account(log, person, "brokerage"))
    bootstrap_finance_capture_targets(log, household.id)
    subjects = {item.subject_id for item in CaptureTargetRegistry(
        log, FinanceCaptureTargetResolver(FinanceEntityProjection(log))).for_household(household.id)}
    assert subjects == {checking.id, savings.id}
    assert brokerage.id not in subjects


def test_ambiguous_primary_residence_is_a_zero_write_validation_failure(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    household, person = _household(log)
    for _ in range(2):
        home = finance.declare_asset(log, "property", "GBP")
        finance.link_ownership(log, "asset", home.id, "owner", person.id)
        mortgage = finance.declare_obligation(log, "mortgage", "GBP", amount=1)
        finance.link_ownership(log, "obligation", mortgage.id, "owes", person.id)
        finance.link_ownership(log, "obligation", mortgage.id, "secures", home.id)
        record_mortgage_evidence(log, mortgage.id, "property_role", "primary_residence", 1,
                                 confidence=1, source="canonical", lineage="canonical")
    before = list(log.events())
    with pytest.raises(CaptureTargetBootstrapError, match="multiple canonical"):
        bootstrap_finance_capture_targets(log, household.id)
    assert list(log.events()) == before


def test_display_name_never_participates_in_stream_identity(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    household, person = _household(log)
    pension = finance.declare_account(log, "pension", "GBP", name="first")
    finance.link_ownership(log, "account", pension.id, "owner", person.id)
    first = stream_identity(household.id, pension.id, "pension_balance")
    grammar.update(log, "finance", "account", pension.id, {"name": "second"}, "renamed")
    assert stream_identity(household.id, pension.id, "pension_balance") == first

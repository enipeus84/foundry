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
from foundry.finance.runtime_bootstrap import bootstrap_finance_capture_targets, stream_identity


def _household(log):
    household, person = declare_party(log, "household"), declare_party(log, "person")
    join_household(log, person.id, household.id)
    return household, person


def _account(log, person, type_):
    account = finance.declare_account(log, type_, "GBP")
    finance.link_ownership(log, "account", account.id, "owner", person.id)
    return account


def _capture_client(log, monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from foundry import webauth
    email = "operator@example.test"
    for key, value in {
        "FOUNDRY_DATA_PATH": str(log.path), "SUPABASE_URL": "https://example.supabase.co",
        "SUPABASE_PUBLISHABLE_KEY": "test-key", "FOUNDRY_ALLOWED_EMAIL": email,
        "SESSION_SECRET": "unit-test-secret-0123456789abcdef", "APP_BASE_URL": "http://testserver",
    }.items():
        monkeypatch.setenv(key, value)
    from foundry.web import _bootstrap_capture_targets, app
    _bootstrap_capture_targets()
    client = TestClient(app, follow_redirects=False)
    client.cookies.set(webauth.SESSION_COOKIE, webauth.session_token(email, webauth.load_config()))
    return client, app


def test_invalid_target_is_diagnosed_while_valid_targets_continue(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    household, person = _household(log)
    pension, cash = _account(log, person, "pension"), _account(log, person, "checking")
    AssetRegistry(log, entity_exists=lambda subject: subject == cash.id).register(
        AssetRegistration(cash.id, "finance", "another-household"))
    result = bootstrap_finance_capture_targets(log, household.id)
    assert pension.id != cash.id
    assert result.telemetry_streams_created == 1
    assert any(item.entity == cash.id for item in result.diagnostics)
    assert any(event["kind"] == "core.capture_target_bootstrap.diagnostic" for event in log.events())


def test_operations_truthfully_reports_partial_bootstrap(tmp_path, monkeypatch):
    log = EventLog(tmp_path / "events.jsonl")
    household, person = _household(log)
    _account(log, person, "pension")
    cash = _account(log, person, "checking")
    AssetRegistry(log, entity_exists=lambda subject: subject == cash.id).register(
        AssetRegistration(cash.id, "finance", "another-household"))
    client, app = _capture_client(log, monkeypatch)
    diagnostic = app.state.capture_target_bootstrap_diagnostic
    assert diagnostic is not None
    assert diagnostic.entity == cash.id and diagnostic.validation == "capture target"
    response = client.get("/operations/capture")
    assert response.status_code == 200
    assert "Capture target bootstrap partially completed" in response.text
    assert "1 bootstrap issue" in response.text
    assert "1 capture target is registered." in response.text
    assert cash.id not in response.text


def test_operations_truthfully_reports_total_failure_and_multiple_issues(tmp_path, monkeypatch):
    log = EventLog(tmp_path / "events.jsonl")
    household, person = _household(log)
    first, second = _account(log, person, "checking"), _account(log, person, "savings")
    assets = AssetRegistry(log, entity_exists=lambda subject: subject in {first.id, second.id})
    for account in (first, second):
        assets.register(AssetRegistration(account.id, "finance", "another-household"))

    client, _ = _capture_client(log, monkeypatch)
    response = client.get("/operations/capture")

    assert "Capture target bootstrap failed" in response.text
    assert "2 bootstrap issues" in response.text
    assert "No capture targets were registered." in response.text
    assert first.id not in response.text and second.id not in response.text


def test_operations_truthfully_reports_success_for_eligible_brokerage_account(tmp_path, monkeypatch):
    log = EventLog(tmp_path / "events.jsonl")
    household, person = _household(log)
    _account(log, person, "brokerage")

    client, _ = _capture_client(log, monkeypatch)
    response = client.get("/operations/capture")

    assert "Capture targets ready" in response.text
    assert "1 capture target is registered." in response.text


def test_operations_truthfully_reports_successful_bootstrap(tmp_path, monkeypatch):
    log = EventLog(tmp_path / "events.jsonl")
    _, person = _household(log)
    _account(log, person, "pension")

    client, _ = _capture_client(log, monkeypatch)
    response = client.get("/operations/capture")

    assert "Capture targets ready" in response.text
    assert "Bootstrap completed successfully. 1 capture target is registered." in response.text


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


def test_competing_stream_is_diagnosed_without_blocking_other_targets(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    household, person = _household(log)
    pension, cash = _account(log, person, "pension"), _account(log, person, "checking")
    AssetRegistry(log, entity_exists=lambda subject: subject == cash.id).register(
        AssetRegistration(cash.id, "finance", household.id))
    existing = TelemetryStream("historical", cash.id, "cash_balance", "manual", "annual", "review_each",
                               "operator", "USD", "numeric", household.id, "annual")
    from foundry.core.acquisition import TelemetryStreamRegistry
    TelemetryStreamRegistry(log).declare(existing)
    result = bootstrap_finance_capture_targets(log, household.id)
    assert result.telemetry_streams_created == 1
    assert any(item.entity == cash.id for item in result.diagnostics)
    assert pension.id in {event["payload"].get("subject_id") for event in log.events()
                          if event["kind"] == "core.telemetry_stream.declared"}


def test_deterministic_stream_identity_collision_is_diagnosed_before_registry_append(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    household, person = _household(log)
    pension = _account(log, person, "pension")
    collision = TelemetryStream(
        stream_identity(household.id, pension.id, "pension_balance"), "unrelated-subject",
        "cash_balance", "manual", "annual", "review_each", "operator", "GBP", "numeric",
        household.id, "annual")
    from foundry.core.acquisition import TelemetryStreamRegistry
    TelemetryStreamRegistry(log).declare(collision)

    result = bootstrap_finance_capture_targets(log, household.id)

    assert result.asset_registrations_created == result.telemetry_streams_created == 0
    assert any(item.entity == pension.id and "identity collision" in item.reason
               for item in result.diagnostics)
    assert pension.id not in AssetRegistry(log, entity_exists=lambda _: True).registrations


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


def test_all_canonical_balance_accounts_bootstrap(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    household, person = _household(log)
    checking, savings, brokerage = (_account(log, person, "checking"), _account(log, person, "savings"),
                                    _account(log, person, "brokerage"))
    bootstrap_finance_capture_targets(log, household.id)
    subjects = {item.subject_id for item in CaptureTargetRegistry(
        log, FinanceCaptureTargetResolver(FinanceEntityProjection(log))).for_household(household.id)}
    assert subjects == {checking.id, savings.id, brokerage.id}


def test_ambiguous_primary_residence_is_diagnosed_without_registry_writes(tmp_path):
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
    result = bootstrap_finance_capture_targets(log, household.id)
    assert result.telemetry_streams_created == 0
    assert any(item.validation == "primary residence" for item in result.diagnostics)
    assert not any(event["kind"] == "core.telemetry_stream.declared" for event in log.events())


def test_display_name_never_participates_in_stream_identity(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    household, person = _household(log)
    pension = finance.declare_account(log, "pension", "GBP", name="first")
    finance.link_ownership(log, "account", pension.id, "owner", person.id)
    first = stream_identity(household.id, pension.id, "pension_balance")
    grammar.update(log, "finance", "account", pension.id, {"name": "second"}, "renamed")
    assert stream_identity(household.id, pension.id, "pension_balance") == first


def test_malformed_canonical_entity_is_diagnosed_and_does_not_block_valid_discovery(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    household, person = _household(log)
    pension = _account(log, person, "pension")
    log.append("finance.account.declared", {"entity_id": "malformed", "currency": "GBP"})

    result = bootstrap_finance_capture_targets(log, household.id)

    assert result.telemetry_streams_created == 1
    assert any(item.entity == "malformed" and item.validation == "canonical projection"
               for item in result.diagnostics)
    assert pension.id in {event["payload"].get("subject_id") for event in log.events()
                          if event["kind"] == "core.telemetry_stream.declared"}


def test_repeated_bad_startup_does_not_duplicate_diagnostics_or_targets(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    household, person = _household(log)
    cash = _account(log, person, "checking")
    AssetRegistry(log, entity_exists=lambda subject: subject == cash.id).register(
        AssetRegistration(cash.id, "finance", "another-household"))

    bootstrap_finance_capture_targets(log, household.id)
    first = list(log.events())
    bootstrap_finance_capture_targets(EventLog(log.path), household.id)

    assert list(EventLog(log.path).events()) == first

"""RFC-015 Phase 1 Capture Target Registry acceptance tests."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from foundry.core.acquisition import AcquisitionError, AssetRegistration, AssetRegistry, TelemetryStream, TelemetryStreamRegistry
from foundry.core.capture_targets import CaptureTargetRegistry
from foundry.core.entities import declare_party
from foundry.eventlog import EventLog
from foundry.finance import entities as finance
from foundry.finance.capture_targets import FinanceCaptureTargetResolver
from foundry.finance.entities import FinanceEntityProjection


def _stream(identifier: str, subject_id: str, property_name: str, household_id: str) -> TelemetryStream:
    return TelemetryStream(
        id=identifier, subject_id=subject_id, property=property_name, channel="manual",
        refresh_policy="annual", confirmation_policy="review_each", source_identity="operator",
        unit_or_currency="GBP", validation_contract="numeric", household_id=household_id,
        expected_cadence="annual",
    )


def _registry(log: EventLog) -> CaptureTargetRegistry:
    return CaptureTargetRegistry(log, FinanceCaptureTargetResolver(FinanceEntityProjection(log)))


def _registered_account(log: EventLog, household_id: str, account_type: str = "checking"):
    account = finance.declare_account(log, account_type, "GBP", name="Canonical account")
    AssetRegistry(log, entity_exists=lambda subject_id: subject_id == account.id).register(
        AssetRegistration(account.id, "finance", household_id))
    return account


def test_unknown_entity_registration_fails_closed(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    household = declare_party(log, "household")
    registry = _registry(log)
    with pytest.raises(AcquisitionError, match="unknown domain entity reference"):
        registry.assets.register(AssetRegistration("unknown-account", "finance", household.id))


def test_projection_requires_canonical_entity_registration_household_and_compatibility(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    first, second = declare_party(log, "household"), declare_party(log, "household")
    account = _registered_account(log, first.id)
    streams = TelemetryStreamRegistry(log)
    streams.declare(_stream("eligible", account.id, "cash_balance", first.id))
    streams.declare(_stream("cross-household", account.id, "cash_balance", second.id))
    streams.declare(_stream("unsupported", account.id, "pension_balance", first.id))
    streams.declare(_stream("orphan", "missing", "cash_balance", first.id))
    registry = _registry(log)
    assert [target.id for target in registry.for_household(first.id)] == ["eligible"]
    assert registry.for_household(second.id) == ()


def test_closed_entity_and_retired_stream_leave_selection_but_preserve_history_resolution(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    household = declare_party(log, "household")
    active = _registered_account(log, household.id)
    closed = _registered_account(log, household.id)
    finance.close_account(log, closed.id, "closed")
    registry = _registry(log)
    registry.declare(_stream("active", active.id, "cash_balance", household.id))
    TelemetryStreamRegistry(log).declare(_stream("closed", closed.id, "cash_balance", household.id))
    assert [target.id for target in _registry(log).for_household(household.id)] == ["active"]
    registry.retire("active", "provider moved", 123.0)
    streams = TelemetryStreamRegistry(log)
    assert streams.streams["active"].subject_id == active.id
    assert "active" in streams.retired
    assert streams.retirements["active"]["reason"] == "provider moved"
    assert _registry(log).for_household(household.id) == ()


def test_duplicate_active_targets_are_refused_and_historical_duplicates_surface_as_conflicts(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    household = declare_party(log, "household")
    account = _registered_account(log, household.id)
    registry = _registry(log)
    registry.declare(_stream("first", account.id, "cash_balance", household.id))
    with pytest.raises(AcquisitionError, match="duplicate active capture target"):
        registry.declare(_stream("second", account.id, "cash_balance", household.id))
    TelemetryStreamRegistry(log).declare(_stream("legacy-duplicate", account.id, "cash_balance", household.id))
    replayed = _registry(log)
    assert replayed.for_household(household.id) == ()
    assert replayed.conflicts == {(household.id, account.id, "cash_balance"): ("first", "legacy-duplicate")}


def test_contract_compatibility_is_metadata_driven(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    household = declare_party(log, "household")
    pension = _registered_account(log, household.id, "pension")
    registry = _registry(log)
    registry.declare(_stream("pension", pension.id, "pension_balance", household.id))

    class Contract:
        def accepts_stream(self, property_name: str) -> bool:
            return property_name == "pension_balance"

    assert [target.id for target in registry.for_contract(household.id, Contract())] == ["pension"]


def test_operations_and_acquisition_share_the_same_finance_entity_resolution(tmp_path):
    from foundry import acquisition_web, operations_web

    log = EventLog(tmp_path / "events.jsonl")
    account = finance.declare_account(log, "checking", "GBP")
    console = SimpleNamespace(log=log)
    operations = operations_web._asset_registry(console)
    acquisition = acquisition_web._asset_registry(console)
    assert operations.entity_exists(account.id) is acquisition.entity_exists(account.id) is True
    assert operations.entity_exists("unknown") is acquisition.entity_exists("unknown") is False


def test_no_permissive_entity_existence_stub_remains_in_production_code():
    source_root = Path(__file__).resolve().parents[1] / "src"
    matches = [path for path in source_root.rglob("*.py")
               if "entity_exists=lambda" in path.read_text(encoding="utf-8")
               and "lambda _" in path.read_text(encoding="utf-8")
               and ": True" in path.read_text(encoding="utf-8")]
    assert matches == []

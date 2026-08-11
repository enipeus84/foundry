"""RFC-017 Phase 2 pension provenance regressions."""

from __future__ import annotations

import itertools
from pathlib import Path

import pytest

from foundry.core.acquisition import AssetRegistration, AssetRegistry
from foundry.core.entities import EntityProjection, declare_party, join_household, update_party
from foundry.core.metrics import MetricRequest
from foundry.core.scope import Subject
from foundry.core.subject_authority import CanonicalSubjectAuthority
from foundry.core.value_provenance import ProvenanceNode, ProvenanceResolver, ValueProvenanceError, ValueReference
from foundry.eventlog import EventLog
from foundry.finance import entities as fin
from foundry.finance.entities import FinanceEntityProjection
from foundry.finance.pension_evidence import PensionEvidenceProjection, record_pension_evidence
from foundry.finance.pension_metrics import FinancePensionMetricProvider
from foundry.finance.pension_provenance import (
    OWNERSHIP_CONTEXT,
    PENSION_WEALTH,
    RAW_VALUATION,
    TERMINAL_ATTRIBUTION,
    FinancePensionExplainer,
)
from foundry.web import _build_console


AS_OF = 100.0


def _assumptions(log):
    return fin.declare_assumption_set(log, "Pension", "v1", {
        "valuation_stale_after_days": 550.0,
    })


def _world(tmp_path, monkeypatch):
    ticks = itertools.count(1)
    monkeypatch.setattr("foundry.eventlog.time.time", lambda: float(next(ticks)))
    log = EventLog(tmp_path / "events.jsonl")
    household = declare_party(log, "household")
    update_party(log, household.id, {"reporting_currency": "GBP"}, "test")
    first, second = declare_party(log, "person"), declare_party(log, "person")
    join_household(log, first.id, household.id)
    join_household(log, second.id, household.id)
    return log, household, first, second, _assumptions(log)


def _account(log, owner, *, value=100_000.0, currency="GBP", share=None,
             as_of=AS_OF, valuation=True):
    pension = fin.declare_account(log, "pension", currency, tax_wrapper="pension_wrapper",
                                  liquidity_classification="illiquid_long")
    link = fin.link_ownership(log, "account", pension.id, "owner", owner.id, share=share)
    if valuation:
        fin.declare_valuation(log, pension.id, value, currency, as_of)
    return pension, link


def _resolver(log, household, assumption):
    core, finance = EntityProjection(log), FinanceEntityProjection(log)
    assets = AssetRegistry(log, entity_exists=lambda subject_id: subject_id in finance.accounts)
    for account_id in finance.accounts:
        assets.register(AssetRegistration(account_id, "finance", household.id))
    authority = CanonicalSubjectAuthority.from_canonical_state(
        asset_registrations=assets.registrations, parties=core.parties)
    result = ProvenanceResolver(authority=authority)
    result.register(FinancePensionExplainer(log, assumption_set_id=assumption.id))
    return result


def _reference(subject, *, known_at=10_000.0):
    return ValueReference(subject, PENSION_WEALTH, AS_OF, known_at)


def _metric(log, subject, assumption):
    return FinancePensionMetricProvider(
        FinanceEntityProjection(log), EntityProjection(log), PensionEvidenceProjection(log),
    ).calculate(MetricRequest(PENSION_WEALTH, subject, AS_OF,
                              assumption_set_id=assumption.id))


def _attributed(result, account_id):
    return next(item for item in result.contributions
                if item.role == "increases" and item.contributor.subject.id == account_id)


def test_household_and_fractional_person_attribution_match_metric(tmp_path, monkeypatch):
    log, household, first, second, assumption = _world(tmp_path, monkeypatch)
    pension, first_link = _account(log, first, share=50)
    fin.link_ownership(log, "account", pension.id, "owner", second.id, share=50)
    resolver = _resolver(log, household, assumption)

    whole = resolver.explain(_reference(Subject("party", household.id)), max_depth=1)
    person = resolver.explain(_reference(Subject("party", first.id)), max_depth=1)

    assert whole.quantity == _metric(log, Subject("party", household.id), assumption).value == 100_000.0
    assert person.quantity == _metric(log, Subject("party", first.id), assumption).value == 50_000.0
    edge = _attributed(person, pension.id)
    assert edge.quantity == 50_000.0
    assert edge.expandable is False
    assert edge.contributor.value_id == TERMINAL_ATTRIBUTION
    assert first_link["id"] in person.anchors
    contexts = {item.contributor.value_id for item in person.contributions if item.role == "contextual"}
    assert contexts == {RAW_VALUATION, OWNERSHIP_CONTEXT}
    raw_ref = next(item.contributor for item in person.contributions
                   if item.contributor.value_id == RAW_VALUATION)
    assert resolver.explain(raw_ref, max_depth=0).quantity == 100_000.0
    assert person.completeness == "complete"


def test_obs_pension_01_is_reproduced_not_corrected(tmp_path, monkeypatch):
    log, household, first, second, assumption = _world(tmp_path, monkeypatch)
    pension, retained_link = _account(log, first, share=None)
    fin.link_ownership(log, "account", pension.id, "owner", second.id, share=100)
    resolver = _resolver(log, household, assumption)
    result = resolver.explain(_reference(Subject("party", first.id)), max_depth=0)

    assert _metric(log, Subject("party", first.id), assumption).value == 100_000.0
    assert result.quantity == _attributed(result, pension.id).quantity == 100_000.0
    assert retained_link["id"] in result.anchors


def test_explicit_full_person_attribution_matches_metric(tmp_path, monkeypatch):
    log, household, first, _, assumption = _world(tmp_path, monkeypatch)
    pension, _ = _account(log, first, share=100)
    result = _resolver(log, household, assumption).explain(
        _reference(Subject("party", first.id)), max_depth=0)
    assert result.quantity == _metric(log, Subject("party", first.id), assumption).value == 100_000.0
    assert _attributed(result, pension.id).quantity == 100_000.0


def test_missing_conflicting_out_of_period_and_incommensurable_are_distinct(tmp_path, monkeypatch):
    log, household, first, _, assumption = _world(tmp_path, monkeypatch)
    _account(log, first, value=25_000.0)
    conflict, _ = _account(log, first)
    missing, _ = _account(log, first, valuation=False)
    future, _ = _account(log, first, as_of=AS_OF + 1)
    usd, _ = _account(log, first, currency="USD")
    record_pension_evidence(log, conflict.id, "db_annual_income_accrued", 12_000.0, AS_OF,
                            confidence=.9, source="statement", lineage="test", unit_or_currency="GBP")

    result = _resolver(log, household, assumption).explain(
        _reference(Subject("party", household.id)), max_depth=1)
    assert result.quantity == _metric(log, Subject("party", household.id), assumption).value == 25_000.0
    assert {(item.subject.id, item.reason) for item in result.exclusions} == {
        (conflict.id, "conflicting"), (missing.id, "unobserved"),
        (future.id, "out_of_period"), (usd.id, "incommensurable")}
    assert result.completeness == "partial"


def test_known_at_replays_ownership_and_valuation_history(tmp_path, monkeypatch):
    log, household, first, second, assumption = _world(tmp_path, monkeypatch)
    pension, _ = _account(log, first, value=100_000.0, share=50)
    before_correction = max(event["ts"] for event in log.events())
    fin.link_ownership(log, "account", pension.id, "owner", first.id, share=60)
    after_correction = max(event["ts"] for event in log.events())
    fin.declare_valuation(log, pension.id, 120_000.0, "GBP", AS_OF)
    resolver = _resolver(log, household, assumption)

    before = resolver.explain(_reference(Subject("party", first.id), known_at=before_correction), max_depth=0)
    after = resolver.explain(_reference(Subject("party", first.id), known_at=after_correction), max_depth=0)
    latest = resolver.explain(_reference(Subject("party", first.id)), max_depth=0)

    assert before.quantity == 50_000.0
    assert after.quantity == 60_000.0
    assert latest.quantity == 72_000.0
    assert second.id


def test_later_known_valuation_does_not_leak_backward(tmp_path, monkeypatch):
    log, household, first, _, assumption = _world(tmp_path, monkeypatch)
    pension, _ = _account(log, first, valuation=False)
    before_valuation = max(event["ts"] for event in log.events())
    fin.declare_valuation(log, pension.id, 100_000.0, "GBP", AS_OF)
    resolver = _resolver(log, household, assumption)

    earlier = resolver.explain(_reference(Subject("party", household.id), known_at=before_valuation), max_depth=0)
    later = resolver.explain(_reference(Subject("party", household.id)), max_depth=0)
    assert earlier.status == "unavailable"
    assert later.quantity == 100_000.0


def test_terminal_identifier_cannot_be_registered_and_resources_remain_authorised(tmp_path, monkeypatch):
    log, household, first, _, assumption = _world(tmp_path, monkeypatch)
    pension, _ = _account(log, first)
    resolver = _resolver(log, household, assumption)

    class TerminalExplainer:
        def explainable_value_ids(self):
            return frozenset({TERMINAL_ATTRIBUTION})

        def explain(self, reference):
            return ProvenanceNode(reference, "observed", "available", 100_000.0, "GBP",
                                  "test", ("event",), (), (), "wrongly registered")

    resolver.register(TerminalExplainer())
    with pytest.raises(ValueProvenanceError, match="expandable flag"):
        resolver.explain(_reference(Subject("party", household.id)), max_depth=1)
    with pytest.raises(ValueProvenanceError):
        resolver.explain(ValueReference(Subject("resource", "foreign"), RAW_VALUATION, AS_OF, 10_000), max_depth=0)
    with pytest.raises(ValueProvenanceError):
        resolver.explain(ValueReference(Subject("invalid", pension.id), RAW_VALUATION, AS_OF, 10_000), max_depth=0)


def test_explaining_is_deterministic_and_writes_nothing(tmp_path, monkeypatch):
    log, household, first, _, assumption = _world(tmp_path, monkeypatch)
    _account(log, first)
    resolver = _resolver(log, household, assumption)
    before = tuple(log.events())
    first_result = resolver.explain(_reference(Subject("party", household.id)), max_depth=1)
    second_result = resolver.explain(_reference(Subject("party", household.id)), max_depth=1)
    assert first_result == second_result
    assert tuple(log.events()) == before


def test_explainer_has_no_writer_or_contribution_history_path():
    source = (Path(__file__).resolve().parents[1]
              / "src/foundry/finance/pension_provenance.py").read_text()
    assert "EventLog" not in source
    assert "self._log.append" not in source
    assert "record_pension_evidence" not in source
    assert "employee_contribution" not in source
    assert "employer_contribution" not in source


def test_production_composition_registers_without_exposing_a_consumer(tmp_path, monkeypatch):
    monkeypatch.setenv("FOUNDRY_DATA_PATH", str(tmp_path / "events.jsonl"))
    console = _build_console()
    assert console.provenance is not None
    assert PENSION_WEALTH in console.provenance._explainers

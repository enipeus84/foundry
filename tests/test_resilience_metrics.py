"""RFC-008 published Financial Resilience metric contracts."""

import inspect

import pytest

from foundry.core.entities import EntityProjection
from foundry.core.metrics import MetricRegistry, MetricRequest
from foundry.core.scope import Subject
from foundry.demo_data import build_morgan_household, _seed_transactions
from foundry.errors import DuplicateMetricError
from foundry.eventlog import EventLog
from foundry.finance import entities as fin
from foundry.finance.entities import FinanceEntityProjection
from foundry.finance.metrics import (
    CALCULATION_VERSION as EXISTING_CALCULATION_VERSION,
    FinanceMetricProvider,
    METRIC_IDS as EXISTING_METRIC_IDS,
)
from foundry.finance.resilience_evidence import (
    ResilienceEvidenceProjection,
    record_resilience_evidence,
)
from foundry.finance.resilience_metrics import (
    CALCULATION_VERSION,
    METRIC_IDS,
    FinanceResilienceMetricProvider,
)


AS_OF = 1_785_170_000.0


def _assumptions(log):
    return fin.declare_assumption_set(
        log,
        "Financial Resilience policy",
        "v1",
        {
            "reserve_target_months": 18.0,
            "secure_floor_months": 6.0,
            "critical_floor_months": 1.0,
            "income_concentration_limit": .5,
            "commitment_horizon_months": 12.0,
            "outflow_crosscheck_tolerance": .2,
            "evidence_stale_after_days": 120.0,
            "movement_lookback_days": 90.0,
            "income_reduction_fraction": .25,
            "income_reduction_months": 3.0,
            "unexpected_expenditure": 5_000.0,
            "rate_shock_monthly_cost": 300.0,
            "temporary_unemployment_months": 3.0,
        },
    )


def _system(tmp_path, *, commitment=True, commitment_due_days=30):
    log = EventLog(tmp_path / "events.jsonl")
    household = build_morgan_household(log, as_of=AS_OF)
    _seed_transactions(log, household, AS_OF)
    assumptions = _assumptions(log)
    if commitment:
        record_resilience_evidence(
            log,
            household.household_id,
            "near_term_commitment",
            2_000.0,
            AS_OF,
            confidence=.9,
            source="synthetic household declaration",
            lineage="synthetic RFC-008 test evidence",
            unit_or_currency="GBP",
            due_at=AS_OF + commitment_due_days * 86_400.0,
            description="annual insurance premium",
            actor="synthetic_demo",
        )
    core = EntityProjection(log)
    finance = FinanceEntityProjection(log)
    evidence = ResilienceEvidenceProjection(log)
    base = FinanceMetricProvider(finance, core)
    resilience = FinanceResilienceMetricProvider(finance, core, evidence)
    registry = MetricRegistry()
    registry.register(base)
    registry.register(resilience)
    scope = Subject("party", household.household_id)
    return (
        log, household, assumptions, finance, registry, scope, resilience)


def _request(metric_id, scope, assumptions, *, as_of=AS_OF, **changes):
    values = {
        "metric_id": metric_id,
        "scope": scope,
        "as_of": as_of,
        "assumption_set_id": assumptions.id,
    }
    values.update(changes)
    return MetricRequest(**values)


def test_provider_owns_exactly_four_new_metrics_without_reowning_runway(
        tmp_path):
    _, _, _, _, registry, _, provider = _system(tmp_path)

    assert provider.owned_metric_ids() == METRIC_IDS
    assert METRIC_IDS == {
        "finance.essential_outflow_monthly",
        "finance.emergency_reserve_target",
        "finance.emergency_reserve_gap",
        "finance.deployable_surplus",
    }
    assert "finance.liquidity_runway" in EXISTING_METRIC_IDS
    assert "finance.liquidity_runway" not in METRIC_IDS
    assert registry.provider_for("finance.liquidity_runway") \
        is not registry.provider_for("finance.deployable_surplus")
    assert EXISTING_CALCULATION_VERSION == "v1"
    assert CALCULATION_VERSION == "resilience-metrics-v1"


def test_duplicate_resilience_metric_registration_fails_closed(tmp_path):
    _, _, _, _, _, _, provider = _system(tmp_path)
    registry = MetricRegistry()
    registry.register(provider)

    with pytest.raises(DuplicateMetricError):
        registry.register(provider.__class__(
            provider.finance, provider.core, provider.evidence))


def test_one_outflow_basis_reproduces_existing_liquidity_runway(tmp_path):
    _, _, assumptions, _, registry, scope, _ = _system(tmp_path)
    runway = registry.dispatch(MetricRequest(
        "finance.liquidity_runway", scope, AS_OF))
    outflow = registry.dispatch(_request(
        "finance.essential_outflow_monthly", scope, assumptions))
    gap = registry.dispatch(_request(
        "finance.emergency_reserve_gap", scope, assumptions))
    target = registry.dispatch(_request(
        "finance.emergency_reserve_target", scope, assumptions))

    assert runway.status == outflow.status == "available"
    assert runway.unit_or_currency == "months"
    assert outflow.unit_or_currency == "GBP"
    liquid_holdings = target.value - gap.value
    assert liquid_holdings / outflow.value == pytest.approx(runway.value)
    assert outflow.input_references
    assert outflow.assumption_references == tuple(assumptions.provenance)


def test_reserve_target_and_signed_gap_use_full_eighteen_months(tmp_path):
    _, _, assumptions, _, registry, scope, _ = _system(tmp_path)
    outflow = registry.dispatch(_request(
        "finance.essential_outflow_monthly", scope, assumptions))
    target = registry.dispatch(_request(
        "finance.emergency_reserve_target", scope, assumptions))
    gap = registry.dispatch(_request(
        "finance.emergency_reserve_gap", scope, assumptions))

    assert target.value == pytest.approx(outflow.value * 18.0)
    assert target.unit_or_currency == "GBP"
    assert gap.unit_or_currency == "GBP"
    assert gap.value < 0  # The synthetic household exceeds its target.
    assert gap.assumption_references


def test_deployable_surplus_is_conservative_stock_after_commitments(tmp_path):
    _, _, assumptions, _, registry, scope, _ = _system(tmp_path)
    target = registry.dispatch(_request(
        "finance.emergency_reserve_target", scope, assumptions))
    gap = registry.dispatch(_request(
        "finance.emergency_reserve_gap", scope, assumptions))
    surplus = registry.dispatch(_request(
        "finance.deployable_surplus", scope, assumptions))
    liquid = target.value - gap.value

    assert surplus.value == pytest.approx(
        max(0.0, liquid - target.value - 2_000.0))
    assert surplus.value >= 0
    assert surplus.unit_or_currency == "GBP"
    assert "month" not in surplus.unit_or_currency.lower()
    assert surplus.evidence_references


def test_below_destination_has_zero_deployable_surplus_not_partial_variant(
        tmp_path):
    log, household, assumptions, _, _, scope, _ = _system(tmp_path)
    fin.declare_transaction(
        log,
        household.joint_checking_id,
        -100_000.0,
        "GBP",
        "groceries",
        AS_OF,
        description="deterministic below-target fixture",
    )
    core = EntityProjection(log)
    finance = FinanceEntityProjection(log)
    provider = FinanceResilienceMetricProvider(
        finance, core, ResilienceEvidenceProjection(log))

    surplus = provider.calculate(_request(
        "finance.deployable_surplus", scope, assumptions))

    assert surplus.status == "available"
    assert surplus.value == 0.0
    assert not any("partial" in note.lower()
                   for note in surplus.limitations)


def test_absent_commitments_are_zero_only_with_mandatory_limitation(tmp_path):
    _, _, assumptions, _, registry, scope, _ = _system(
        tmp_path, commitment=False)

    surplus = registry.dispatch(_request(
        "finance.deployable_surplus", scope, assumptions))

    assert surplus.status == "available"
    assert any(
        "No near-term commitment evidence is recorded" in note
        for note in surplus.limitations
    )


def test_commitments_outside_horizon_are_zero_only_with_limitation(tmp_path):
    _, _, assumptions, _, registry, scope, _ = _system(
        tmp_path, commitment_due_days=400)

    surplus = registry.dispatch(_request(
        "finance.deployable_surplus", scope, assumptions))

    assert surplus.status == "available"
    assert any(
        "No declared commitment falls within the approved 12-month horizon"
        in note
        for note in surplus.limitations
    )


def test_metric_dependencies_are_memoised_per_request_scope(
        tmp_path, monkeypatch):
    _, _, assumptions, _, registry, scope, provider = _system(tmp_path)
    calls = 0
    original = provider.basis._average_essential_outflow

    def counted(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(
        provider.basis, "_average_essential_outflow", counted)

    for metric_id in sorted(METRIC_IDS):
        result = registry.dispatch(_request(
            metric_id, scope, assumptions))
        assert result.status == "available"

    assert calls == 1


def test_staleness_propagates_without_removing_metric_value(tmp_path):
    _, _, assumptions, _, registry, scope, _ = _system(tmp_path)
    stale_as_of = AS_OF + 400 * 86_400.0

    outflow = registry.dispatch(_request(
        "finance.essential_outflow_monthly",
        scope,
        assumptions,
        as_of=stale_as_of,
    ))
    target = registry.dispatch(_request(
        "finance.emergency_reserve_target",
        scope,
        assumptions,
        as_of=stale_as_of,
    ))

    assert outflow.status == target.status == "stale"
    assert outflow.value is not None
    assert target.value == pytest.approx(outflow.value * 18.0)


@pytest.mark.parametrize("metric_id", sorted(METRIC_IDS))
def test_missing_assumption_set_fails_honestly(metric_id, tmp_path):
    _, _, _, _, registry, scope, _ = _system(tmp_path)

    result = registry.dispatch(MetricRequest(metric_id, scope, AS_OF))

    assert result.status == "unavailable"
    assert result.value is None
    assert result.limitations == (
        "active resilience Assumption Set not found",)


@pytest.mark.parametrize("changes", [
    {"horizon": (AS_OF, AS_OF + 1.0)},
    {"scenario_id": "scenario-1"},
    {"requested_calculation_version": "future"},
    {"parameters": {"invented": 1}},
])
def test_unsupported_request_shapes_never_return_a_baseline(
        changes, tmp_path):
    _, _, assumptions, _, registry, scope, _ = _system(tmp_path)

    result = registry.dispatch(_request(
        "finance.essential_outflow_monthly",
        scope,
        assumptions,
        **changes,
    ))

    assert result.status == "unsupported"
    assert result.value is None


def test_runway_source_and_formula_are_not_redefined():
    source = inspect.getsource(FinanceMetricProvider._liquidity_runway)

    assert "(accounts + other) / monthly_outflow" in source
    assert "finance.emergency_reserve" not in source
    assert "deployable_surplus" not in source

"""Integration tests: the synthetic Parker-Brads household
(fixtures.py) validates the whole Finance pipeline end to end — real
entities, real ownership, real metrics, real reconciliation — not just
the unit-level scenarios in test_finance_metrics.py."""

import pytest

from foundry.core.entities import EntityProjection
from foundry.core.metrics import MetricRequest
from foundry.core.scope import Subject
from foundry.finance.entities import FinanceEntityProjection
from foundry.finance.fixtures import build_parker_brads_household
from foundry.finance.metrics import METRIC_IDS, FinanceMetricProvider


def _build(kernel):
    household = build_parker_brads_household(kernel.log)
    core_entities = EntityProjection(kernel.log)
    finance_entities = FinanceEntityProjection(kernel.log)
    provider = FinanceMetricProvider(finance_entities, core_entities)
    return household, core_entities, finance_entities, provider


def test_fixture_builds_a_household_of_four_with_two_owning_members(kernel):
    household, core_entities, _finance_entities, _provider = _build(kernel)
    members = {p.id for p in core_entities.members_of(household.household_id)}
    assert members == {household.chris_id, household.fiona_id, household.hamish_id, household.harriet_id}


def test_all_five_metrics_return_available_for_the_household(kernel):
    """The fixture exists to give every registered metric live data —
    a household this fully populated should never fall back to
    unsupported/unavailable for its own top-level scope."""
    household, _core_entities, _finance_entities, provider = _build(kernel)
    scope = Subject("party", household.household_id)

    net_worth = provider.calculate(MetricRequest("finance.net_worth", scope, household.as_of))
    runway = provider.calculate(MetricRequest("finance.liquidity_runway", scope, household.as_of))
    cash_flow = provider.calculate(MetricRequest("finance.cash_flow", scope, household.as_of))
    allocation = provider.calculate(MetricRequest("finance.asset_allocation", scope, household.as_of,
                                                    parameters={"asset_category": "private_equity"}))
    concentration = provider.calculate(MetricRequest("finance.employer_concentration",
                                                       Subject("party", household.chris_id), household.as_of))

    for result in (net_worth, runway, cash_flow, allocation, concentration):
        assert result.status == "available", result.limitations

    assert net_worth.value > 0
    assert 0.0 < concentration.value < 1.0  # Chris's Anchor stock is concentrated, not his whole portfolio


def test_household_net_worth_equals_sum_of_member_attributions(kernel):
    """001 §9, criterion 9 — Hamish and Harriet hold nothing, and must
    contribute exactly zero, not break the reconciliation."""
    household, _core_entities, _finance_entities, provider = _build(kernel)
    household_result = provider.calculate(MetricRequest(
        "finance.net_worth", Subject("party", household.household_id), household.as_of))

    member_ids = [household.chris_id, household.fiona_id, household.hamish_id, household.harriet_id]
    attributed_total = 0.0
    for member_id in member_ids:
        result = provider.calculate(MetricRequest("finance.net_worth", Subject("party", member_id), household.as_of))
        if result.status == "available":
            attributed_total += result.value
        # Hamish/Harriet legitimately fall back to `unavailable` — they
        # own nothing, which is not the same as owning zero of something.

    assert attributed_total == pytest.approx(household_result.value)


def test_children_have_no_owned_resources_and_report_unavailable_not_zero(kernel):
    household, _core_entities, _finance_entities, provider = _build(kernel)
    for child_id in (household.hamish_id, household.harriet_id):
        result = provider.calculate(MetricRequest(
            "finance.net_worth", Subject("party", child_id), household.as_of))
        assert result.status == "unavailable"
        assert result.value is None


def test_cross_currency_holiday_let_is_included_in_household_net_worth(kernel):
    household, core_entities, finance_entities, provider = _build(kernel)
    result = provider.calculate(MetricRequest(
        "finance.net_worth", Subject("party", household.household_id), household.as_of))
    assert result.status == "available"
    assert not result.limitations  # a rate was found; nothing was excluded
    holiday_let_valuation = finance_entities.valuations_of(household.holiday_let_id)[0]
    assert holiday_let_valuation.currency == "EUR"


def test_employer_concentration_flags_chris_anchor_systems_stake(kernel):
    household, _core_entities, _finance_entities, provider = _build(kernel)
    result = provider.calculate(MetricRequest(
        "finance.employer_concentration", Subject("party", household.chris_id), household.as_of))
    assert result.status == "available"
    assert result.value == pytest.approx(12_000.0 / (25_000.0 + 12_000.0))


def test_dispatching_every_metric_appends_no_events(kernel):
    """A metric calculation is a read, never a write (000 §13.4: a
    provider never writes a derived value into canonical observed
    state) — the event count is identical before and after computing
    all five metrics."""
    household, _core_entities, _finance_entities, provider = _build(kernel)
    scope = Subject("party", household.household_id)
    before = len(list(kernel.log.events()))

    provider.calculate(MetricRequest("finance.net_worth", scope, household.as_of))
    provider.calculate(MetricRequest("finance.liquidity_runway", scope, household.as_of))
    provider.calculate(MetricRequest("finance.cash_flow", scope, household.as_of))
    provider.calculate(MetricRequest("finance.asset_allocation", scope, household.as_of,
                                       parameters={"asset_category": "private_equity"}))
    provider.calculate(MetricRequest("finance.employer_concentration",
                                       Subject("party", household.chris_id), household.as_of))

    assert len(list(kernel.log.events())) == before


def test_fixture_writes_only_core_and_finance_event_kinds(kernel):
    build_parker_brads_household(kernel.log)
    kinds = {e["kind"].split(".")[0] for e in kernel.log.events()}
    assert kinds <= {"core", "finance"}


def test_fixture_replay_is_deterministic(kernel):
    """Rebuilding both projections twice from the same log must agree
    byte-for-byte (001 §24, criterion 8)."""
    household = build_parker_brads_household(kernel.log)

    entities_a, entities_b = FinanceEntityProjection(kernel.log), FinanceEntityProjection(kernel.log)
    assert {k: vars(v) for k, v in entities_a.accounts.items()} == \
           {k: vars(v) for k, v in entities_b.accounts.items()}
    assert {k: vars(v) for k, v in entities_a.positions.items()} == \
           {k: vars(v) for k, v in entities_b.positions.items()}

    core_a, core_b = EntityProjection(kernel.log), EntityProjection(kernel.log)
    provider_a = FinanceMetricProvider(entities_a, core_a)
    provider_b = FinanceMetricProvider(entities_b, core_b)
    scope = Subject("party", household.household_id)
    for metric_id in METRIC_IDS - {"finance.asset_allocation", "finance.cash_flow", "finance.employer_concentration"}:
        result_a = provider_a.calculate(MetricRequest(metric_id, scope, household.as_of))
        result_b = provider_b.calculate(MetricRequest(metric_id, scope, household.as_of))
        assert result_a.value == result_b.value

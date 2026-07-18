"""Demonstration: the Flight Deck (foundry.core.flight_deck) receives
*real* Finance metrics through the Metric Registry (000 §13.5, §14),
computed from the synthetic Parker-Brads household — not a mock
provider standing in for a domain, the way foundry.core's own test
suite necessarily does (RFC-001 implements no real domain).

This is the concrete cross-package proof 001 §23 and 000 §14 both
describe: Core composes a tile by dispatching a `MetricRequest`
through a `MetricRegistry` a caller populated; nothing in
`foundry.core` imports `foundry.finance`, and nothing here reaches into
`FinanceMetricProvider`'s calculation methods directly — every value on
every tile arrived via `registry.dispatch()` alone."""

import pytest

from foundry.core.entities import EntityProjection, declare_mission
from foundry.core.evidence import EvidenceIndex
from foundry.core.flight_deck import compose_flight_deck, compose_tile
from foundry.core.metrics import MetricRegistry, MetricRequest
from foundry.core.scope import Subject
from foundry.finance.entities import FinanceEntityProjection
from foundry.finance.fixtures import build_parker_brads_household
from foundry.finance.metrics import FinanceMetricProvider


def _wire_up(kernel, household):
    core_entities = EntityProjection(kernel.log)
    finance_entities = FinanceEntityProjection(kernel.log)
    evidence_index = EvidenceIndex(kernel.log)
    registry = MetricRegistry()
    registry.register(FinanceMetricProvider(finance_entities, core_entities))
    return core_entities, finance_entities, evidence_index, registry


def test_flight_deck_tile_carries_a_real_net_worth_value_from_the_household(kernel):
    household = build_parker_brads_household(kernel.log)
    core_entities, finance_entities, evidence_index, registry = _wire_up(kernel, household)

    # The independently-computed value, straight from the provider —
    # the tile below must match it exactly, having gone through
    # Core's dispatch machinery instead.
    direct = FinanceMetricProvider(finance_entities, core_entities).calculate(
        MetricRequest(metric_id="finance.net_worth", scope=Subject("party", household.household_id),
                      as_of=household.as_of))

    tile = compose_tile("finance.net_worth", Subject("party", household.household_id), registry,
                         core_entities, evidence_index, household.as_of)

    assert tile.current_value.status == "available"
    assert tile.current_value.value == direct.value
    assert tile.current_value.unit_or_currency == "GBP"
    # Lineage survives dispatch unchanged (000 §15, criterion 13):
    assert tile.calculation_and_evidence_references["input_references"] == direct.input_references
    # Every reference is a real event id in the log this fixture wrote —
    # proof this is live data, not a stand-in value:
    for ref in tile.current_value.input_references:
        assert kernel.log.get(ref) is not None


def test_flight_deck_composes_two_finance_tiles_in_one_call(kernel):
    """001 §23's V1 candidate KPIs include both Net Worth and Liquidity
    Runway, each populated through the identical core tile contract —
    no finance-specific field (001 §24, criterion 4)."""
    household = build_parker_brads_household(kernel.log)
    core_entities, _finance_entities, evidence_index, registry = _wire_up(kernel, household)

    tiles = compose_flight_deck(
        [
            ("finance.net_worth", Subject("party", household.household_id), None),
            ("finance.liquidity_runway", Subject("party", household.household_id), None),
        ],
        registry, core_entities, evidence_index, household.as_of,
    )

    by_metric = {t.metric_id: t for t in tiles}
    assert by_metric["finance.net_worth"].current_value.status == "available"
    assert by_metric["finance.liquidity_runway"].current_value.status == "available"
    assert by_metric["finance.liquidity_runway"].current_value.unit_or_currency == "months"


def test_mission_status_evaluated_against_a_real_finance_metric(kernel):
    """000 §8's three-step split, end to end with real data: Finance
    calculates net worth, Core evaluates the Mission's RAG status
    against it — no finance-specific mission logic exists."""
    household = build_parker_brads_household(kernel.log)
    core_entities, finance_entities, evidence_index, registry = _wire_up(kernel, household)

    current_net_worth = FinanceMetricProvider(finance_entities, core_entities).owned_metric_ids()
    assert "finance.net_worth" in current_net_worth

    mission = declare_mission(kernel.log, "Grow household net worth", target_metric="finance.net_worth",
                               target_value=400_000.0, tolerance=50_000.0)
    core_entities = EntityProjection(kernel.log)  # refresh to see the new Mission

    tile = compose_tile("finance.net_worth", Subject("party", household.household_id), registry,
                         core_entities, evidence_index, household.as_of, mission_id=mission.id)

    assert tile.rag_status in ("on_track", "at_risk", "off_track")  # never fabricated, never None here
    assert tile.variance_from_target == pytest.approx(tile.current_value.value - 400_000.0)


def test_flight_deck_never_appends_an_event_even_with_a_real_domain(kernel):
    """000 §14: the Flight Deck is a consumer, never a producer —
    holds even when the domain behind it is real, not a mock."""
    household = build_parker_brads_household(kernel.log)
    core_entities, _finance_entities, evidence_index, registry = _wire_up(kernel, household)

    before = len(list(kernel.log.events()))
    compose_flight_deck(
        [("finance.net_worth", Subject("party", household.household_id), None)],
        registry, core_entities, evidence_index, household.as_of,
    )
    after = len(list(kernel.log.events()))
    assert before == after


def test_core_flight_deck_module_never_imports_finance():
    """The other half of the independence guarantee 000's own test
    suite checks from Core's side (test_core_flight_deck.py): this
    package wires Finance in from the *outside*, at the call site
    above — foundry.core.flight_deck itself names no Finance symbol."""
    import ast
    import inspect

    import foundry.core.flight_deck as flight_deck_module
    tree = ast.parse(inspect.getsource(flight_deck_module))
    imported = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names} | \
        {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
    assert not any(m.startswith("foundry.finance") for m in imported)

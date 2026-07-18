"""Integration tests: Flight Deck composition (000 §14) from multiple
independent mock domains, and its independence from any real domain
(RFC-001 implements no real domain, including Finance)."""

import time

from foundry.core import evidence
from foundry.core.entities import EntityProjection, declare_mission, declare_party, join_household
from foundry.core.flight_deck import compose_flight_deck, compose_tile
from foundry.core.metrics import MetricRegistry, MetricRequest, MetricResult
from foundry.core.scope import Subject


class _AlphaDomainProvider:
    """Stands in for one product domain (e.g. Finance)."""

    def owned_metric_ids(self):
        return frozenset({"alpha.net_worth"})

    def calculate(self, request):
        return MetricResult(
            metric_id=request.metric_id, value=42_000.0, unit_or_currency="GBP",
            scope=request.scope, as_of=request.as_of, status="available",
            calculation_version="v1", input_references=("alpha-evt-1",),
        )


class _BetaDomainProvider:
    """Stands in for an unrelated second product domain (e.g. a future
    Career domain) — has no knowledge of, or dependency on, Alpha."""

    def owned_metric_ids(self):
        return frozenset({"beta.optionality_score"})

    def calculate(self, request):
        return MetricResult(
            metric_id=request.metric_id, value=0.8, unit_or_currency=None,
            scope=request.scope, as_of=request.as_of, status="available",
            calculation_version="v1", input_references=("beta-evt-1",),
        )


def test_compose_tile_pulls_vulnerability_and_recommendation_claims(kernel):
    log = kernel.log
    chris = declare_party(log, "person")
    e = kernel.ingest("Chris has 24% of net worth in one employer's stock.")
    vulnerability = kernel.derive(e["id"])[0]
    evidence.tag_claim(log, vulnerability.id, "insight_type", "vulnerability")
    evidence.concern(log, vulnerability.id, chris.id)

    e2 = kernel.ingest("Diversifying the position is recommended.")
    recommendation = kernel.derive(e2["id"])[0]
    evidence.tag_claim(log, recommendation.id, "insight_type", "recommendation")
    evidence.concern(log, recommendation.id, chris.id)

    registry = MetricRegistry()
    registry.register(_AlphaDomainProvider())
    entities = EntityProjection(log)
    index = evidence.EvidenceIndex(log)

    tile = compose_tile("alpha.net_worth", Subject("party", chris.id), registry,
                         entities, index, time.time())
    assert tile.current_value.value == 42_000.0
    assert tile.strategic_vulnerability == [vulnerability.id]
    assert tile.next_decision == [recommendation.id]


def test_compose_flight_deck_from_two_independent_domains(kernel):
    """Core composes a page from two mock providers, neither of which
    references the other's code — the concrete demonstration that
    Core imports no domain calculation logic directly."""
    log = kernel.log
    household = declare_party(log, "household")
    registry = MetricRegistry()
    registry.register(_AlphaDomainProvider())
    registry.register(_BetaDomainProvider())
    entities = EntityProjection(log)
    index = evidence.EvidenceIndex(log)

    tiles = compose_flight_deck(
        [
            ("alpha.net_worth", Subject("party", household.id), None),
            ("beta.optionality_score", Subject("party", household.id), None),
        ],
        registry, entities, index, time.time(),
    )
    assert {t.metric_id for t in tiles} == {"alpha.net_worth", "beta.optionality_score"}
    assert [t.current_value.value for t in tiles] == [42_000.0, 0.8]


def test_household_tile_aggregates_via_group_scope(kernel):
    log = kernel.log
    household = declare_party(log, "household")
    chris = declare_party(log, "person")
    join_household(log, chris.id, household.id)
    e = kernel.ingest("Chris is exposed to a single employer's equity.")
    claim = kernel.derive(e["id"])[0]
    evidence.tag_claim(log, claim.id, "insight_type", "vulnerability")
    evidence.concern(log, claim.id, chris.id)  # concerns the *member*, not the household

    registry = MetricRegistry()
    registry.register(_AlphaDomainProvider())
    entities = EntityProjection(log)
    index = evidence.EvidenceIndex(log)

    household_tile = compose_tile("alpha.net_worth", Subject("party", household.id),
                                   registry, entities, index, time.time())
    # A household-scoped tile surfaces a member's vulnerability too,
    # via the group-expansion drill-down rule (000 §8, §10).
    assert household_tile.strategic_vulnerability == [claim.id]


def test_tile_reflects_mission_rag_status(kernel):
    log = kernel.log
    mission = declare_mission(log, "Net worth target", target_metric="alpha.net_worth",
                               target_value=42_000.0, tolerance=1000.0)
    registry = MetricRegistry()
    registry.register(_AlphaDomainProvider())
    entities = EntityProjection(log)
    index = evidence.EvidenceIndex(log)

    tile = compose_tile("alpha.net_worth", Subject("mission", mission.id), registry,
                         entities, index, time.time(), mission_id=mission.id)
    assert tile.rag_status == "on_track"
    assert tile.variance_from_target == 0.0


def test_compose_tile_looks_up_mission_fresh_not_via_stale_object(kernel):
    """compose_tile() takes mission_id, not a Mission object, and
    resolves it from the same `entities` projection passed alongside —
    so a target set *after* the caller's own Mission snapshot was taken
    is still honoured, with no way to accidentally mix a stale Mission
    with a fresh projection."""
    log = kernel.log
    mission = declare_mission(log, "Net worth target")  # no target yet
    registry = MetricRegistry()
    registry.register(_AlphaDomainProvider())

    from foundry.core import grammar
    grammar.update(log, "core", "mission", mission.id,
                    {"target_metric": "alpha.net_worth", "target_value": 42_000.0,
                     "tolerance": 1000.0}, reason="target set after declare")

    entities = EntityProjection(log)  # built *after* the update above
    index = evidence.EvidenceIndex(log)
    tile = compose_tile("alpha.net_worth", Subject("mission", mission.id), registry,
                         entities, index, time.time(), mission_id=mission.id)
    assert tile.rag_status == "on_track"


def test_compose_tile_unknown_mission_id_is_harmless(kernel):
    log = kernel.log
    registry = MetricRegistry()
    registry.register(_AlphaDomainProvider())
    entities = EntityProjection(log)
    index = evidence.EvidenceIndex(log)
    tile = compose_tile("alpha.net_worth", Subject("party", "p1"), registry,
                         entities, index, time.time(), mission_id="no-such-mission")
    assert tile.rag_status is None


def test_flight_deck_never_appends_an_event(kernel):
    """The Flight Deck is a consumer, never a producer (000 §14)."""
    log = kernel.log
    registry = MetricRegistry()
    registry.register(_AlphaDomainProvider())
    entities = EntityProjection(log)
    index = evidence.EvidenceIndex(log)

    before = len(list(log.events()))
    compose_flight_deck([("alpha.net_worth", Subject("party", "p1"), None)],
                         registry, entities, index, time.time())
    after = len(list(log.events()))
    assert before == after


def test_core_module_imports_no_finance_package():
    """Core remains independent of Finance: no module under
    foundry.core imports `foundry.finance` in its own source — checked
    by static inspection (the same technique test_core_metrics.py uses
    for "no model adapter import"), not by asserting `foundry.finance`
    is absent from `sys.modules` process-wide. That process-global form
    held only while RFC-002 didn't exist yet; now that
    tests/test_finance_*.py legitimately import `foundry.finance`
    elsewhere in the same pytest run, the only invariant left to check
    is the one that actually matters: no *core* module's own source
    names it."""
    import ast
    import importlib
    import inspect
    import pkgutil

    import foundry.core as core_pkg

    for _, name, _ in pkgutil.iter_modules(core_pkg.__path__, prefix="foundry.core."):
        module = importlib.import_module(name)
        tree = ast.parse(inspect.getsource(module))
        imported = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import)
                    for alias in node.names} | \
            {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
        assert not any(m.startswith("foundry.finance") for m in imported), name

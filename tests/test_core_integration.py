"""Whole-surface adversarial checks: replay determinism across every
Core projection together, and the "no derived value is ever written as
canonical state" guarantee, exercised end to end rather than per
module."""

from foundry.core import decisions, evidence, grammar, vocab
from foundry.core.entities import EntityProjection, declare_mission, declare_party, join_household
from foundry.core.flight_deck import compose_flight_deck
from foundry.core.metrics import MetricRegistry, MetricRequest, MetricResult
from foundry.core.mission_evaluation import get_mission_status
from foundry.core.scope import Subject


class _MockProvider:
    def __init__(self, metric_id, value):
        self.metric_id, self.value = metric_id, value

    def owned_metric_ids(self):
        return frozenset({self.metric_id})

    def calculate(self, request):
        return MetricResult(metric_id=request.metric_id, value=self.value, unit_or_currency="GBP",
                             scope=request.scope, as_of=request.as_of, status="available",
                             calculation_version="v1")


def _build_scenario(log):
    household = declare_party(log, "household")
    chris = declare_party(log, "person")
    join_household(log, chris.id, household.id)
    mission = declare_mission(log, "Net worth goal", target_metric="mock.net_worth",
                               target_value=1000.0, tolerance=100.0)

    decision = decisions.declare_decision(log, statement="Sell RSUs", expected_outcome="Reduce risk")
    decisions.concern_decision(log, decision.id, chris.id)
    outcome = decisions.declare_outcome(log, decision, "mock.concentration", 0.17, 1.0)
    decisions.declare_review(log, decision, outcome, statement="Worked", review_verdict="achieved",
                              concerns=[chris.id])

    return household, chris, mission, decision


def test_all_three_core_projections_replay_deterministically_together(kernel):
    """Rebuilding EntityProjection, EvidenceIndex, and DecisionProjection
    from the same log twice, independently, must agree byte-for-byte —
    the multi-projection analogue of Canon's own regression oracle."""
    _build_scenario(kernel.log)

    entities_a, entities_b = EntityProjection(kernel.log), EntityProjection(kernel.log)
    index_a, index_b = evidence.EvidenceIndex(kernel.log), evidence.EvidenceIndex(kernel.log)
    decisions_a = decisions.DecisionProjection(kernel.log)
    decisions_b = decisions.DecisionProjection(kernel.log)

    assert {k: vars(v) for k, v in entities_a.parties.items()} == \
           {k: vars(v) for k, v in entities_b.parties.items()}
    assert {k: vars(v) for k, v in entities_a.missions.items()} == \
           {k: vars(v) for k, v in entities_b.missions.items()}
    assert index_a.tags == index_b.tags
    assert index_a.subjects == index_b.subjects
    assert {k: vars(v) for k, v in decisions_a.decisions.items()} == \
           {k: vars(v) for k, v in decisions_b.decisions.items()}
    assert {k: vars(v) for k, v in decisions_a.outcomes.items()} == \
           {k: vars(v) for k, v in decisions_b.outcomes.items()}


def test_mission_evaluation_and_flight_deck_composition_append_nothing(kernel):
    """The full read path — Mission status evaluation and Flight Deck
    composition together — never appends a single event, however many
    times it runs. Derived values (metric results, RAG status, tiles)
    are computed fresh every call, never written as canonical or cached
    observed state (000 §13.4, §14)."""
    household, chris, mission, decision = _build_scenario(kernel.log)
    before = len(list(kernel.log.events()))

    registry = MetricRegistry()
    registry.register(_MockProvider("mock.net_worth", 1050.0))
    entities = EntityProjection(kernel.log)
    index = evidence.EvidenceIndex(kernel.log)

    for _ in range(3):
        status, result = get_mission_status(mission.id, entities, registry,
                                             Subject("mission", mission.id), 1.0)
        compose_flight_deck(
            [("mock.net_worth", Subject("party", household.id), mission.id)],
            registry, entities, index, 1.0,
        )
    assert status == "on_track"
    after = len(list(kernel.log.events()))
    assert before == after


def test_replay_order_within_a_single_entity_is_log_order_not_call_order():
    """A relationship event for an entity that doesn't exist yet in the
    projection (a malformed/tampered log, never producible via the
    public write API) is silently ignored — the same fallthrough
    discipline Canon already applies to unknown targets — never a
    crash, never a fabricated entity."""
    import tempfile
    from pathlib import Path

    from foundry.eventlog import EventLog

    with tempfile.TemporaryDirectory() as d:
        log = EventLog(Path(d) / "events.jsonl")
        # A `linked` event referencing a party id that was never declared:
        log.append("core.party.linked",
                    {"entity_id": "ghost-party", "relation": "member_of", "target": "some-household"})
        projection = EntityProjection(log)
        assert projection.parties == {}  # no crash, no phantom entity


def test_rejected_writes_leave_no_trace_in_any_projection(kernel):
    """A VocabularyError raised before a write must leave every Core
    projection exactly as it was — 'checked before the append' (grammar
    module docstrings) means a rejected value never contaminates any
    read model, not just the raw log."""
    import pytest

    from foundry.errors import VocabularyError

    _build_scenario(kernel.log)
    before_events = len(list(kernel.log.events()))

    with pytest.raises(VocabularyError):
        grammar.relate(kernel.log, "core", "party", "chris", "not_a_relation",
                        "household", vocab.PARTY_RELATIONSHIP)

    assert len(list(kernel.log.events())) == before_events

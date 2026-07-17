"""Integration tests: the closed Decision -> Execution -> Outcome ->
Review -> Learning loop (000 §12), instantiated with a mock domain
event standing in for a real one (RFC-001 implements no real domain)."""

from foundry.canon import Canon
from foundry.core import decisions, evidence, grammar, vocab
from foundry.core.decisions import DecisionProjection


def test_worked_example_paypal_style_decision(kernel):
    """Mirrors 000 §12's illustrative example and 001 §21's financial
    instantiation, using a mock 'widget' domain in place of Finance."""
    log = kernel.log

    decision = decisions.declare_decision(
        log, statement="Sell the concentrated position immediately",
        rationale="Concentration risk from vested equity",
        expected_outcome="Reduce concentration risk",
    )
    decisions.concern_decision(log, decision.id, "party-chris")
    decisions.concern_decision(log, decision.id, "widget-position-1")

    # Execution: a mock domain's own mutation event, linked back via
    # `executes` — Core supplies only the relation, not the entity.
    grammar.declare(log, "widget", "position", "widget-position-1", {"quantity": 0})
    execution_link = grammar.relate(log, "widget", "position", "widget-position-1", "executes",
                                     decision.id, vocab.STRUCTURAL_RELATIONSHIP)

    outcome = decisions.declare_outcome(
        log, decision, observed_metric="widget.concentration",
        observed_value=0.17, observed_at=1_800_000_000.0,
    )
    decisions.concern_outcome(log, outcome.id, "party-chris")

    review_claim_id = decisions.declare_review(
        log, decision, outcome,
        statement="Objective achieved despite subsequent market movement",
        review_verdict="achieved", concerns=["party-chris", "widget-position-1"],
    )

    # -- Decision + Outcome are correctly projected --
    projection = DecisionProjection(log)
    d = projection.decisions[decision.id]
    assert d.concerns == ["party-chris", "widget-position-1"]
    o = projection.outcomes[outcome.id]
    assert o.decision_id == decision.id and o.observed_value == 0.17

    # -- Execution is discoverable via the relation, not a new entity --
    executions = projection.executions_of(decision.id)
    assert len(executions) == 1
    assert executions[0]["id"] == execution_link["id"]

    # -- Review is a Claim, correctly typed and linked --
    index = evidence.EvidenceIndex(log)
    assert index.current_tag(review_claim_id, "insight_type") == "review"
    assert index.current_tag(review_claim_id, "review_verdict") == "achieved"
    assert review_claim_id in index.claims_concerning("party-chris")

    # -- Provenance survives: Canon (unmodified) resolves the Review
    #    Claim's source events back to the Decision and Outcome, with
    #    no change to canon.py required.
    canon = Canon(log)
    explanation = canon.explain(review_claim_id)
    source_kinds = {e["kind"] for e in explanation["source_events"]}
    assert source_kinds == {"core.decision.declared", "core.decision_outcome.declared"}


def test_decision_does_not_write_finance_or_other_domain_events(kernel):
    """Recording a decision is not the same as it happening — no
    domain-specific entity event is ever appended as a side effect of
    declare_decision()."""
    before = list(kernel.log.events())
    decisions.declare_decision(kernel.log, statement="Considering a change")
    after = list(kernel.log.events())
    new_kinds = {e["kind"] for e in after[len(before):]}
    assert new_kinds == {"core.decision.declared"}


def test_learning_is_citable_via_informed_by_no_second_knowledge_system(kernel):
    """A Decision Review Claim is retrievable and citable exactly like
    any other Claim — 'lessons learned become future evidence' costs
    no new machinery."""
    log = kernel.log
    decision = decisions.declare_decision(log, statement="Sell RSUs", expected_outcome="Reduce risk")
    outcome = decisions.declare_outcome(log, decision, "widget.concentration", 0.17, 1.0)
    lesson_claim_id = decisions.declare_review(
        log, decision, outcome, statement="Selling promptly worked",
        review_verdict="achieved",
    )

    later_decision = decisions.declare_decision(log, statement="Sell Fiona's RSUs similarly")
    decisions.inform_decision(log, later_decision.id, lesson_claim_id)

    projection = DecisionProjection(log)
    assert projection.decisions[later_decision.id].informed_by == [lesson_claim_id]

    # And it's retrievable through the ordinary Canon, like any Claim:
    canon = Canon(log)
    assert canon.get(lesson_claim_id).statement == "Selling promptly worked"


def test_revise_decision_leaves_original_intact(kernel):
    log = kernel.log
    original = decisions.declare_decision(log, statement="Invest in X")
    revised = decisions.declare_decision(log, statement="Invest in Y instead")
    decisions.revise_decision(log, revised.id, original.id)

    projection = DecisionProjection(log)
    assert projection.decisions[revised.id].revises == original.id
    assert projection.decisions[original.id].statement == "Invest in X"  # untouched


def test_rebuild_equals_incremental_apply(kernel):
    """REGRESSION ORACLE for DecisionProjection."""
    log = kernel.log
    decision = decisions.declare_decision(log, statement="Test decision")
    decisions.concern_decision(log, decision.id, "subject-1")
    outcome = decisions.declare_outcome(log, decision, "metric.x", 1.0, 2.0)
    decisions.concern_outcome(log, outcome.id, "subject-1")

    projection = DecisionProjection(log)
    before = (
        {k: vars(v).copy() for k, v in projection.decisions.items()},
        {k: vars(v).copy() for k, v in projection.outcomes.items()},
    )
    projection.rebuild()
    after = (
        {k: vars(v).copy() for k, v in projection.decisions.items()},
        {k: vars(v).copy() for k, v in projection.outcomes.items()},
    )
    assert before == after

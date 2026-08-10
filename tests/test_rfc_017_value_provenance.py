from __future__ import annotations

from pathlib import Path

import pytest

from foundry.core.scope import Subject
from foundry.core.value_provenance import (
    Contribution, Exclusion, ExplanationDescriptor, ProvenanceNode,
    ProvenanceResolver, ValueProvenanceError, ValueReference,
)
from foundry.errors import DuplicateValueExplainerError


SCOPE = Subject("party", "household-1")


def ref(value_id: str, *, as_of: float = 10, known_at: float = 20) -> ValueReference:
    return ValueReference(SCOPE, value_id, as_of, known_at)


def node(reference: ValueReference, *, kind="derived", quantity=10.0, unit="credits",
         anchors=("event-1",), contributions=(), exclusions=(), status="available") -> ProvenanceNode:
    return ProvenanceNode(reference, kind, status, quantity, unit, "test-v1", anchors,
                          contributions, exclusions, "Mock value")


class MockExplainer:
    def __init__(self, nodes: dict[str, ProvenanceNode]):
        self.nodes = nodes
        self.calls: list[ValueReference] = []

    def explainable_value_ids(self) -> frozenset[str]:
        return frozenset(self.nodes)

    def explain(self, reference: ValueReference) -> ProvenanceNode | None:
        self.calls.append(reference)
        return self.nodes.get(reference.value_id)


def resolver_for(nodes, *, descriptors=()):
    resolver = ProvenanceResolver(descriptors)
    resolver.register(MockExplainer(nodes))
    return resolver


def test_zero_contributions_are_honestly_partial():
    root = ref("example.total")
    result = resolver_for({root.value_id: node(root)}).explain(root, max_depth=0)
    assert result.completeness == "partial"
    assert result.residual == 10.0


def test_balanced_parts_are_complete_but_exclusions_make_them_partial():
    root = ref("example.total")
    contribution = Contribution("increases", 10, ref("example.part"), False)
    result = resolver_for({root.value_id: node(
        root, contributions=(contribution,), exclusions=(Exclusion(SCOPE, "unobserved"),),
    )}).explain(root, max_depth=0)
    assert result.completeness == "partial"
    assert result.residual == 0


def test_observed_and_indivisible_nodes_make_no_additive_coverage_claim():
    observed_ref, indivisible_ref = ref("example.fact"), ref("example.product")
    observed = node(observed_ref, kind="observed", contributions=())
    contextual = Contribution("contextual", None, observed_ref, False)
    indivisible = node(indivisible_ref, contributions=(contextual,))
    result = resolver_for({observed_ref.value_id: observed, indivisible_ref.value_id: indivisible})
    assert result.explain(observed_ref, max_depth=0).completeness is None
    expanded = result.explain(indivisible_ref, max_depth=0)
    assert expanded.completeness == "indivisible"
    assert expanded.residual is None


@pytest.mark.parametrize("bad", [
    lambda root: node(root, kind="observed", contributions=(Contribution("increases", 1, ref("child"), False),)),
    lambda root: node(root, kind="observed", anchors=()),
])
def test_observed_contract_refuses_non_terminal_or_unanchored_nodes(bad):
    root = ref("example.fact")
    with pytest.raises(ValueProvenanceError):
        resolver_for({root.value_id: bad(root)}).explain(root, max_depth=0)


def test_refuses_unknown_unit_mismatch_repeated_contributor_and_empty_version():
    root = ref("example.total")
    unknown = ProvenanceResolver().explain(root, max_depth=0)
    assert unknown is None
    child = ref("example.part")
    repeated = node(root, contributions=(
        Contribution("increases", 5, child, False), Contribution("decreases", 5, child, False),
    ))
    with pytest.raises(ValueProvenanceError, match="repeated"):
        resolver_for({root.value_id: repeated}).explain(root, max_depth=0)
    broken = node(root)
    object.__setattr__(broken, "calculation_version", "")
    with pytest.raises(ValueProvenanceError, match="calculation version"):
        resolver_for({root.value_id: broken}).explain(root, max_depth=0)
    child_node = node(child, quantity=5, unit="other")
    parent = node(root, contributions=(Contribution("increases", 5, child, True),))
    with pytest.raises(ValueProvenanceError, match="unit differs"):
        resolver_for({root.value_id: parent, child.value_id: child_node}).explain(root, max_depth=1)


def test_resolver_preserves_order_and_uses_exact_comparison_without_tolerance():
    root = ref("example.total")
    first, second = ref("first"), ref("second")
    parts = (Contribution("increases", 0.1, first, False), Contribution("increases", 0.2, second, False))
    result = resolver_for({root.value_id: node(root, quantity=0.3, contributions=parts)}).explain(root, max_depth=0)
    assert result.contributions == parts
    assert result.completeness == "partial"
    tolerant = resolver_for({root.value_id: node(root, quantity=0.3, contributions=parts)}, descriptors=(
        ExplanationDescriptor(root.value_id, "credits", 0.01),
    )).explain(root, max_depth=0)
    assert tolerant.completeness == "complete"


def test_expansion_carries_the_identical_bitemporal_scope_and_respects_depth():
    root, child = ref("example.total", as_of=11, known_at=22), ref("example.part", as_of=11, known_at=22)
    parent = node(root, contributions=(Contribution("increases", 10, child, True),))
    child_node = node(child, quantity=10)
    explainer = MockExplainer({root.value_id: parent, child.value_id: child_node})
    resolver = ProvenanceResolver()
    resolver.register(explainer)
    resolver.explain(root, max_depth=0)
    assert explainer.calls == [root]
    resolver.explain(root, max_depth=1)
    assert explainer.calls[-2:] == [root, child]
    assert explainer.calls[-1].subject == root.subject
    assert explainer.calls[-1].as_of == root.as_of
    assert explainer.calls[-1].known_at == root.known_at


def test_frozen_clock_explanation_excludes_later_facts_and_replays_identically():
    class ClockExplainer:
        def explainable_value_ids(self):
            return frozenset({"example.clock"})

        def explain(self, reference):
            anchor = "event-early" if reference.known_at < 30 else "event-late"
            return node(reference, kind="observed", anchors=(anchor,))

    resolver = ProvenanceResolver()
    resolver.register(ClockExplainer())
    historical = ref("example.clock", known_at=20)
    first, second = resolver.explain(historical, max_depth=0), resolver.explain(historical, max_depth=0)
    assert first == second
    assert first.anchors == ("event-early",)
    assert resolver.explain(ref("example.clock", known_at=40), max_depth=0).anchors == ("event-late",)


def test_cycles_mark_the_parent_unavailable_and_additive_disagreement_refuses():
    root, child = ref("example.a"), ref("example.b")
    parent = node(root, contributions=(Contribution("increases", 10, child, True),))
    cycle = node(child, contributions=(Contribution("increases", 10, root, True),))
    cycle_result = resolver_for({root.value_id: parent, child.value_id: cycle}).explain(root, max_depth=2)
    assert cycle_result.status == "unavailable"
    assert cycle_result.quantity is None
    disagreeing = node(child, quantity=9)
    conflict = resolver_for({root.value_id: parent, child.value_id: disagreeing}).explain(root, max_depth=1)
    assert conflict.status == "unavailable"
    assert conflict.quantity is None
    assert conflict.completeness is None
    assert conflict.residual is None


def test_closed_vocabulary_duplicate_ownership_and_non_declarable_completeness():
    root = ref("example.total")
    with pytest.raises(ValueProvenanceError):
        Contribution("contextual", 1, root, False)
    with pytest.raises(ValueProvenanceError, match="must not be negative"):
        Contribution("decreases", -1, root, False)
    with pytest.raises(TypeError):
        ProvenanceNode(root, "derived", "available", 1, "credits", "v", (), (), (), "Mock", "complete")
    one, two = MockExplainer({root.value_id: node(root)}), MockExplainer({root.value_id: node(root)})
    resolver = ProvenanceResolver()
    resolver.register(one)
    with pytest.raises(DuplicateValueExplainerError):
        resolver.register(two)


def test_core_module_is_domain_neutral_and_has_no_event_writer():
    source = (Path(__file__).resolve().parents[1] / "src/foundry/core/value_provenance.py").read_text()
    assert "foundry.finance" not in source
    assert "EventLog" not in source
    assert ".append(" not in source

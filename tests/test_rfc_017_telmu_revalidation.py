"""Independent post-remediation probes for RFC-017 Phase 1."""

from __future__ import annotations

import pytest

from foundry.core.scope import Subject
from foundry.core.value_provenance import (
    Contribution, ExplanationDescriptor, ProvenanceNode, ProvenanceResolver,
    ValueReference,
)


SCOPE = Subject("party", "household")


def ref(value_id, *, scope=SCOPE, as_of=10, known_at=20):
    return ValueReference(scope, value_id, as_of, known_at)


def node(reference, *, quantity=10, status="available", contributions=(), kind="derived"):
    return ProvenanceNode(reference, kind, status, quantity, "unit", "v1", ("event",),
                          contributions, (), "synthetic")


class Explainer:
    def __init__(self, nodes):
        self.nodes = nodes
        self.calls = []

    def explainable_value_ids(self):
        return frozenset(self.nodes)

    def explain(self, reference):
        self.calls.append(reference)
        return self.nodes.get(reference.value_id)


def resolve(nodes, root, *, depth=0, descriptors=()):
    resolver = ProvenanceResolver(descriptors)
    resolver.register(Explainer(nodes))
    return resolver.explain(root, max_depth=depth)


def test_revalidation_refuses_all_coordinate_substitution_before_child_dispatch():
    root = ref("root")
    child = ref("child", scope=Subject("party", "other"), as_of=11, known_at=21)
    parent = node(root, contributions=(Contribution("contextual", None, child, True),))
    with pytest.raises(ValueError, match="preserve subject, as_of, and known_at"):
        resolve({root.value_id: parent, child.value_id: node(child)}, root, depth=1)


def test_revalidation_resolver_strips_provider_owned_fields_and_unavailable_magnitude():
    observed = ref("observed")
    supplied = node(observed, kind="observed").with_derived_completeness("complete", 0)
    resolved = resolve({observed.value_id: supplied}, observed)
    assert resolved.completeness is None and resolved.residual is None
    unavailable = ref("unavailable")
    malformed = node(unavailable, status="unavailable").with_derived_completeness("complete", 0)
    resolved = resolve({unavailable.value_id: malformed}, unavailable)
    assert (resolved.quantity, resolved.completeness, resolved.residual) == (None, None, None)


def test_revalidation_registry_uses_single_declaration_snapshot():
    class ShiftingExplainer:
        def __init__(self):
            self.calls = 0

        def explainable_value_ids(self):
            self.calls += 1
            return frozenset({"first" if self.calls == 1 else "second"})

        def explain(self, reference):
            return node(reference)

    explainer = ShiftingExplainer()
    resolver = ProvenanceResolver()
    resolver.register(explainer)
    assert explainer.calls == 1
    assert resolver.explain(ref("first"), max_depth=0) is not None
    assert resolver.explain(ref("second"), max_depth=0) is None


def test_revalidation_expanded_additive_disagreement_makes_parent_unavailable():
    parent_ref, child_ref = ref("parent"), ref("child")
    parent = node(parent_ref, contributions=(Contribution("increases", 10, child_ref, True),))
    child = node(child_ref, quantity=9)
    resolved = resolve({parent_ref.value_id: parent, child_ref.value_id: child}, parent_ref, depth=1)
    assert resolved.status == "unavailable"
    assert resolved.quantity is None


@pytest.mark.parametrize(("role", "parent_quantity"), [("increases", 10), ("decreases", -10)])
def test_revalidation_additive_agreement_expands_normally_and_disagreement_is_unavailable(role, parent_quantity):
    parent_ref, child_ref = ref(f"{role}.parent"), ref(f"{role}.child")
    parent = node(parent_ref, quantity=parent_quantity,
                  contributions=(Contribution(role, 10, child_ref, True),))
    equal = resolve({parent_ref.value_id: parent, child_ref.value_id: node(child_ref, quantity=10)},
                    parent_ref, depth=1)
    assert equal.status == "available"
    conflict = resolve({parent_ref.value_id: parent, child_ref.value_id: node(child_ref, quantity=9)},
                       parent_ref, depth=1)
    assert (conflict.status, conflict.quantity, conflict.completeness, conflict.residual) == (
        "unavailable", None, None, None)


def test_revalidation_additive_agreement_uses_declared_tolerance_and_propagates_nested_conflict():
    root, middle, leaf = ref("root"), ref("middle"), ref("leaf")
    parent = node(root, contributions=(Contribution("increases", 10, middle, True),))
    within_tolerance = resolve(
        {root.value_id: parent, middle.value_id: node(middle, quantity=9.6)}, root, depth=1,
        descriptors=(ExplanationDescriptor(root.value_id, "unit", 0.5),),
    )
    assert within_tolerance.status == "available"
    nested = node(middle, contributions=(Contribution("increases", 10, leaf, True),))
    conflict = resolve(
        {root.value_id: parent, middle.value_id: nested, leaf.value_id: node(leaf, quantity=9)}, root, depth=2,
    )
    assert (conflict.status, conflict.quantity, conflict.completeness, conflict.residual) == (
        "unavailable", None, None, None)


def test_revalidation_siblings_cannot_mask_an_expanded_quantity_conflict():
    root, conflicted, sibling = ref("root"), ref("conflicted"), ref("sibling")
    parent = node(root, quantity=20, contributions=(
        Contribution("increases", 10, conflicted, True),
        Contribution("increases", 10, sibling, False),
    ))
    resolved = resolve(
        {root.value_id: parent, conflicted.value_id: node(conflicted, quantity=9)}, root, depth=1,
    )
    assert (resolved.status, resolved.quantity, resolved.completeness, resolved.residual) == (
        "unavailable", None, None, None)


def test_final_revalidation_malformed_expanded_child_still_refuses():
    parent_ref, child_ref = ref("parent"), ref("child")
    parent = node(parent_ref, contributions=(Contribution("increases", 10, child_ref, True),))
    malformed_child = node(child_ref, kind="observed", contributions=(
        Contribution("increases", 10, ref("grandchild"), False),
    ))
    with pytest.raises(ValueError, match="observed nodes require anchors and terminate"):
        resolve({parent_ref.value_id: parent, child_ref.value_id: malformed_child}, parent_ref, depth=1)

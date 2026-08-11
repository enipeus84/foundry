"""TELMU independent adversarial validation for RFC-017 Phase 1.

Expected failures document implementation findings.  They are strict so a
subsequent correction converts each into an XPASS and demands re-review.
"""

from __future__ import annotations

import pytest

from foundry.core.scope import Subject
from foundry.core.value_provenance import (
    Contribution, ExplanationDescriptor, ProvenanceNode, ProvenanceResolver,
    ValueReference,
)


ROOT_SCOPE = Subject("party", "root")
OTHER_SCOPE = Subject("party", "other")


class TestAuthority:
    def household_for(self, subject):
        return "household-root" if subject == ROOT_SCOPE else "household-other" if subject == OTHER_SCOPE else None


AUTHORITY = TestAuthority()


def reference(value_id, *, subject=ROOT_SCOPE, as_of=100, known_at=200):
    return ValueReference(subject, value_id, as_of, known_at)


def provenance(reference, *, quantity=10, unit="unit", status="available",
               contributions=(), exclusions=(), kind="derived", anchors=("event",)):
    return ProvenanceNode(reference, kind, status, quantity, unit, "v1", anchors,
                          contributions, exclusions, "synthetic")


class Explainer:
    def __init__(self, nodes):
        self.nodes = nodes
        self.calls = []

    def explainable_value_ids(self):
        return frozenset(self.nodes)

    def explain(self, value_reference):
        self.calls.append(value_reference)
        return self.nodes.get(value_reference.value_id)


def resolve(nodes, reference, *, depth=0, descriptors=()):
    resolver = ProvenanceResolver(descriptors, authority=AUTHORITY)
    resolver.register(Explainer(nodes))
    return resolver.explain(reference, max_depth=depth)


@pytest.mark.parametrize(("quantity", "parts", "tolerance", "expected"), [
    (10, (10,), None, "complete"),
    (10, (9,), None, "partial"),
    (10, (11,), None, "partial"),
    (10, (9.5,), 0.5, "complete"),
    (10, (9.49,), 0.5, "partial"),
    (10, (10,), 0, "complete"),
])
def test_telmu_completeness_boundary_matrix(quantity, parts, tolerance, expected):
    root = reference("synthetic.root")
    contributions = tuple(
        Contribution("increases", value, reference(f"synthetic.part.{index}"), False)
        for index, value in enumerate(parts)
    )
    descriptors = () if tolerance is None else (
        ExplanationDescriptor(root.value_id, "unit", tolerance),
    )
    result = resolve({root.value_id: provenance(root, quantity=quantity, contributions=contributions)},
                     root, descriptors=descriptors)
    assert result.completeness == expected


def test_telmu_contextual_never_enters_additive_arithmetic():
    root = reference("synthetic.root")
    contextual = Contribution("contextual", None, reference("synthetic.factor"), False)
    additive = Contribution("increases", 10, reference("synthetic.part"), False)
    result = resolve({root.value_id: provenance(root, contributions=(contextual, additive))}, root)
    assert result.completeness == "complete"
    assert result.residual == 0


def test_telmu_depth_zero_does_not_expand_a_registered_contributor():
    root, child = reference("synthetic.root"), reference("synthetic.child")
    parent = provenance(root, contributions=(Contribution("increases", 10, child, True),))
    explainer = Explainer({root.value_id: parent, child.value_id: provenance(child)})
    resolver = ProvenanceResolver(authority=AUTHORITY)
    resolver.register(explainer)
    resolver.explain(root, max_depth=0)
    assert explainer.calls == [root]


def test_telmu_rejects_an_explainer_that_changes_its_owned_value_ids_during_registration():
    class ShiftingExplainer:
        def __init__(self):
            self.calls = 0

        def explainable_value_ids(self):
            self.calls += 1
            return frozenset({"synthetic.first" if self.calls == 1 else "synthetic.second"})

        def explain(self, value_reference):
            return provenance(value_reference)

    explainer = ShiftingExplainer()
    resolver = ProvenanceResolver(authority=AUTHORITY)
    resolver.register(explainer)
    assert explainer.calls == 1
    assert resolver.explain(reference("synthetic.first"), max_depth=0) is not None
    assert resolver.explain(reference("synthetic.second"), max_depth=0) is None


def test_telmu_refuses_non_snapshot_iterable_ownership_declarations():
    class IterableExplainer:
        def explainable_value_ids(self):
            return iter(("synthetic.value",))

        def explain(self, value_reference):
            return provenance(value_reference)

    with pytest.raises(ValueError, match="frozenset"):
        ProvenanceResolver(authority=AUTHORITY).register(IterableExplainer())


def test_telmu_refuses_recursive_temporal_substitution():
    root = reference("synthetic.root")
    substituted = reference("synthetic.child", subject=OTHER_SCOPE, as_of=999, known_at=999)
    parent = provenance(root, contributions=(Contribution("increases", 10, substituted, True),))
    child = provenance(substituted)
    with pytest.raises(ValueError, match="preserve as_of and known_at"):
        resolve({root.value_id: parent, substituted.value_id: child}, root, depth=1)


def test_telmu_refuses_explainer_declared_completeness_on_observed_node():
    root = reference("synthetic.fact")
    supplied = provenance(root, kind="observed").with_derived_completeness("complete", 0)
    result = resolve({root.value_id: supplied}, root)
    assert result.completeness is None
    assert result.residual is None


def test_telmu_unavailable_node_cannot_make_a_completeness_claim():
    root = reference("synthetic.unavailable")
    contribution = Contribution("increases", 10, reference("synthetic.part"), False)
    result = resolve({root.value_id: provenance(root, status="unavailable", contributions=(contribution,))}, root)
    assert result.quantity is None
    assert result.completeness is None
    assert result.residual is None


@pytest.mark.parametrize("substituted", [
    lambda: reference("synthetic.child", as_of=101),
    lambda: reference("synthetic.child", known_at=201),
])
def test_telmu_refuses_each_recursive_temporal_substitution(substituted):
    root, child = reference("synthetic.root"), substituted()
    parent = provenance(root, contributions=(Contribution("increases", 10, child, True),))
    with pytest.raises(ValueError, match="preserve as_of and known_at"):
        resolve({root.value_id: parent, child.value_id: provenance(child)}, root, depth=1)


def test_telmu_refuses_nested_and_contextual_coordinate_substitution():
    root, middle = reference("synthetic.root"), reference("synthetic.middle")
    substituted = reference("synthetic.child", known_at=201)
    parent = provenance(root, contributions=(Contribution("increases", 10, middle, True),))
    nested = provenance(middle, contributions=(Contribution("contextual", None, substituted, True),))
    with pytest.raises(ValueError, match="preserve as_of and known_at"):
        resolve({root.value_id: parent, middle.value_id: nested, substituted.value_id: provenance(substituted)},
                root, depth=2)


@pytest.mark.parametrize("status", ["unavailable", "unsupported"])
def test_telmu_status_without_usable_value_normalises_provider_fields(status):
    root = reference(f"synthetic.{status}")
    malformed = provenance(root, status=status, contributions=(
        Contribution("increases", 10, reference("synthetic.part"), False),
    )).with_derived_completeness("complete", 0)
    result = resolve({root.value_id: malformed}, root)
    assert result.quantity is None
    assert result.completeness is None
    assert result.residual is None

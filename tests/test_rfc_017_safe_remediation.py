"""Durable regressions for the SAFE-017 remediation findings."""

from __future__ import annotations

import pytest

from foundry.core import vocab
from foundry.core.scope import Subject
from foundry.core.value_provenance import (
    Contribution, Exclusion, ProvenanceNode, ProvenanceResolver, ValueProvenanceError,
    ValueReference,
)
from foundry.errors import DuplicateValueExplainerError


SCOPE = Subject("party", "household")
FOREIGN_SCOPE = Subject("party", "foreign")


def reference(value_id, *, scope=SCOPE, as_of=10, known_at=20):
    return ValueReference(scope, value_id, as_of, known_at)


def node(reference, *, status="available", quantity=10, contributions=(), exclusions=()):
    return ProvenanceNode(reference, "derived", status, quantity, "unit", "v1", ("event",),
                          contributions, exclusions, "synthetic")


class Explainer:
    def __init__(self, nodes, value_ids=None):
        self.nodes = nodes
        self.value_ids = frozenset(nodes) if value_ids is None else value_ids
        self.calls = 0

    def explainable_value_ids(self):
        self.calls += 1
        return self.value_ids

    def explain(self, value_reference):
        return self.nodes.get(value_reference.value_id)


def resolve(nodes, root, *, depth=0):
    resolver = ProvenanceResolver()
    resolver.register(Explainer(nodes))
    return resolver.explain(root, max_depth=depth)


@pytest.mark.parametrize(("status", "usable"), [
    ("available", True), ("stale", True), ("unavailable", False),
    ("unsupported", False), ("error", False),
])
def test_safe_017_01_only_positive_usable_statuses_may_claim_magnitude(status, usable):
    root = reference(f"status.{status}")
    result = resolve({root.value_id: node(
        root, status=status, contributions=(Contribution("increases", 10, reference("part"), False),),
    )}, root)
    if usable:
        assert (result.quantity, result.completeness, result.residual) == (10, "complete", 0)
    else:
        assert (result.quantity, result.completeness, result.residual) == (None, None, None)


def test_safe_017_01_domain_added_status_is_non_usable_by_default(monkeypatch):
    monkeypatch.setattr(vocab.METRIC_STATUS, "_values", vocab.METRIC_STATUS.values | {"domain_pending"})
    root = reference("status.domain")
    result = resolve({root.value_id: node(
        root, status="domain_pending", contributions=(Contribution("increases", 10, reference("part"), False),),
    )}, root)
    assert (result.quantity, result.completeness, result.residual) == (None, None, None)


@pytest.mark.parametrize("child", [
    lambda: reference("child", scope=FOREIGN_SCOPE),
    lambda: reference("child", as_of=11),
    lambda: reference("child", known_at=21),
])
def test_safe_017_02_refuses_unexpanded_contributor_coordinate_substitution(child):
    root, substituted = reference("root"), child()
    parent = node(root, contributions=(Contribution("increases", 10, substituted, False),))
    with pytest.raises(ValueProvenanceError, match="preserve subject, as_of, and known_at"):
        resolve({root.value_id: parent}, root)


def test_safe_017_02_refuses_contextual_depth_bound_nested_and_exclusion_substitution():
    root, middle = reference("root"), reference("middle")
    foreign = reference("foreign", known_at=21)
    contextual = node(root, contributions=(Contribution("contextual", None, foreign, False),))
    with pytest.raises(ValueProvenanceError, match="preserve subject, as_of, and known_at"):
        resolve({root.value_id: contextual}, root)
    bounded = node(root, contributions=(Contribution("increases", 10, foreign, True),))
    with pytest.raises(ValueProvenanceError, match="preserve subject, as_of, and known_at"):
        resolve({root.value_id: bounded, foreign.value_id: node(foreign)}, root, depth=0)
    nested = node(middle, contributions=(Contribution("increases", 10, foreign, False),))
    parent = node(root, contributions=(Contribution("increases", 10, middle, True),))
    with pytest.raises(ValueProvenanceError, match="preserve subject, as_of, and known_at"):
        resolve({root.value_id: parent, middle.value_id: nested}, root, depth=2)
    excluded = node(root, exclusions=(Exclusion(FOREIGN_SCOPE, "unobserved"),))
    with pytest.raises(ValueProvenanceError, match="exclusions must preserve the requesting subject"):
        resolve({root.value_id: excluded}, root)


def test_safe_017_02_valid_unexpanded_reference_remains_valid():
    root, child = reference("root"), reference("child")
    result = resolve({root.value_id: node(
        root, contributions=(Contribution("increases", 10, child, False),),
    )}, root)
    assert result.completeness == "complete"


@pytest.mark.parametrize("spaced", [" value", "value ", " value "])
def test_safe_017_03_normalised_cross_explainer_duplicates_fail_closed(spaced):
    resolver = ProvenanceResolver()
    resolver.register(Explainer({"value": node(reference("value"))}, frozenset({"value"})))
    duplicate = Explainer({"value": node(reference("value"))}, frozenset({spaced}))
    with pytest.raises(DuplicateValueExplainerError):
        resolver.register(duplicate)


def test_safe_017_03_internal_normalisation_collision_and_stateful_snapshot_fail_closed():
    collided = Explainer({}, frozenset({"value", " value "}))
    with pytest.raises(DuplicateValueExplainerError, match="duplicate canonical"):
        ProvenanceResolver().register(collided)

    class ShiftingExplainer(Explainer):
        def explainable_value_ids(self):
            self.calls += 1
            return frozenset({"first" if self.calls == 1 else "second"})

    shifting = ShiftingExplainer({"first": node(reference("first"))})
    resolver = ProvenanceResolver()
    resolver.register(shifting)
    assert shifting.calls == 1
    assert resolver.explain(reference("first"), max_depth=0) is not None
    assert resolver.explain(reference("second"), max_depth=0) is None

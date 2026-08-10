"""SAFE remediation regressions for RFC-017 Phase 1.

Each test is named for the SAFE finding it defends.  The reproducers are the
SAFE probes, retained as executable evidence rather than described in prose.
"""

from __future__ import annotations

import pytest

from foundry.core.scope import Subject
from foundry.core.value_provenance import (
    MAGNITUDE_BEARING_STATUS, Contribution, Exclusion, ProvenanceNode,
    ProvenanceResolver, ValueProvenanceError, ValueReference,
)
from foundry.core import vocab
from foundry.errors import DuplicateValueExplainerError


SCOPE = Subject("party", "household-1")
OTHER = Subject("party", "household-2")


def ref(value_id: str, *, subject: Subject = SCOPE, as_of: float = 10,
        known_at: float = 20) -> ValueReference:
    return ValueReference(subject, value_id, as_of, known_at)


def node(reference: ValueReference, *, kind="derived", status="available",
         quantity=10.0, unit="credits", contributions=(), exclusions=()) -> ProvenanceNode:
    return ProvenanceNode(reference, kind, status, quantity, unit, "test-v1",
                          ("event-1",), contributions, exclusions, "Mock value")


class MockExplainer:
    def __init__(self, nodes, value_ids=None):
        self.nodes = nodes
        self._value_ids = frozenset(nodes) if value_ids is None else frozenset(value_ids)

    def explainable_value_ids(self) -> frozenset[str]:
        return self._value_ids

    def explain(self, reference: ValueReference) -> ProvenanceNode | None:
        maker = self.nodes.get(reference.value_id)
        return maker(reference) if callable(maker) else maker


def resolver_for(nodes, **kwargs):
    resolver = ProvenanceResolver()
    resolver.register(MockExplainer(nodes, **kwargs))
    return resolver


# ---------------------------------------------------------------- SAFE-017-01

@pytest.mark.parametrize("status", sorted(set(vocab.METRIC_STATUS.values) - MAGNITUDE_BEARING_STATUS))
def test_safe_017_01_no_failure_status_can_carry_a_coverage_claim(status):
    """A status outside the authorised set never presents magnitude or coverage.

    The original remediation named the failure statuses instead, so `error`
    balanced its parts and reported `complete` with a real quantity.
    """
    root = ref("v")
    resolver = resolver_for({"v": node(
        root, status=status, quantity=100.0,
        contributions=(Contribution("increases", 100.0, ref("leaf"), False),))})
    result = resolver.explain(root, max_depth=0)
    assert result.status == status
    assert result.quantity is None
    assert result.completeness is None
    assert result.residual is None


@pytest.mark.parametrize("status", sorted(MAGNITUDE_BEARING_STATUS))
def test_safe_017_01_authorised_statuses_still_report_coverage(status):
    root = ref("v")
    resolver = resolver_for({"v": node(
        root, status=status, quantity=100.0,
        contributions=(Contribution("increases", 100.0, ref("leaf"), False),))})
    result = resolver.explain(root, max_depth=0)
    assert result.quantity == 100.0
    assert result.completeness == "complete"
    assert result.residual == 0


def test_safe_017_01_status_allow_list_is_closed_against_vocabulary_extension():
    """`METRIC_STATUS` is extensible; the coverage rule must not inherit
    anything added to it."""
    assert MAGNITUDE_BEARING_STATUS <= vocab.METRIC_STATUS.values
    assert MAGNITUDE_BEARING_STATUS == {"available", "stale"}


# ---------------------------------------------------------------- SAFE-017-02

@pytest.mark.parametrize("role", ["increases", "decreases", "contextual"])
def test_safe_017_02_unexpandable_contributor_coordinates_are_verified(role):
    """A contributor Core never expands still cannot carry foreign coordinates.

    Reproducer: a hostile explainer marked the contributor non-expandable and
    Core returned another household's subject inside a `complete` explanation.
    """
    root = ref("parent")
    foreign = ref("unowned.value", subject=OTHER, as_of=9999, known_at=9999)
    quantity = None if role == "contextual" else 100.0
    resolver = resolver_for({"parent": node(
        root, quantity=100.0,
        contributions=(Contribution(role, quantity, foreign, False),))})
    with pytest.raises(ValueProvenanceError):
        resolver.explain(root, max_depth=5)


@pytest.mark.parametrize("substituted", [
    ref("child", subject=OTHER),
    ref("child", as_of=11),
    ref("child", known_at=9999),
])
def test_safe_017_02_depth_bound_does_not_suspend_coordinate_verification(substituted):
    """At `depth == max_depth` the resolver returned before checking, so the
    deepest level of every explanation was unverified."""
    root = ref("parent")
    resolver = resolver_for({
        "parent": node(root, quantity=100.0, contributions=(
            Contribution("increases", 100.0, substituted, True),)),
        "child": node(substituted, kind="observed", quantity=100.0),
    }, value_ids={"parent", "child"})
    with pytest.raises(ValueProvenanceError):
        resolver.explain(root, max_depth=0)


def test_safe_017_02_exclusion_subject_is_verified():
    root = ref("v")
    resolver = resolver_for({"v": node(
        root, quantity=100.0,
        contributions=(Contribution("increases", 100.0, ref("leaf"), False),),
        exclusions=(Exclusion(OTHER, "unobserved"),))})
    with pytest.raises(ValueProvenanceError):
        resolver.explain(root, max_depth=0)


def test_safe_017_02_conforming_references_still_resolve():
    root = ref("v")
    resolver = resolver_for({"v": node(
        root, quantity=100.0,
        contributions=(Contribution("increases", 100.0, ref("leaf"), False),),
        exclusions=(Exclusion(SCOPE, "unobserved"),))})
    result = resolver.explain(root, max_depth=0)
    assert result.completeness == "partial"


# ---------------------------------------------------------------- SAFE-017-03

def test_safe_017_03_ownership_is_normalised_before_duplicate_validation():
    """Two explainers could own ids differing only by whitespace: the duplicate
    guard did not fire and the second owner became unreachable."""
    resolver = ProvenanceResolver()
    first = MockExplainer({"finance.net_worth": node(ref("finance.net_worth"))})
    second = MockExplainer({}, value_ids={" finance.net_worth "})
    resolver.register(first)
    with pytest.raises(DuplicateValueExplainerError):
        resolver.register(second)


def test_safe_017_03_normalised_ownership_routes_a_padded_declaration():
    resolver = ProvenanceResolver()
    resolver.register(MockExplainer(
        {"v": lambda reference: node(reference, quantity=1.0)},
        value_ids={"  v  "}))
    assert resolver.explain(ref("v"), max_depth=0) is not None


def test_safe_017_03_ownership_is_read_exactly_once():
    """The single-declaration snapshot (R4) survives normalisation."""
    calls = []

    class Counting(MockExplainer):
        def explainable_value_ids(self):
            calls.append(1)
            return super().explainable_value_ids()

    ProvenanceResolver().register(Counting({"v": node(ref("v"))}))
    assert len(calls) == 1

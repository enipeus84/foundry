"""Governor-amended RFC-017 Phase 1 conformance and SAFE-017-04 regressions."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from foundry.core.acquisition import AssetRegistration, AssetRegistry
from foundry.core.entities import EntityProjection, declare_party, join_household
from foundry.core.scope import Subject
from foundry.core.subject_authority import CanonicalSubjectAuthority
from foundry.core.value_provenance import (
    Contribution, Exclusion, ProvenanceNode, ProvenanceResolver,
    ValueProvenanceError, ValueReference,
)
from foundry.eventlog import EventLog


ROOT = Subject("party", "household-a")
ACCOUNT = Subject("resource", "account-a")
ASSET = Subject("resource", "asset-a")
OBLIGATION = Subject("resource", "obligation-a")
FOREIGN = Subject("resource", "account-b")
UNKNOWN = Subject("resource", "missing")


class MappingAuthority:
    def __init__(self, mapping):
        self.mapping = mapping

    def household_for(self, subject):
        return self.mapping.get(subject)


AUTHORITY = MappingAuthority({
    ROOT: "household-a", ACCOUNT: "household-a", ASSET: "household-a",
    OBLIGATION: "household-a", FOREIGN: "household-b",
})


def ref(value_id, *, subject=ROOT, as_of=10, known_at=20):
    return ValueReference(subject, value_id, as_of, known_at)


def node(reference, *, quantity=1.0, kind="derived", contributions=(), exclusions=(),
         status="available"):
    return ProvenanceNode(reference, kind, status, quantity, "unit", "v1", ("event",),
                          contributions, exclusions, "mock")


class Explainer:
    def __init__(self, nodes):
        self.nodes = nodes
        self.calls = []

    def explainable_value_ids(self):
        return frozenset(self.nodes)

    def explain(self, reference):
        self.calls.append(reference)
        value = self.nodes.get(reference.value_id)
        return value(reference) if callable(value) else value


def resolver_for(nodes, authority=AUTHORITY):
    resolver = ProvenanceResolver(authority=authority)
    explainer = Explainer(nodes)
    resolver.register(explainer)
    return resolver, explainer


def canonical_authority():
    return CanonicalSubjectAuthority.from_canonical_state(
        parties={"household-a": SimpleNamespace(
            party_type="household", status="active", memberships=())},
        asset_registrations={
            "account-a": SimpleNamespace(household_id="household-a"),
            "asset-a": SimpleNamespace(household_id="household-a"),
        },
    )


def test_canonical_subject_authority_uses_only_core_projection_read_views(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    household_a, household_b, person = (
        declare_party(log, "household"), declare_party(log, "household"), declare_party(log, "person"))
    join_household(log, person.id, household_a.id)
    entities = EntityProjection(log)
    assets = AssetRegistry(log, entity_exists=lambda subject_id: subject_id == "account-a")
    assets.register(AssetRegistration("account-a", "neutral", household_a.id))
    authority = CanonicalSubjectAuthority.from_canonical_state(
        asset_registrations=assets.registrations, parties=entities.parties)
    assert authority.household_for(Subject("party", household_a.id)) == household_a.id
    assert authority.household_for(Subject("party", person.id)) == household_a.id
    assert authority.household_for(Subject("resource", "account-a")) == household_a.id
    assert authority.household_for(Subject("party", household_b.id)) == household_b.id
    assert authority.household_for(UNKNOWN) is None
    join_household(log, person.id, household_b.id)
    ambiguous = CanonicalSubjectAuthority.from_canonical_state(
        asset_registrations=assets.registrations, parties=EntityProjection(log).parties)
    assert ambiguous.household_for(Subject("party", person.id)) is None


@pytest.mark.parametrize("subject", [
    Subject("", "account-a"),
    Subject(" ", "account-a"),
    Subject(7, "account-a"),
    Subject(None, "account-a"),
    Subject("unknown-kind", "account-a"),
    Subject("resource", ""),
    Subject("resource", " "),
    Subject("resource", 7),
])
def test_canonical_subject_authority_refuses_malformed_or_unknown_identity(subject):
    authority = canonical_authority()
    assert authority.household_for(Subject("resource", "account-a")) == "household-a"
    assert authority.household_for(subject) is None


@pytest.mark.parametrize("role", ["increases", "decreases", "contextual"])
def test_malformed_subject_refuses_at_root_and_unexpanded_contribution(role):
    authority = canonical_authority()
    malformed = Subject("unknown-kind", "account-a")
    root = ref("root")
    child = ref("child", subject=malformed)
    quantity = None if role == "contextual" else 1
    resolver, _ = resolver_for({"root": node(
        root, contributions=(Contribution(role, quantity, child, False),))}, authority)
    with pytest.raises(ValueProvenanceError, match="authorising household"):
        resolver.explain(root, max_depth=0)

    malformed_root = ref("root", subject=malformed)
    resolver, _ = resolver_for({"root": node(malformed_root)}, authority)
    with pytest.raises(ValueProvenanceError, match="unambiguous household authority"):
        resolver.explain(malformed_root, max_depth=0)


def test_malformed_subject_refuses_at_depth_bound_nested_and_exclusion():
    authority = canonical_authority()
    malformed = Subject("unknown-kind", "account-a")
    root = ref("root")
    bad_child = ref("child", subject=malformed)

    depth_bound, _ = resolver_for({
        "root": node(root, contributions=(Contribution("contextual", None, bad_child, True),)),
        "child": node(bad_child),
    }, authority)
    with pytest.raises(ValueProvenanceError, match="authorising household"):
        depth_bound.explain(root, max_depth=0)

    middle = ref("middle", subject=ASSET)
    nested, _ = resolver_for({
        "root": node(root, contributions=(Contribution("contextual", None, middle, True),)),
        "middle": node(middle, contributions=(
            Contribution("contextual", None, bad_child, False),)),
    }, authority)
    with pytest.raises(ValueProvenanceError, match="authorising household"):
        nested.explain(root, max_depth=2)

    excluded, _ = resolver_for({"root": node(
        root, exclusions=(Exclusion(malformed, "unobserved"),))}, authority)
    with pytest.raises(ValueProvenanceError, match="authorising household"):
        excluded.explain(root, max_depth=0)


def test_malformed_subject_cannot_inherit_a_cached_valid_resource_node():
    authority = canonical_authority()
    root = ref("root")
    left = ref("left")
    right = ref("right")
    valid = ref("shared", subject=ACCOUNT)
    malformed = ref("shared", subject=Subject("unknown-kind", "account-a"))
    resolver, explainer = resolver_for({
        "root": node(root, quantity=2, contributions=(
            Contribution("increases", 1, left, True),
            Contribution("increases", 1, right, True),
        )),
        "left": node(left, contributions=(Contribution("contextual", None, valid, True),)),
        "right": node(right, contributions=(Contribution("contextual", None, malformed, True),)),
        "shared": lambda reference: node(reference, kind="observed"),
    }, authority)
    with pytest.raises(ValueProvenanceError, match="authorising household"):
        resolver.explain(root, max_depth=2)
    assert explainer.calls == [root, left, valid, right]


def test_same_subject_and_cross_resource_same_household_traversal_are_allowed():
    root = ref("root")
    same_subject = Contribution("increases", 1, ref("same"), False)
    result, _ = resolver_for({"root": node(root, contributions=(same_subject,))})
    assert result.explain(root, max_depth=0).completeness == "complete"

    account = ref("account", subject=ACCOUNT)
    asset = ref("asset", subject=ASSET)
    obligation = ref("obligation", subject=OBLIGATION)
    cross_subject = node(root, quantity=3, contributions=(
        Contribution("increases", 1, account, False),
        Contribution("increases", 1, asset, False),
        Contribution("increases", 1, obligation, False),
    ))
    resolver, _ = resolver_for({"root": cross_subject})
    assert resolver.explain(root, max_depth=0).completeness == "complete"


def test_foreign_unknown_and_unresolvable_root_authority_refuse():
    root = ref("root")
    foreign = ref("foreign", subject=FOREIGN)
    resolver, _ = resolver_for({"root": node(
        root, contributions=(Contribution("increases", 1, foreign, False),))})
    with pytest.raises(ValueProvenanceError, match="outside the authorising household"):
        resolver.explain(root, max_depth=0)

    unknown = ref("unknown", subject=UNKNOWN)
    resolver, _ = resolver_for({"root": node(
        root, contributions=(Contribution("increases", 1, unknown, False),))})
    with pytest.raises(ValueProvenanceError, match="outside the authorising household"):
        resolver.explain(root, max_depth=0)

    resolver, _ = resolver_for({"root": node(root)}, MappingAuthority({}))
    with pytest.raises(ValueProvenanceError, match="unambiguous household authority"):
        resolver.explain(root, max_depth=0)


def test_same_household_exclusion_is_allowed_and_foreign_exclusion_refuses():
    root = ref("root")
    same = node(root, contributions=(Contribution("increases", 1, ref("leaf"), False),),
                exclusions=(Exclusion(ACCOUNT, "unobserved"),))
    resolver, _ = resolver_for({"root": same})
    assert resolver.explain(root, max_depth=0).completeness == "partial"

    foreign = node(root, contributions=(Contribution("increases", 1, ref("leaf"), False),),
                   exclusions=(Exclusion(FOREIGN, "unobserved"),))
    resolver, _ = resolver_for({"root": foreign})
    with pytest.raises(ValueProvenanceError, match="outside the authorising household"):
        resolver.explain(root, max_depth=0)


@pytest.mark.parametrize("child", [
    ref("child", as_of=11), ref("child", known_at=21),
])
def test_temporal_substitution_refuses_even_for_unexpanded_contributors(child):
    root = ref("root")
    resolver, _ = resolver_for({"root": node(
        root, contributions=(Contribution("contextual", None, child, False),))})
    with pytest.raises(ValueProvenanceError, match="preserve as_of and known_at"):
        resolver.explain(root, max_depth=0)


def test_memoisation_resolves_a_diamond_once_per_semantic_reference():
    root, left, right, shared = ref("root"), ref("left"), ref("right"), ref("shared")
    nodes = {
        "root": node(root, quantity=2, contributions=(
            Contribution("increases", 1, left, True), Contribution("increases", 1, right, True))),
        "left": node(left, contributions=(Contribution("contextual", None, shared, True),)),
        "right": node(right, contributions=(Contribution("contextual", None, shared, True),)),
        "shared": node(shared, kind="observed"),
    }
    class CountingAuthority(MappingAuthority):
        def __init__(self, mapping):
            super().__init__(mapping)
            self.calls = []

        def household_for(self, subject):
            self.calls.append(subject)
            return super().household_for(subject)

    authority = CountingAuthority(AUTHORITY.mapping)
    resolver, explainer = resolver_for(nodes, authority)
    assert resolver.explain(root, max_depth=2).status == "available"
    assert explainer.calls.count(shared) == 1
    assert authority.calls.count(shared.subject) >= 3
    resolver.explain(root, max_depth=2)
    assert explainer.calls.count(shared) == 2


def test_memoisation_does_not_hide_cycles_or_provider_state_within_a_call():
    root, child = ref("root"), ref("child")
    cycle, _ = resolver_for({
        "root": node(root, contributions=(Contribution("increases", 1, child, True),)),
        "child": node(child, contributions=(Contribution("increases", 1, root, True),)),
    })
    assert cycle.explain(root, max_depth=2).status == "unavailable"

    root, left, right, shared = ref("stateful.root"), ref("stateful.left"), ref("stateful.right"), ref("stateful.shared")
    calls = 0

    def stateful(reference):
        nonlocal calls
        if reference == shared:
            calls += 1
            return node(reference, kind="observed", quantity=1 if calls == 1 else 99)
        return {
            root: node(root, quantity=2, contributions=(
                Contribution("increases", 1, left, True), Contribution("increases", 1, right, True))),
            left: node(left, contributions=(Contribution("contextual", None, shared, True),)),
            right: node(right, contributions=(Contribution("contextual", None, shared, True),)),
        }[reference]

    class StatefulExplainer:
        def explainable_value_ids(self):
            return frozenset({item.value_id for item in (root, left, right, shared)})

        def explain(self, reference):
            return stateful(reference)

    resolver = ProvenanceResolver(authority=AUTHORITY)
    resolver.register(StatefulExplainer())
    assert resolver.explain(root, max_depth=2).status == "available"
    assert calls == 1


def test_memoisation_scales_provider_work_with_distinct_references_not_paths():
    root, shared = ref("root"), ref("shared")
    branches = tuple(ref(f"branch-{index}") for index in range(8))
    nodes = {
        "root": node(root, quantity=8, contributions=tuple(
            Contribution("increases", 1, branch, True) for branch in branches)),
        "shared": node(shared, kind="observed"),
    }
    nodes.update({
        branch.value_id: node(branch, contributions=(Contribution("contextual", None, shared, True),))
        for branch in branches
    })
    resolver, explainer = resolver_for(nodes)
    assert resolver.explain(root, max_depth=2).status == "available"
    assert len(explainer.calls) == 10
    assert explainer.calls.count(shared) == 1


def test_authority_seam_and_resolver_have_no_writer_or_registry_import_path():
    root = Path(__file__).resolve().parents[1] / "src/foundry/core"
    resolver_source = (root / "value_provenance.py").read_text()
    authority_source = (root / "subject_authority.py").read_text()
    assert "EventLog" not in resolver_source + authority_source
    assert "from .acquisition" not in resolver_source + authority_source
    assert "foundry.finance" not in resolver_source + authority_source
    assert ".append(" not in resolver_source + authority_source

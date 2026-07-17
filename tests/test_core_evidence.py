"""Unit + regression tests: Claim tagging and the Core Evidence Index
(000 §11, §11.1)."""

import pytest

from foundry.canon import Canon
from foundry.core import evidence
from foundry.errors import VocabularyError


def test_tag_claim_rejects_unknown_tag_type(kernel):
    e = kernel.ingest("Alice is the lead.")
    claim = kernel.derive(e["id"])[0]
    with pytest.raises(VocabularyError):
        evidence.tag_claim(kernel.log, claim.id, "not_a_tag_type", "x")


def test_tag_claim_rejects_unknown_value(kernel):
    e = kernel.ingest("Alice is the lead.")
    claim = kernel.derive(e["id"])[0]
    with pytest.raises(VocabularyError):
        evidence.tag_claim(kernel.log, claim.id, "insight_type", "not_a_real_type")


def test_current_tag_is_most_recent(kernel):
    """Reclassification is a new tag event, not an edit — history is
    preserved, but `current_tag` reflects the latest."""
    e = kernel.ingest("Subscription spending is rising.")
    claim = kernel.derive(e["id"])[0]
    evidence.tag_claim(kernel.log, claim.id, "insight_type", "observation")
    evidence.tag_claim(kernel.log, claim.id, "insight_type", "warning")

    index = evidence.EvidenceIndex(kernel.log)
    assert index.current_tag(claim.id, "insight_type") == "warning"
    assert [h.value for h in index.tag_history[claim.id]] == ["observation", "warning"]


def test_concern_and_claims_concerning(kernel):
    e = kernel.ingest("Concentration risk is present.")
    claim = kernel.derive(e["id"])[0]
    evidence.concern(kernel.log, claim.id, "party-123")

    index = evidence.EvidenceIndex(kernel.log)
    assert claim.id in index.claims_concerning("party-123")
    assert index.claims_concerning("someone-else") == frozenset()


def test_link_claim_rejects_relation_outside_structural_vocabulary(kernel):
    e = kernel.ingest("Alice is here.")
    claim = kernel.derive(e["id"])[0]
    with pytest.raises(VocabularyError):
        evidence.link_claim(kernel.log, claim.id, "owns", "target-1")


def test_evidence_index_ignores_events_it_does_not_own(kernel):
    """The index owns only claim.tagged and concerns-relation
    claim.linked — everything else (ingest, claim.derived, core.*)
    passes through untouched, the same fallthrough discipline Canon
    already uses."""
    e = kernel.ingest("Bob prefers option two.")
    kernel.derive(e["id"])
    index = evidence.EvidenceIndex(kernel.log)
    assert index.tags == {}
    assert index.subjects == {}


def test_core_evidence_index_does_not_modify_canon(kernel):
    """The index is a sibling projection, not a change to canon.py:
    Canon still sees only claim.derived/updated/superseded/linked and
    silently ignores claim.tagged, exactly as it already ignores
    bare `ingest` events."""
    e = kernel.ingest("Chris is exposed to a concentrated position.")
    claim = kernel.derive(e["id"])[0]
    evidence.tag_claim(kernel.log, claim.id, "insight_type", "recommendation")

    fresh_canon = Canon(kernel.log)
    assert fresh_canon.get(claim.id) is not None
    assert not hasattr(fresh_canon.get(claim.id), "tags")


def test_rebuild_equals_incremental_apply(kernel):
    """REGRESSION ORACLE for the Evidence Index."""
    e = kernel.ingest("Multiple insights are present for testing.")
    claims = kernel.derive(e["id"])
    for c in claims:
        evidence.tag_claim(kernel.log, c.id, "insight_type", "observation")
        evidence.concern(kernel.log, c.id, "subject-1")

    index = evidence.EvidenceIndex(kernel.log)
    before = (dict(index.tags), {k: set(v) for k, v in index.subjects.items()})
    index.rebuild()
    after = (dict(index.tags), {k: set(v) for k, v in index.subjects.items()})
    assert before == after

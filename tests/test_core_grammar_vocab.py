"""Unit tests: the shared event grammar and controlled vocabularies
(000 §6, §7)."""

import pytest

from foundry.core import grammar, vocab
from foundry.errors import VocabularyError


def test_declare_writes_prefixed_kind(kernel):
    e = grammar.declare(kernel.log, "core", "party", "p1", {"party_type": "person"})
    assert e["kind"] == "core.party.declared"
    assert e["payload"] == {"entity_id": "p1", "party_type": "person"}


def test_update_carries_reason(kernel):
    e = grammar.update(kernel.log, "core", "party", "p1", {"name": "Chris"}, reason="correction")
    assert e["kind"] == "core.party.updated"
    assert e["payload"]["reason"] == "correction"


def test_close_carries_extra_fields(kernel):
    """Mission needs to distinguish `achieved` from `abandoned` without
    a sixth verb — `**extra` on close() is how."""
    e = grammar.close(kernel.log, "core", "mission", "m1", "done", status="achieved")
    assert e["payload"]["status"] == "achieved"


def test_relate_rejects_value_outside_vocabulary(kernel):
    """A relation must never reach the append-only log if it isn't in
    the governed vocabulary — this is checked before the write, not
    after, because a bad write can never be un-written."""
    with pytest.raises(VocabularyError):
        grammar.relate(kernel.log, "core", "party", "p1", "not_a_real_relation",
                        "p2", vocab.PARTY_RELATIONSHIP)
    # And nothing was written:
    assert list(kernel.log.events()) == []


def test_relate_accepts_governed_value(kernel):
    e = grammar.relate(kernel.log, "core", "party", "p1", "member_of", "h1",
                        vocab.PARTY_RELATIONSHIP)
    assert e["payload"] == {"entity_id": "p1", "relation": "member_of", "target": "h1"}


def test_vocabulary_extension_is_additive_only():
    """A domain may extend a core vocabulary; it must never lose what
    was already there (000 §5, principle 4)."""
    v = vocab.ExtensibleVocabulary("test_vocab", {"a", "b"})
    v.extend("c")
    assert v.values == frozenset({"a", "b", "c"})
    assert "a" in v and "c" in v


def test_extending_a_core_vocabulary_shape_does_not_remove_base_values():
    """Exercises the exact extension a domain will perform (Finance
    adding `tax_resident_in` to `party_relationship`), against a
    throwaway copy of the real vocabulary's base values — never the
    shared global singleton itself, which must stay untouched for every
    other test in the process (see vocab.py's module docstring)."""
    core_party_relationship_shape = vocab.ExtensibleVocabulary(
        "party_relationship", set(vocab.PARTY_RELATIONSHIP.values))
    before = core_party_relationship_shape.values

    core_party_relationship_shape.extend("tax_resident_in")

    assert before <= core_party_relationship_shape.values
    assert "tax_resident_in" in core_party_relationship_shape
    assert "member_of" in core_party_relationship_shape  # unchanged
    # And the real, shared global vocabulary was never touched:
    assert "tax_resident_in" not in vocab.PARTY_RELATIONSHIP

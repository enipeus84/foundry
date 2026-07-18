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


def test_extending_a_copy_never_touches_the_shared_global_vocabulary():
    """Exercises the shape of extension a domain performs at its own
    import time (Finance adds `tax_resident_in` to `party_relationship`
    — see foundry.finance.vocab), against a throwaway copy of the real
    vocabulary's base values, proving `.extend()` mutates only the
    object it's called on.

    Uses a value no real domain claims, deliberately: by the time this
    suite runs, `foundry.finance` may already have been imported by
    another test in the same process and legitimately extended the
    *real* shared singleton with `tax_resident_in` — the correct,
    intended effect of the "register on import" pattern vocab.py's own
    docstring prescribes, not something this test polices. What this
    test polices is narrower and still holds regardless: a copy's
    `.extend()` call can never leak into the shared global."""
    core_party_relationship_shape = vocab.ExtensibleVocabulary(
        "party_relationship", set(vocab.PARTY_RELATIONSHIP.values))
    before = core_party_relationship_shape.values

    core_party_relationship_shape.extend("some_other_domains_relation")

    assert before <= core_party_relationship_shape.values
    assert "some_other_domains_relation" in core_party_relationship_shape
    assert "member_of" in core_party_relationship_shape  # unchanged
    # The copy and the real global are different objects — extending
    # the copy can never leak into the shared singleton:
    assert "some_other_domains_relation" not in vocab.PARTY_RELATIONSHIP
    assert core_party_relationship_shape is not vocab.PARTY_RELATIONSHIP

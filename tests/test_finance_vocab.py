"""Unit tests: Finance's own controlled vocabularies and its additive
extensions to Core's (001 §6)."""

import pytest

from foundry.core import vocab as core_vocab
from foundry.errors import VocabularyError
from foundry.finance import vocab


def test_finance_owns_nine_vocabularies():
    assert "checking" in vocab.ACCOUNT_TYPE
    assert "isa" in vocab.TAX_WRAPPER
    assert "property" in vocab.ASSET_CATEGORY
    assert "mortgage" in vocab.LIABILITY_CATEGORY
    assert "housing" in vocab.TRANSACTION_CATEGORY
    assert "co_owner" in vocab.OWNERSHIP_RELATIONSHIP
    assert "liquid" in vocab.LIQUIDITY_CLASSIFICATION
    assert "salary" in vocab.RECURRING_COMMITMENT_TYPE
    assert "observed" in vocab.TAX_ESTIMATION_BASIS


def test_extends_core_party_relationship_with_tax_resident_in():
    """Importing foundry.finance.vocab is what registers the
    extension — the same "register on import" pattern
    foundry.core.vocab prescribes for a dependent domain."""
    assert "tax_resident_in" in core_vocab.PARTY_RELATIONSHIP
    # And the base Core values are untouched, never redefined:
    assert "member_of" in core_vocab.PARTY_RELATIONSHIP
    assert "employed_by" in core_vocab.PARTY_RELATIONSHIP


def test_extends_core_structural_relationship_with_fulfils():
    assert "fulfils" in core_vocab.STRUCTURAL_RELATIONSHIP
    assert "concerns" in core_vocab.STRUCTURAL_RELATIONSHIP


def test_ownership_relationship_is_not_extracted_to_core():
    """001 §6: ownership_relationship stays entirely Finance's own —
    Core's vocab module has no such attribute."""
    assert not hasattr(core_vocab, "OWNERSHIP_RELATIONSHIP")


def test_vocabulary_extension_never_removes_or_redefines_a_value():
    with pytest.raises(AttributeError):
        vocab.ACCOUNT_TYPE.values.remove("checking")  # frozenset — no mutation possible

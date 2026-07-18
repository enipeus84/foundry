"""
Controlled vocabularies — 001-finance-domain-model.md §6.

Finance-owned, additive, never redefined — the identical discipline
`foundry.core.vocab` documents for Core's own vocabularies. Two of
Core's vocabularies are additively extended here, at import time, the
same "register on import" pattern `foundry.core.vocab` itself
prescribes for a dependent domain: `party_relationship` gains
`tax_resident_in`, `structural_relationship` gains `fulfils`. Neither
extension redefines or repurposes an existing Core value.

`ownership_relationship` is deliberately *not* extracted to Core — it
describes legal/financial ownership of a value-bearing resource, which
001 §6 names as inherently Finance's concept.
"""

from __future__ import annotations

from foundry.core import vocab as core_vocab
from foundry.core.vocab import ExtensibleVocabulary

ACCOUNT_TYPE = ExtensibleVocabulary(
    "account_type",
    {"checking", "savings", "credit_card", "loan", "mortgage",
     "brokerage", "pension", "other"},
)

TAX_WRAPPER = ExtensibleVocabulary(
    "tax_wrapper",
    {"none", "isa", "pension_wrapper", "gia_taxable", "other"},
)

ASSET_CATEGORY = ExtensibleVocabulary(
    "asset_category",
    {"property", "vehicle", "collectible", "private_equity",
     "cash_equivalent", "other"},
)

LIABILITY_CATEGORY = ExtensibleVocabulary(
    "liability_category",
    {"mortgage", "personal_loan", "credit_card_debt", "informal_loan", "other"},
)

TRANSACTION_CATEGORY = ExtensibleVocabulary(
    "transaction_category",
    {"income", "housing", "transport", "groceries", "childcare", "education",
     "healthcare", "discretionary", "savings_transfer", "investment_contribution",
     "pension_contribution", "tax_payment", "other"},
)

OWNERSHIP_RELATIONSHIP = ExtensibleVocabulary(
    "ownership_relationship",
    {"owner", "co_owner", "beneficial_owner", "custodian", "beneficiary",
     "owes", "guarantees", "secures", "collateralises"},
)

LIQUIDITY_CLASSIFICATION = ExtensibleVocabulary(
    "liquidity_classification",
    {"liquid", "near_liquid", "illiquid_short", "illiquid_long"},
)

RECURRING_COMMITMENT_TYPE = ExtensibleVocabulary(
    "recurring_commitment_type",
    {"salary", "pension_contribution", "mortgage_payment", "regular_expense",
     "savings_contribution", "investment_contribution", "child_contribution"},
)

TAX_ESTIMATION_BASIS = ExtensibleVocabulary(
    "tax_estimation_basis",
    {"observed", "estimated", "derived", "unsupported"},
)

# --------------------------------------------------- Core vocabulary extensions

core_vocab.PARTY_RELATIONSHIP.extend("tax_resident_in")
core_vocab.STRUCTURAL_RELATIONSHIP.extend("fulfils")

# Relations that confer ownership of *value* for aggregation purposes
# (001 §9's net-worth union rule) — a deliberate subset of
# OWNERSHIP_RELATIONSHIP: `custodian` and `beneficiary` describe a
# stewardship or future entitlement, not present-day economic value,
# so they are excluded from what a household/individual "holds" today.
# `owes`/`guarantees`/`secures`/`collateralises` are liability-side
# relations, handled separately. This subset is a V1 product judgement,
# not a 001 requirement — see docs/rfc-002-implementation-report.md.
VALUE_OWNERSHIP_RELATIONS = frozenset({"owner", "co_owner", "beneficial_owner"})
LIABILITY_RELATIONS = frozenset({"owes"})

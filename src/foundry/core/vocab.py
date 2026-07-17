"""
Controlled vocabularies — 000-core-domain-model.md §7.

Core-owned, additive, extensible by dependent domains, never redefined
(design principle 4). A vocabulary here starts with Core's base values;
a domain spec may `.extend()` it with its own additive values (Finance
adds `tax_resident_in` to `party_relationship`, for example) but may
never remove or repurpose an existing one — the same append-only
discipline the event log itself enforces, applied to classification
values instead of events.

RFC-001 implements the vocabularies themselves and the extension
mechanism; no domain package exists yet to call `.extend()`; a test
still exercises it directly to prove the contract holds.

Each vocabulary below is a **process-global singleton**, intentionally
— a controlled value, once added, is schema, not per-instance data
(unlike `MetricRegistry`, which genuinely differs per application or
test and is constructed fresh each time). A domain package extends one
by calling `.extend()` on the shared object, typically once, at its own
module's import time — the same "register on import" pattern
`codecs.register()`/`mimetypes.add_type()` already use in the stdlib.
`.extend()` is idempotent (backed by `set.update`), so calling it
repeatedly is harmless. **Tests must not mutate a shared vocabulary
in place** — construct a throwaway `ExtensibleVocabulary` instead, or
process-order-dependent test pollution follows.
"""

from __future__ import annotations


class ExtensibleVocabulary:
    """A named, additive-only set of controlled values."""

    def __init__(self, name: str, base_values: set[str]):
        self.name = name
        self._values = set(base_values)

    def __contains__(self, value: str) -> bool:
        return value in self._values

    def __iter__(self):
        return iter(self._values)

    @property
    def values(self) -> frozenset[str]:
        return frozenset(self._values)

    def extend(self, *new_values: str) -> None:
        """Add one or more values. Never removes or redefines an
        existing one — the only mutation this type permits."""
        self._values.update(new_values)

    def __repr__(self) -> str:
        return f"ExtensibleVocabulary({self.name!r}, {sorted(self._values)!r})"


PARTY_TYPE = ExtensibleVocabulary("party_type", {"person", "household"})

PARTY_RELATIONSHIP = ExtensibleVocabulary(
    "party_relationship", {"member_of", "employed_by"})

STRUCTURAL_RELATIONSHIP = ExtensibleVocabulary(
    "structural_relationship",
    {"concerns", "informed_by", "modelled_by", "outcome_of",
     "reviews", "executes", "revises"},
)

TAG_TYPE = ExtensibleVocabulary("tag_type", {"insight_type", "review_verdict"})

INSIGHT_TYPE = ExtensibleVocabulary(
    "insight_type",
    {"observation", "interpretation", "vulnerability", "opportunity",
     "recommendation", "warning", "review"},
)

REVIEW_VERDICT = ExtensibleVocabulary(
    "review_verdict",
    {"achieved", "partially_achieved", "not_achieved", "inconclusive"},
)

MISSION_STATUS = ExtensibleVocabulary(
    "mission_status",
    {"on_track", "at_risk", "off_track", "achieved", "abandoned"},
)

METRIC_STATUS = ExtensibleVocabulary(
    "metric_status",
    {"available", "unavailable", "unsupported", "stale", "error"},
)

# tag_type -> the vocabulary its value must belong to.
TAG_VALUE_VOCAB: dict[str, ExtensibleVocabulary] = {
    "insight_type": INSIGHT_TYPE,
    "review_verdict": REVIEW_VERDICT,
}

"""
Evidence model & the Core Evidence Index — 000-core-domain-model.md
§11, §11.1.

Interpreted knowledge is always a `Claim` in the existing `Canon` — no
domain may introduce a parallel claim system. A Claim's classification
is a *typed tag* (`claim.tagged`), never a relationship; its scope
attribution is a *relationship* (`claim.linked {relation: "concerns"}`)
via the identical mechanism `kernel.link()` already provides. Both are
appended directly against the `EventLog` here rather than through
`Kernel`, because a Decision Review Claim's provenance is a Decision
and its Outcome, not an `ingest` event — `kernel.derive()` is gated to
`ingest`-sourced events only, so Core bypasses it exactly as
`kernel.ingest()` itself is nothing but a thin wrapper over the same
`EventLog.append` call (000 §6).

The Core Evidence Index is a *second* projection, a sibling to `Canon`,
not a modification of it: `Canon._apply` already ignores event kinds it
doesn't fold (the same fallthrough that already skips bare `ingest`
events), so `claim.tagged` and the `concerns`-relation subset of
`claim.linked` pass through it untouched. Storing this state *inside*
`Claim` itself — adding a `tags` field to the dataclass in `canon.py`
— is precisely what this design avoids by keeping the index external,
additive, and shared: exactly one index, queried by every domain,
never duplicated per domain.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from foundry.eventlog import EventLog

from . import grammar, vocab
from ..errors import VocabularyError


# --------------------------------------------------------------- writes

def derive_claim_directly(log: EventLog, statement: str, confidence: float,
                           evidence: list[str], provenance: list[str],
                           actor: str) -> tuple[dict, str]:
    """Append a `claim.derived` event whose provenance is *not*
    necessarily an `ingest` event id (a Decision Review's provenance is
    a Decision's and Decision Outcome's event ids). Bypasses
    `kernel.derive()` deliberately — see module docstring."""
    claim_id = grammar.new_id()
    payload = {
        "claim_id": claim_id, "statement": statement,
        "confidence": max(0.0, min(1.0, confidence)),
        "evidence": list(evidence), "provenance": list(provenance),
    }
    event = log.append("claim.derived", payload, actor=actor)
    return event, claim_id


def tag_claim(log: EventLog, claim_id: str, tag_type: str, value: str,
              reason: str | None = None, actor: str = "user") -> dict:
    """`claim.tagged` — a classification, never a relationship (design
    principle 2). Validated against the controlled vocabulary the
    `tag_type` names before it's written."""
    if tag_type not in vocab.TAG_TYPE:
        raise VocabularyError(f"{tag_type!r} is not a valid tag_type")
    value_vocab = vocab.TAG_VALUE_VOCAB.get(tag_type)
    if value_vocab is not None and value not in value_vocab:
        raise VocabularyError(f"{value!r} is not a valid {tag_type} value")
    payload = {"claim_id": claim_id, "tag_type": tag_type, "value": value}
    if reason is not None:
        payload["reason"] = reason
    return log.append("claim.tagged", payload, actor=actor)


def link_claim(log: EventLog, claim_id: str, relation: str, target: str,
               actor: str = "user") -> dict:
    """`claim.linked` — a relationship to another addressable entity.
    `relation` must be a `structural_relationship` value."""
    if relation not in vocab.STRUCTURAL_RELATIONSHIP:
        raise VocabularyError(f"{relation!r} is not a valid structural_relationship")
    payload = {"claim_id": claim_id, "relation": relation, "target": target}
    return log.append("claim.linked", payload, actor=actor)


def concern(log: EventLog, claim_id: str, subject_id: str, actor: str = "user") -> dict:
    """Scope-attribute a Claim to a subject (000 §10)."""
    return link_claim(log, claim_id, "concerns", subject_id, actor=actor)


# ---------------------------------------------------------------- reads

@dataclass
class TagEvent:
    tag_type: str
    value: str
    event_id: str


class EvidenceIndex:
    """The one shared Core Evidence Index (000 §11.1). Folds
    `claim.tagged` and `concerns`-relation `claim.linked` events into
    two lookups: current tags per claim, and claims per subject.
    Deletable and rebuildable, with no write path of its own."""

    def __init__(self, log: EventLog):
        self.log = log
        self.tags: dict[str, dict[str, str]] = {}
        self.tag_history: dict[str, list[TagEvent]] = {}
        self.subjects: dict[str, set[str]] = {}
        self.rebuild()

    def rebuild(self) -> None:
        self.tags, self.tag_history, self.subjects = {}, {}, {}
        for e in self.log.events():
            self.apply(e)

    def apply(self, e: dict) -> None:
        kind = e["kind"]
        if kind == "claim.tagged":
            p = e["payload"]
            cid = p["claim_id"]
            self.tags.setdefault(cid, {})[p["tag_type"]] = p["value"]
            self.tag_history.setdefault(cid, []).append(
                TagEvent(tag_type=p["tag_type"], value=p["value"], event_id=e["id"]))
        elif kind == "claim.linked":
            p = e["payload"]
            if p.get("relation") == "concerns":
                self.subjects.setdefault(p["target"], set()).add(p["claim_id"])
        # Every other event kind (claim.derived/updated/superseded,
        # core.*, finance.*, ingest) is silently ignored — this index
        # owns only classification and scope attribution.

    def current_tag(self, claim_id: str, tag_type: str) -> str | None:
        return self.tags.get(claim_id, {}).get(tag_type)

    def claims_concerning(self, subject_id: str) -> frozenset[str]:
        return frozenset(self.subjects.get(subject_id, set()))

    def claims_tagged(self, tag_type: str, value: str) -> frozenset[str]:
        return frozenset(cid for cid, current in self.tags.items()
                          if current.get(tag_type) == value)

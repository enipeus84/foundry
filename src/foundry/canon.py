"""
Canon — derived knowledge.

The Canon is NOT a second store of truth. It is a projection (a
materialised view) computed by replaying the event log. Delete it,
replay the log, and you get an identical Canon back.

This resolves an internal tension in the original brief:

    "Claims may evolve. Events never do."

If claims evolved by in-place mutation, the evolution itself would be
unprovenanced — you could ask "why do you believe this?" but not
"why did you *stop* believing what you believed yesterday?". So claim
mutations are events too:

    claim.derived     — a model or human asserted a new claim
    claim.updated     — statement/confidence revised (with reason)
    claim.superseded  — claim replaced by another claim
    claim.linked      — relationship asserted between two claims

The Canon replays these into current state. Full history remains in
the log forever.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .eventlog import EventLog


@dataclass
class Claim:
    id: str
    statement: str
    confidence: float
    provenance: list[str] = field(default_factory=list)   # source event ids
    evidence: list[str] = field(default_factory=list)     # verbatim supporting text
    derived_by: str = ""                                   # actor (model) identity
    ts: float = 0.0
    status: str = "active"                                 # active | superseded
    superseded_by: str | None = None
    links: list[dict] = field(default_factory=list)        # {relation, target}
    history: list[str] = field(default_factory=list)       # event ids that shaped it

    def to_dict(self) -> dict:
        return self.__dict__.copy()


class Canon:
    """Current-state view of all claims, rebuilt from the log on demand."""

    def __init__(self, log: EventLog):
        self.log = log
        self.claims: dict[str, Claim] = {}
        self.rebuild()

    def rebuild(self) -> None:
        """Replay the entire event log from scratch.

        This is the correctness oracle: `apply()` exists purely as an
        optimisation, and a rebuilt Canon must always equal an
        incrementally-maintained one (enforced by regression tests).
        """
        self.claims = {}
        for e in self.log.events():
            self.apply(e)

    # ---------------------------------------------------------------- replay

    def apply(self, e: dict) -> None:
        """Fold ONE event into current state. Idempotence is not
        required — the log is append-only and each event is applied
        exactly once per replay."""
        self._apply(e)

    def _apply(self, e: dict) -> None:
        kind, p = e["kind"], e["payload"]
        if kind == "claim.derived":
            self.claims[p["claim_id"]] = Claim(
                id=p["claim_id"],
                statement=p["statement"],
                confidence=p["confidence"],
                provenance=p.get("provenance", []),
                evidence=p.get("evidence", []),
                derived_by=e["actor"],
                ts=e["ts"],
                history=[e["id"]],
            )
        elif kind == "claim.updated":
            c = self.claims.get(p["claim_id"])
            if c:
                c.statement = p.get("statement", c.statement)
                c.confidence = p.get("confidence", c.confidence)
                if p.get("evidence"):
                    c.evidence.extend(p["evidence"])
                if p.get("provenance"):
                    c.provenance.extend(p["provenance"])
                c.history.append(e["id"])
        elif kind == "claim.superseded":
            c = self.claims.get(p["claim_id"])
            if c:
                c.status = "superseded"
                c.superseded_by = p.get("superseded_by")
                c.history.append(e["id"])
        elif kind == "claim.linked":
            c = self.claims.get(p["claim_id"])
            if c:
                c.links.append({"relation": p["relation"], "target": p["target"]})
                c.history.append(e["id"])

    # ----------------------------------------------------------------- query

    def active(self) -> list[Claim]:
        return [c for c in self.claims.values() if c.status == "active"]

    def get(self, claim_id: str) -> Claim | None:
        return self.claims.get(claim_id)

    def explain(self, claim_id: str) -> dict[str, Any] | None:
        """
        Full provenance answer to "why do you believe this?":
        source events, extraction actor, evidence, revision history.
        """
        c = self.get(claim_id)
        if not c:
            return None
        return {
            "claim": c.statement,
            "confidence": c.confidence,
            "derived_by": c.derived_by,
            "evidence": c.evidence,
            "source_events": [self.log.get(eid) for eid in c.provenance],
            "revision_events": [self.log.get(eid) for eid in c.history],
            "status": c.status,
        }

"""
Decision lifecycle — 000-core-domain-model.md §12.

    Observation -> Understanding -> Decision -> Execution -> Outcome
    -> Reflection -> Learning

A domain supplies Observation and Understanding; everything from
Decision onward lives here, once, so a future Career decision needs no
lifecycle of its own.

Decision and Decision Outcome are entities (`core.decision.*`,
`core.decision_outcome.*`), folded by `DecisionProjection`. Execution is
*not* an entity — it is whichever domain-specific mutation events carry
the decision out, linked back via `executes`; a domain appends its own
`<prefix>.<type>.linked` event for that, which this module does not
provide (Core does not know a domain's entity types, 000 §3). Decision
Review is *not* an entity either — it is a `Claim`, built from
`evidence.py`'s primitives, so "lessons learned become future evidence"
costs no new machinery: a Decision Review Claim is retrievable, citable
via `why()`, and referenceable by a later Decision's `informed_by` link
exactly like any other Claim.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from foundry.eventlog import EventLog

from . import evidence, grammar, vocab

PREFIX = "core"


@dataclass
class Decision:
    id: str
    statement: str
    rationale: str = ""
    expected_outcome: str = ""
    actor: str = ""
    ts: float = 0.0
    modelled_by: str | None = None
    revises: str | None = None
    informed_by: list[str] = field(default_factory=list)
    concerns: list[str] = field(default_factory=list)
    provenance: list[str] = field(default_factory=list)
    history: list[str] = field(default_factory=list)


@dataclass
class DecisionOutcome:
    id: str
    decision_id: str
    observed_metric: str
    observed_value: float
    observed_at: float
    concerns: list[str] = field(default_factory=list)
    provenance: list[str] = field(default_factory=list)
    history: list[str] = field(default_factory=list)


# --------------------------------------------------------------- writes

def declare_decision(log: EventLog, statement: str, rationale: str = "",
                      expected_outcome: str = "", actor: str = "user") -> Decision:
    decision_id = grammar.new_id()
    e = grammar.declare(log, PREFIX, "decision", decision_id, {
        "statement": statement, "rationale": rationale,
        "expected_outcome": expected_outcome,
    }, actor=actor)
    return Decision(id=decision_id, statement=statement, rationale=rationale,
                     expected_outcome=expected_outcome, actor=actor, ts=e["ts"],
                     provenance=[e["id"]], history=[e["id"]])


def concern_decision(log: EventLog, decision_id: str, subject_id: str, actor: str = "user") -> dict:
    return grammar.relate(log, PREFIX, "decision", decision_id, "concerns",
                           subject_id, vocab.STRUCTURAL_RELATIONSHIP, actor=actor)


def inform_decision(log: EventLog, decision_id: str, claim_or_scenario_id: str,
                     actor: str = "user") -> dict:
    return grammar.relate(log, PREFIX, "decision", decision_id, "informed_by",
                           claim_or_scenario_id, vocab.STRUCTURAL_RELATIONSHIP, actor=actor)


def model_decision(log: EventLog, decision_id: str, model_id: str, actor: str = "user") -> dict:
    return grammar.relate(log, PREFIX, "decision", decision_id, "modelled_by",
                           model_id, vocab.STRUCTURAL_RELATIONSHIP, actor=actor)


def revise_decision(log: EventLog, new_decision_id: str, superseded_decision_id: str,
                     actor: str = "user") -> dict:
    return grammar.relate(log, PREFIX, "decision", new_decision_id, "revises",
                           superseded_decision_id, vocab.STRUCTURAL_RELATIONSHIP, actor=actor)


def declare_outcome(log: EventLog, decision: Decision, observed_metric: str,
                     observed_value: float, observed_at: float,
                     actor: str = "user") -> DecisionOutcome:
    outcome_id = grammar.new_id()
    e = grammar.declare(log, PREFIX, "decision_outcome", outcome_id, {
        "decision_id": decision.id, "observed_metric": observed_metric,
        "observed_value": observed_value, "observed_at": observed_at,
    }, actor=actor)
    grammar.relate(log, PREFIX, "decision_outcome", outcome_id, "outcome_of",
                    decision.id, vocab.STRUCTURAL_RELATIONSHIP, actor=actor)
    return DecisionOutcome(id=outcome_id, decision_id=decision.id,
                            observed_metric=observed_metric, observed_value=observed_value,
                            observed_at=observed_at, provenance=[e["id"]], history=[e["id"]])


def concern_outcome(log: EventLog, outcome_id: str, subject_id: str, actor: str = "user") -> dict:
    return grammar.relate(log, PREFIX, "decision_outcome", outcome_id, "concerns",
                           subject_id, vocab.STRUCTURAL_RELATIONSHIP, actor=actor)


def declare_review(log: EventLog, decision: Decision, outcome: DecisionOutcome,
                    statement: str, review_verdict: str, concerns: list[str] = (),
                    confidence: float = 1.0, evidence_text: str = "",
                    actor: str = "user") -> str:
    """Reflection: a `Claim`, not an entity. `provenance` is the
    Decision's and Decision Outcome's *event* ids (not entity ids, and
    not an `ingest` event) — the direct, spec-sanctioned use of
    `Claim.provenance` `000` §12 describes. Returns the new claim id.

    `concerns` is taken as an explicit parameter rather than read off
    `decision.concerns`, deliberately: `Decision` objects are plain,
    unmutated snapshots (this module never mutates one in place after
    returning it, per constitutional invariant 2 — state lives in the
    log, not in a cached object), so a `Decision` returned by
    `declare_decision()` before any `concern_decision()` calls would be
    stale by the time a review is written. Passing `concerns`
    explicitly — typically read from a fresh `DecisionProjection` — has
    no way to go stale."""
    event, claim_id = evidence.derive_claim_directly(
        log, statement=statement, confidence=confidence,
        evidence=[evidence_text or statement],
        provenance=[*decision.provenance, *outcome.provenance], actor=actor,
    )
    evidence.tag_claim(log, claim_id, "insight_type", "review", actor=actor)
    evidence.tag_claim(log, claim_id, "review_verdict", review_verdict, actor=actor)
    evidence.link_claim(log, claim_id, "reviews", decision.id, actor=actor)
    for subject_id in concerns:
        evidence.concern(log, claim_id, subject_id, actor=actor)
    return claim_id


# ---------------------------------------------------------------- reads

class DecisionProjection:
    """Current Decision/Decision Outcome state, folded from
    `core.decision.*`/`core.decision_outcome.*` events. Deletable and
    rebuildable; `apply()` and `rebuild()` must always agree."""

    def __init__(self, log: EventLog):
        self.log = log
        self.decisions: dict[str, Decision] = {}
        self.outcomes: dict[str, DecisionOutcome] = {}
        self.rebuild()

    def rebuild(self) -> None:
        self.decisions, self.outcomes = {}, {}
        for e in self.log.events():
            self.apply(e)

    def apply(self, e: dict) -> None:
        kind = e["kind"]
        if kind.startswith("core.decision_outcome."):
            self._apply_outcome(e)
        elif kind.startswith("core.decision."):
            self._apply_decision(e)

    def executions_of(self, decision_id: str) -> list[dict]:
        """Every event, of any domain's own prefix, linked `executes`
        to this Decision — the read-side half of Execution (000 §12),
        found by scanning for the relation rather than owning a stream."""
        out = []
        for e in self.log.events():
            if not e["kind"].endswith(".linked"):
                continue
            p = e["payload"]
            if p.get("relation") == "executes" and p.get("target") == decision_id:
                out.append(e)
        return out

    # -------------------------------------------------------- internals

    def _apply_decision(self, e: dict) -> None:
        verb = e["kind"].rsplit(".", 1)[-1]
        p = e["payload"]
        did = p["entity_id"]
        if verb == "declared":
            self.decisions[did] = Decision(
                id=did, statement=p["statement"], rationale=p.get("rationale", ""),
                expected_outcome=p.get("expected_outcome", ""), actor=e["actor"], ts=e["ts"],
                provenance=[e["id"]], history=[e["id"]],
            )
        elif verb == "linked":
            d = self.decisions.get(did)
            if d:
                rel, target = p["relation"], p["target"]
                if rel == "concerns":
                    d.concerns.append(target)
                elif rel == "informed_by":
                    d.informed_by.append(target)
                elif rel == "modelled_by":
                    d.modelled_by = target
                elif rel == "revises":
                    d.revises = target
                d.history.append(e["id"])

    def _apply_outcome(self, e: dict) -> None:
        verb = e["kind"].rsplit(".", 1)[-1]
        p = e["payload"]
        oid = p["entity_id"]
        if verb == "declared":
            self.outcomes[oid] = DecisionOutcome(
                id=oid, decision_id=p["decision_id"], observed_metric=p["observed_metric"],
                observed_value=p["observed_value"], observed_at=p["observed_at"],
                provenance=[e["id"]], history=[e["id"]],
            )
        elif verb == "linked":
            o = self.outcomes.get(oid)
            if o:
                if p["relation"] == "concerns":
                    o.concerns.append(p["target"])
                o.history.append(e["id"])

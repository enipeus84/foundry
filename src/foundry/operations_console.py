"""The RFC-012 Operations Console Model.

A deterministic fold from RFC-011 projections to a classified, ordered
attention queue.  It selects and orders; it never computes.  Every value it
carries is a lens result the platform already produced, and every mutation the
console can cause travels the existing provider and confirmation gate.

The attention taxonomy and the ordering policy defined here belong to this
versioned model, not to Core (RFC-012 A4/AC-6).  The underlying facts remain
owned by RFC-011 and the domain lenses.

Nothing in this module persists anything: no event, no store, no cache
(AC-3, AC-5).  There is no defer, dismiss, acknowledgement or suppression --
an item clears only when its underlying fact resolves.

Phase 1A note: two architecturally-defined attention kinds are deliberately
not emitted because the current platform contract cannot support them
honestly.  See ``UNIMPLEMENTABLE_IN_PHASE_1A``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .core.acquisition import (
    AssetRegistry,
    EnvelopeProjection,
    ProposalInbox,
    TelemetryStreamRegistry,
    ValuationLenses,
    _CADENCE_SECONDS,
    _digest,
)

MODEL_VERSION = "operations-console@1"

#: Closed V1 attention vocabulary.  Owned by this model (RFC-012 §4.3),
#: deliberately absent from ``core.vocab``.
ATTENTION_KIND = (
    "identity_ambiguous",
    "proposal_pending",
    "unknown_material",
    "reconciliation_divergence",
    "telemetry_stale",
    "valuation_expiring",
)

#: Kinds the frozen architecture defines but the current platform contract
#: cannot yet support without inventing a fact.  Emitting them would be worse
#: than omitting them, because V1 has no dismissal: a false item can never be
#: cleared by the operator.  Both are return-to-architecture items.
#:
#: ``reconciliation_divergence`` -- classifying divergence requires deciding
#: monetary equality.  ``Reconciliation.difference`` is an IEEE-754 float, so
#: an exact test reports 3.0 x 0.1 against 0.3 as divergent forever.  The
#: platform defines no Decimal type, no quantisation contract and no currency
#: precision rules, and an ad hoc epsilon here would be this model inventing
#: financial materiality -- exactly what RFC-012 §3.2 and §4.5 forbid.
#:
#: ``valuation_expiring`` -- separating it from ``telemetry_stale`` requires an
#: authoritative estimate-basis signal.  ``TelemetryStream.property`` is an
#: unconstrained string, so any split on its text would be a naming heuristic.
UNIMPLEMENTABLE_IN_PHASE_1A = frozenset({
    "reconciliation_divergence",
    "valuation_expiring",
})

#: Primary action offered per kind.  Every item has an exit (RFC-012 §4.2).
_ACTION = {
    "identity_ambiguous": "resolve",
    "proposal_pending": "review",
    "unknown_material": "capture",
    "reconciliation_divergence": "investigate",
    "telemetry_stale": "capture",
    "valuation_expiring": "capture",
}

#: Ordering classes of RFC-012 §4.5.  ``(class_rank, sub_rank)``; the
#: within-class key and the stable identifier complete the total order.
#:
#: Class 3 (reconciliation) is declared for completeness.  §4.5 requires
#: "longest-standing divergence first, by the finding's ``valid_at``", but
#: ``Reconciliation`` carries no temporal field, so that rule is not
#: implementable; the Governor's Phase 1A ruling is stable identifier
#: ascending, which is what the ``within_class`` default of 0.0 produces.
_ORDER_CLASS = {
    "identity_ambiguous": (1, 0),
    "proposal_pending": (1, 1),
    "unknown_material": (2, 0),
    "reconciliation_divergence": (3, 0),
    "telemetry_stale": (4, 0),
    "valuation_expiring": (4, 0),
}

#: Kinds whose identity is the proposal, not the subject.  Two pending
#: proposals on one stream are two evidence bundles and two confirmation-gate
#: decisions, so they must never collapse into one item (SAFE-33-01).
_PROPOSAL_IDENTIFIED = frozenset({"proposal_pending", "identity_ambiguous"})

#: Kinds whose identity is the stream: distinct streams on one subject are
#: distinct work (a stale price and a stale unit count are two captures).
_STREAM_IDENTIFIED = frozenset({"telemetry_stale", "valuation_expiring"})

#: A material unknown is an active item, but it is not work the operator can
#: discharge -- the value is unavailable, not merely uncaptured.  It therefore
#: does not block "all actionable work completed" while still forbidding
#: "all telemetry nominal" (RFC-012 §4.4).
_NON_ACTIONABLE = frozenset({"unknown_material"})

TERMINAL_ALL_NOMINAL = "all_nominal"
TERMINAL_ACTIONABLE_COMPLETE = "actionable_complete"
TERMINAL_WORK_PENDING = "work_pending"


def attention_identity(kind: str, *, subject_id: str, stream_id: str | None,
                       proposal_id: str | None) -> tuple[str, ...]:
    """The deduplication and tie-break identity for one item.

    Identity is chosen per item source rather than forced through one
    universal key: aggregation *scope* must never multiply work, but two
    genuinely distinct proposals, or two distinct streams, are genuinely
    distinct work.  Components stay structural (a tuple) so no delimiter can
    be confused with data.
    """
    if kind in _PROPOSAL_IDENTIFIED:
        return (kind, proposal_id or "")
    if kind in _STREAM_IDENTIFIED:
        return (kind, subject_id, stream_id or "")
    return (kind, subject_id)


@dataclass(frozen=True)
class AttentionItem:
    """One unit of operational work, derived never stored."""

    kind: str
    subject_id: str
    action: str
    summary: str
    stream_id: str | None = None
    proposal_id: str | None = None
    evidence_id: str | None = None
    #: Ordering inputs, all authoritative platform facts (RFC-012 §4.5).
    class_rank: int = 9
    sub_rank: int = 0
    within_class: float = 0.0

    @property
    def identity(self) -> tuple[str, ...]:
        return attention_identity(self.kind, subject_id=self.subject_id,
                                  stream_id=self.stream_id,
                                  proposal_id=self.proposal_id)

    @property
    def stable_id(self) -> str:
        """Deterministic digest over canonical JSON of the structural identity.

        A digest rather than a delimiter join: joining unescaped components
        lets ``("a|b", "c")`` and ``("a", "b|c")`` collide, after which ties
        fall to dict insertion order (SAFE-33-06).  ``_digest`` is the
        platform's own canonical encoding (sorted-key JSON + SHA-256), so this
        is stable across processes -- unlike Python's randomised ``hash()``.
        """
        return _digest(list(self.identity))

    @property
    def actionable(self) -> bool:
        return self.kind not in _NON_ACTIONABLE

    def sort_key(self) -> tuple[int, int, float, str]:
        return (self.class_rank, self.sub_rank, self.within_class, self.stable_id)

    def as_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "subject_id": self.subject_id, "action": self.action,
                "summary": self.summary, "stream_id": self.stream_id,
                "proposal_id": self.proposal_id, "evidence_id": self.evidence_id,
                "stable_id": self.stable_id, "actionable": self.actionable}


def _count(count: int, noun: str) -> str:
    return f"{count} {noun}{'' if count == 1 else 's'}"


@dataclass(frozen=True)
class OperationsConsoleView:
    """The whole rendered surface as data.  The renderer adds no facts."""

    items: tuple[AttentionItem, ...]
    terminal_state: str
    as_of: float
    model_version: str
    fresh_stream_count: int
    unknown_count: int
    retired_stream_count: int

    @property
    def nominal(self) -> bool:
        return self.terminal_state == TERMINAL_ALL_NOMINAL

    def summary_line(self) -> str:
        """The one sentence the operator reads.  Never claims false quiet."""
        unknowns = (f"{_count(self.unknown_count, 'material value')} "
                    f"{'remains' if self.unknown_count == 1 else 'remain'} unavailable.")
        if self.terminal_state == TERMINAL_ALL_NOMINAL:
            if self.retired_stream_count and not self.fresh_stream_count:
                return ("No active telemetry requires an update. "
                        f"{_count(self.retired_stream_count, 'retired stream')} "
                        "intentionally suppressed.")
            return (f"All telemetry nominal - {self.fresh_stream_count} "
                    f"streams fresh as of {self.as_of:.0f}.")
        if self.terminal_state == TERMINAL_ACTIONABLE_COMPLETE:
            return f"All actionable work completed. {unknowns}"
        actionable = sum(1 for item in self.items if item.actionable)
        line = f"{_count(actionable, 'item')} {'needs' if actionable == 1 else 'need'} attention."
        if self.unknown_count:
            # Never let the count the operator reads hide a material unknown.
            line = f"{line} {unknowns}"
        return line

    def as_dict(self) -> dict[str, Any]:
        return {"model_version": self.model_version, "as_of": self.as_of,
                "terminal_state": self.terminal_state, "nominal": self.nominal,
                "summary": self.summary_line(),
                "items": [item.as_dict() for item in self.items],
                "retired_stream_count": self.retired_stream_count}


class OperationsConsoleModel:
    """Deterministic fold over RFC-011 projections (RFC-012 §4.1).

    Same log and same clock yield a byte-identical view (AC-2).  Construction
    takes projections, not a log, so the model cannot append.
    """

    version = MODEL_VERSION

    def __init__(self, registry: AssetRegistry, streams: TelemetryStreamRegistry,
                 inbox: ProposalInbox, lenses: ValuationLenses,
                 envelopes: EnvelopeProjection):
        self.registry = registry
        self.streams = streams
        self.inbox = inbox
        self.lenses = lenses
        self.envelopes = envelopes

    # -- item derivation, one private method per authoritative fact ---------

    def _proposal_items(self, household_id: str) -> list[AttentionItem]:
        items: list[AttentionItem] = []
        for proposal in self.inbox.proposals.values():
            if proposal.state != "pending" or proposal.household_id != household_id:
                continue
            stream = self.streams.streams.get(proposal.stream_id)
            if stream is None or not self.streams.is_active(proposal.stream_id):
                # A proposal whose stream declaration is absent has no
                # authoritative subject.  Presenting the stream id in the
                # subject field would misreport identity (SAFE-33-08).
                continue
            envelope = self.envelopes.envelopes.get(proposal.envelope_id)
            received_at = envelope.received_at if envelope else 0.0
            blocked = any(resolution.get("outcome") in {"ambiguous", "unresolved"}
                          for resolution in proposal.resolutions)
            kind = "identity_ambiguous" if blocked else "proposal_pending"
            summary = ("Identity unresolved; confirmation is blocked."
                       if blocked else "Proposal awaiting review.")
            class_rank, sub_rank = _ORDER_CLASS[kind]
            items.append(AttentionItem(
                kind=kind, subject_id=stream.subject_id, action=_ACTION[kind],
                summary=summary, stream_id=proposal.stream_id, proposal_id=proposal.id,
                evidence_id=proposal.evidence_id,
                class_rank=class_rank, sub_rank=sub_rank, within_class=received_at))
        return items

    def _freshness_items(self, household_id: str, *, as_of: float,
                         known_at: float) -> list[AttentionItem]:
        items: list[AttentionItem] = []
        for stream in self.streams.streams.values():
            if stream.household_id != household_id or not self.streams.is_active(stream.id):
                continue
            state = self.lenses.stream_freshness(stream.id, as_of=as_of, known_at=known_at)
            if state != "stale":
                continue
            breach = self._breach_seconds(stream.id, as_of=as_of, known_at=known_at,
                                          policy=stream.refresh_policy)
            # Every breach is telemetry_stale in Phase 1A.  Splitting out
            # valuation_expiring would require an authoritative estimate-basis
            # signal the stream contract does not carry.
            kind = "telemetry_stale"
            class_rank, sub_rank = _ORDER_CLASS[kind]
            items.append(AttentionItem(
                kind=kind, subject_id=stream.subject_id, action=_ACTION[kind],
                summary=(f"{stream.property} breached its {stream.refresh_policy} "
                         f"cadence by {breach / 86400:.0f}d."),
                stream_id=stream.id,
                # Longest overdue first: negate so ascending sort descends duration.
                class_rank=class_rank, sub_rank=sub_rank, within_class=-breach))
        return items

    def _breach_seconds(self, stream_id: str, *, as_of: float, known_at: float,
                        policy: str) -> float:
        """Elapsed minus declared cadence.  A fact, never a severity score."""
        stream = self.streams.streams.get(stream_id)
        cadence = _CADENCE_SECONDS.get(policy)
        if stream is None or cadence is None:
            return 0.0
        observations = [item for item
                        in self.lenses.observations.observations(
                            stream.subject_id, valid_at=as_of, known_at=known_at)
                        if item.stream_id == stream_id]
        if not observations:
            return 0.0
        latest = max(observations, key=lambda item: item.received_at)
        return max(0.0, as_of - latest.received_at - cadence)

    def _unknown_items(self, household_id: str, *, as_of: float,
                       known_at: float) -> list[AttentionItem]:
        """Material unknowns, as determined by the lenses -- never by this model."""
        items: list[AttentionItem] = []
        for subject_id, registration in sorted(self.registry.registrations.items()):
            if registration.household_id != household_id:
                continue
            if not any(stream.household_id == household_id and stream.subject_id == subject_id
                       and self.streams.is_active(stream.id)
                       for stream in self.streams.streams.values()):
                continue
            market = self.lenses.market_value(subject_id, valid_at=as_of, known_at=known_at)
            if market["value"] is not None:
                continue
            class_rank, sub_rank = _ORDER_CLASS["unknown_material"]
            items.append(AttentionItem(
                kind="unknown_material", subject_id=subject_id,
                action=_ACTION["unknown_material"],
                summary="A material input is unknown; value is unavailable.",
                class_rank=class_rank, sub_rank=sub_rank))
        return items

    # -- the fold ----------------------------------------------------------

    def view(self, household_id: str, *, as_of: float,
             known_at: float | None = None) -> OperationsConsoleView:
        """Build the queue.  ``as_of`` is explicit: no wall clock (AC-13)."""
        known_at = as_of if known_at is None else known_at
        collected = (self._proposal_items(household_id)
                     + self._unknown_items(household_id, as_of=as_of, known_at=known_at)
                     + self._freshness_items(household_id, as_of=as_of, known_at=known_at))
        items = tuple(sorted(self._deduplicate(collected), key=lambda item: item.sort_key()))
        unknown_count = sum(1 for item in items if item.kind == "unknown_material")
        if not items:
            terminal = TERMINAL_ALL_NOMINAL
        elif any(item.actionable for item in items):
            terminal = TERMINAL_WORK_PENDING
        else:
            terminal = TERMINAL_ACTIONABLE_COMPLETE
        return OperationsConsoleView(
            items=items, terminal_state=terminal, as_of=as_of,
            model_version=self.version,
            fresh_stream_count=self._fresh_streams(household_id, as_of=as_of,
                                                   known_at=known_at),
            unknown_count=unknown_count,
            retired_stream_count=sum(1 for stream in self.streams.streams.values()
                                     if stream.household_id == household_id
                                     and stream.id in self.streams.retired))

    @staticmethod
    def _deduplicate(items: Iterable[AttentionItem]) -> list[AttentionItem]:
        """Collapse only what aggregation scope duplicates (RFC-012 §3.1, AC-11).

        A subject contributing to both an individual and a household lens
        yields one item, not two.  Identity is per source
        (``attention_identity``), so distinct proposals and distinct streams
        survive: making the queue quieter than the telemetry is the one thing
        the architecture forbids outright.
        """
        seen: dict[tuple[str, ...], AttentionItem] = {}
        for item in items:
            seen.setdefault(item.identity, item)
        return list(seen.values())

    def _fresh_streams(self, household_id: str, *, as_of: float, known_at: float) -> int:
        return sum(1 for stream in self.streams.streams.values()
                   if stream.household_id == household_id
                   and self.streams.is_active(stream.id)
                   and self.lenses.stream_freshness(stream.id, as_of=as_of,
                                                    known_at=known_at) == "available")

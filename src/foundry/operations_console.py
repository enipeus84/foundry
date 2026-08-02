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
_ORDER_CLASS = {
    "identity_ambiguous": (1, 0),
    "proposal_pending": (1, 1),
    "unknown_material": (2, 0),
    "reconciliation_divergence": (3, 0),
    "telemetry_stale": (4, 0),
    "valuation_expiring": (4, 0),
}

#: A material unknown is an active item, but it is not work the operator can
#: discharge -- the value is unavailable, not merely uncaptured.  It therefore
#: does not block "all actionable work completed" while still forbidding
#: "all telemetry nominal" (RFC-012 §4.4).
_NON_ACTIONABLE = frozenset({"unknown_material"})

TERMINAL_ALL_NOMINAL = "all_nominal"
TERMINAL_ACTIONABLE_COMPLETE = "actionable_complete"
TERMINAL_WORK_PENDING = "work_pending"


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
    def stable_id(self) -> str:
        """Final tie-break; deterministic and independent of iteration order."""
        return "|".join((self.kind, self.subject_id, self.stream_id or "",
                         self.proposal_id or ""))

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


@dataclass(frozen=True)
class OperationsConsoleView:
    """The whole rendered surface as data.  The renderer adds no facts."""

    items: tuple[AttentionItem, ...]
    terminal_state: str
    as_of: float
    model_version: str
    fresh_stream_count: int
    unknown_count: int

    @property
    def nominal(self) -> bool:
        return self.terminal_state == TERMINAL_ALL_NOMINAL

    def summary_line(self) -> str:
        """The one sentence the operator reads.  Never claims false quiet."""
        if self.terminal_state == TERMINAL_ALL_NOMINAL:
            return (f"All telemetry nominal - {self.fresh_stream_count} "
                    f"streams fresh as of {self.as_of:.0f}.")
        if self.terminal_state == TERMINAL_ACTIONABLE_COMPLETE:
            plural = "s" if self.unknown_count != 1 else ""
            return (f"All actionable work completed. {self.unknown_count} "
                    f"material value{plural} remain{'' if self.unknown_count != 1 else 's'} "
                    "unavailable.")
        actionable = sum(1 for item in self.items if item.actionable)
        return f"{actionable} item{'s' if actionable != 1 else ''} need attention."

    def as_dict(self) -> dict[str, Any]:
        return {"model_version": self.model_version, "as_of": self.as_of,
                "terminal_state": self.terminal_state, "nominal": self.nominal,
                "summary": self.summary_line(),
                "items": [item.as_dict() for item in self.items]}


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
            envelope = self.envelopes.envelopes.get(proposal.envelope_id)
            received_at = envelope.received_at if envelope else 0.0
            stream = self.streams.streams.get(proposal.stream_id)
            subject_id = stream.subject_id if stream else proposal.stream_id
            blocked = any(resolution.get("outcome") in {"ambiguous", "unresolved"}
                          for resolution in proposal.resolutions)
            kind = "identity_ambiguous" if blocked else "proposal_pending"
            summary = ("Identity unresolved; confirmation is blocked."
                       if blocked else "Proposal awaiting review.")
            class_rank, sub_rank = _ORDER_CLASS[kind]
            items.append(AttentionItem(
                kind=kind, subject_id=subject_id, action=_ACTION[kind], summary=summary,
                stream_id=proposal.stream_id, proposal_id=proposal.id,
                evidence_id=proposal.evidence_id,
                class_rank=class_rank, sub_rank=sub_rank, within_class=received_at))
        return items

    def _freshness_items(self, household_id: str, *, as_of: float,
                         known_at: float) -> list[AttentionItem]:
        items: list[AttentionItem] = []
        for stream in self.streams.streams.values():
            if stream.household_id != household_id:
                continue
            state = self.lenses.stream_freshness(stream.id, as_of=as_of, known_at=known_at)
            if state != "stale":
                continue
            breach = self._breach_seconds(stream.id, as_of=as_of, known_at=known_at,
                                          policy=stream.refresh_policy)
            kind = ("valuation_expiring" if stream.property in {"valuation", "estimate"}
                    else "telemetry_stale")
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

    def _value_items(self, household_id: str, *, as_of: float,
                     known_at: float) -> list[AttentionItem]:
        """Material unknowns and reconciliation divergences, from the lenses."""
        items: list[AttentionItem] = []
        for subject_id, registration in sorted(self.registry.registrations.items()):
            if registration.household_id != household_id:
                continue
            market = self.lenses.market_value(subject_id, valid_at=as_of, known_at=known_at)
            if market["value"] is None:
                class_rank, sub_rank = _ORDER_CLASS["unknown_material"]
                items.append(AttentionItem(
                    kind="unknown_material", subject_id=subject_id,
                    action=_ACTION["unknown_material"],
                    summary="A material input is unknown; value is unavailable.",
                    class_rank=class_rank, sub_rank=sub_rank))
                continue
            if not self.registry.children_of(subject_id):
                continue
            finding = self.lenses.reconciliation(subject_id, valid_at=as_of, known_at=known_at)
            if finding.difference in (None, 0) or not finding.difference:
                continue
            class_rank, sub_rank = _ORDER_CLASS["reconciliation_divergence"]
            items.append(AttentionItem(
                kind="reconciliation_divergence", subject_id=subject_id,
                action=_ACTION["reconciliation_divergence"],
                summary=(f"Holdings fold {finding.derived_total} differs from "
                         f"asserted total {finding.supplied_total}."),
                class_rank=class_rank, sub_rank=sub_rank, within_class=as_of))
        return items

    # -- the fold ----------------------------------------------------------

    def view(self, household_id: str, *, as_of: float,
             known_at: float | None = None) -> OperationsConsoleView:
        """Build the queue.  ``as_of`` is explicit: no wall clock (AC-13)."""
        known_at = as_of if known_at is None else known_at
        collected = (self._proposal_items(household_id)
                     + self._value_items(household_id, as_of=as_of, known_at=known_at)
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
            unknown_count=unknown_count)

    @staticmethod
    def _deduplicate(items: Iterable[AttentionItem]) -> list[AttentionItem]:
        """One canonical subject, one item per kind (RFC-012 §3.1, AC-11).

        Aggregation scope never multiplies operational work: a subject that
        contributes to an individual lens and a household lens yields one
        item, not two.  The stream is part of the key because distinct
        streams on one subject are distinct work -- a stale price and a
        stale unit count are two captures, not one -- and collapsing them
        would hide telemetry rather than deduplicate it.
        """
        seen: dict[tuple[str, str, str], AttentionItem] = {}
        for item in items:
            seen.setdefault((item.kind, item.subject_id, item.stream_id or ""), item)
        return list(seen.values())

    def _fresh_streams(self, household_id: str, *, as_of: float, known_at: float) -> int:
        return sum(1 for stream in self.streams.streams.values()
                   if stream.household_id == household_id
                   and self.lenses.stream_freshness(stream.id, as_of=as_of,
                                                    known_at=known_at) == "available")

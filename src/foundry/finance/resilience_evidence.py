"""Finance-owned manual evidence for Financial Resilience (RFC-008).

The append-only event log remains the source of truth. This narrow envelope
records declarations that the existing Finance entities cannot represent
honestly: income-source cross-checks, dated near-term commitments, and an
essential-outflow cross-check. Protection declarations are reserved for future
work and are deliberately never scored by RFC-008 V1.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from numbers import Real

from foundry.eventlog import EventLog


EVENT_KIND = "finance.resilience_evidence.recorded"

EVIDENCE_FIELDS = frozenset({
    "essential_outflow_monthly",
    "income_source_monthly",
    "near_term_commitment",
    "protection_declaration",
})

_MONEY_FIELDS = frozenset({
    "essential_outflow_monthly",
    "income_source_monthly",
    "near_term_commitment",
})


@dataclass(frozen=True)
class ResilienceEvidence:
    party_id: str
    field: str
    value: str | float
    effective_at: float
    confidence: float
    source: str
    lineage: str
    event_id: str
    unit_or_currency: str | None = None
    due_at: float | None = None
    description: str = ""


@dataclass(frozen=True)
class InvalidResilienceEvidence:
    event_id: str
    party_id: str | None
    effective_at: float | None


def _text(value, field: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) \
            or (not allow_empty and not value.strip()):
        raise ValueError(
            f"{field} must be a string"
            + ("" if allow_empty else " and must not be empty"))
    return value.strip()


def _finite(value, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real) \
            or not math.isfinite(float(value)):
        raise ValueError(f"{field} must be a finite number")
    return float(value)


def _validate_field_value(
    field: str,
    value: str | float,
    unit_or_currency: str | None,
    due_at: float | None,
) -> None:
    if field == "protection_declaration":
        if not isinstance(value, str):
            raise ValueError("protection_declaration must be text")
        if unit_or_currency is not None:
            raise ValueError(
                "protection_declaration cannot carry a currency")
    else:
        if isinstance(value, str):
            raise ValueError(f"{field} must be numeric")
        if value <= 0:
            raise ValueError(f"{field} must be positive")
        if unit_or_currency != "GBP":
            raise ValueError(f"{field} must be denominated in GBP")
    if field == "near_term_commitment":
        if due_at is None:
            raise ValueError("near_term_commitment requires due_at")
    elif due_at is not None:
        raise ValueError(f"{field} cannot carry due_at")


def record_resilience_evidence(
    log: EventLog,
    party_id: str,
    field: str,
    value: str | float,
    effective_at: float,
    *,
    confidence: float,
    source: str,
    lineage: str,
    unit_or_currency: str | None = None,
    due_at: float | None = None,
    description: str = "",
    actor: str = "user",
) -> ResilienceEvidence:
    """Append one attributed declaration after validating its envelope."""
    party_id = _text(party_id, "party_id")
    field = _text(field, "field")
    if field not in EVIDENCE_FIELDS:
        raise ValueError("unsupported resilience evidence field")
    if isinstance(value, str):
        value = _text(value, "value")
    else:
        value = _finite(value, "value")
    effective_at = _finite(effective_at, "effective_at")
    confidence = _finite(confidence, "confidence")
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be between zero and one")
    source = _text(source, "source")
    lineage = _text(lineage, "lineage")
    description = _text(description, "description", allow_empty=True)
    if unit_or_currency is not None:
        unit_or_currency = _text(
            unit_or_currency, "unit_or_currency").upper()
    if due_at is not None:
        due_at = _finite(due_at, "due_at")
    _validate_field_value(field, value, unit_or_currency, due_at)

    event = log.append(EVENT_KIND, {
        "party_id": party_id,
        "field": field,
        "value": value,
        "effective_at": effective_at,
        "confidence": confidence,
        "source": source,
        "lineage": lineage,
        **(
            {"unit_or_currency": unit_or_currency}
            if unit_or_currency is not None else {}
        ),
        **({"due_at": due_at} if due_at is not None else {}),
        **({"description": description} if description else {}),
    }, actor=actor)
    return ResilienceEvidence(
        party_id, field, value, effective_at, confidence, source, lineage,
        event["id"], unit_or_currency, due_at, description)


class ResilienceEvidenceProjection:
    """Tolerant deterministic fold that keeps invalid envelopes visible."""

    def __init__(self, log: EventLog):
        self.log = log
        self.records: dict[str, list[ResilienceEvidence]] = {}
        self.invalid_event_ids: list[str] = []
        self.invalid_records: list[InvalidResilienceEvidence] = []
        self.rebuild()

    def rebuild(self) -> None:
        self.records = {}
        self.invalid_event_ids = []
        self.invalid_records = []
        for event in self.log.events():
            if event.get("kind") == EVENT_KIND:
                self.apply(event)

    def apply(self, event: dict) -> None:
        try:
            payload = event["payload"]
            party_id = _text(payload["party_id"], "party_id")
            field = _text(payload["field"], "field")
            if field not in EVIDENCE_FIELDS:
                raise ValueError("unsupported resilience evidence field")
            value = payload["value"]
            if isinstance(value, str):
                value = _text(value, "value")
            else:
                value = _finite(value, "value")
            effective_at = _finite(payload["effective_at"], "effective_at")
            confidence = _finite(payload["confidence"], "confidence")
            if not 0.0 <= confidence <= 1.0:
                raise ValueError(
                    "confidence must be between zero and one")
            source = _text(payload["source"], "source")
            lineage = _text(payload["lineage"], "lineage")
            unit = payload.get("unit_or_currency")
            if unit is not None:
                unit = _text(unit, "unit_or_currency").upper()
            due_at = payload.get("due_at")
            if due_at is not None:
                due_at = _finite(due_at, "due_at")
            description = _text(
                payload.get("description", ""),
                "description",
                allow_empty=True,
            )
            _validate_field_value(field, value, unit, due_at)
            event_id = _text(event["id"], "event id")
            record = ResilienceEvidence(
                party_id, field, value, effective_at, confidence,
                source, lineage, event_id, unit, due_at, description)
        except (KeyError, TypeError, ValueError):
            event_id = event.get("id")
            event_id = event_id if isinstance(event_id, str) else "unknown"
            payload = event.get("payload")
            party_id = None
            effective_at = None
            if isinstance(payload, dict):
                raw_party_id = payload.get("party_id")
                if isinstance(raw_party_id, str) and raw_party_id.strip():
                    party_id = raw_party_id.strip()
                raw_effective_at = payload.get("effective_at")
                if isinstance(raw_effective_at, Real) \
                        and not isinstance(raw_effective_at, bool) \
                        and math.isfinite(float(raw_effective_at)):
                    effective_at = float(raw_effective_at)
            self.invalid_event_ids.append(event_id)
            self.invalid_records.append(InvalidResilienceEvidence(
                event_id, party_id, effective_at))
            return
        self.records.setdefault(party_id, []).append(record)

    def for_party(
        self,
        party_id: str,
        as_of: float,
        *,
        field: str | None = None,
    ) -> tuple[ResilienceEvidence, ...]:
        return tuple(
            record for record in self.records.get(party_id, ())
            if record.effective_at <= as_of
            and (field is None or record.field == field)
        )

    def future_for(
        self,
        party_id: str,
        as_of: float,
    ) -> tuple[ResilienceEvidence, ...]:
        return tuple(
            record for record in self.records.get(party_id, ())
            if record.effective_at > as_of
        )

    def latest(
        self,
        party_id: str,
        field: str,
        as_of: float,
    ) -> ResilienceEvidence | None:
        matches = self.for_party(party_id, as_of, field=field)
        if not matches:
            return None
        # Equal-effective-date ties follow append order, never random UUID.
        return max(
            enumerate(matches),
            key=lambda item: (item[1].effective_at, item[0]),
        )[1]

    def latest_by_source(
        self,
        party_id: str,
        field: str,
        as_of: float,
    ) -> tuple[ResilienceEvidence, ...]:
        """Return one current declaration per explicit evidence source.

        ``source`` is an envelope field, not inferred display text. Repeated
        declarations from the same source supersede by effective time and
        append order, so correcting one source cannot fabricate plurality.
        """
        latest: dict[str, tuple[int, ResilienceEvidence]] = {}
        for index, record in enumerate(
                self.for_party(party_id, as_of, field=field)):
            previous = latest.get(record.source)
            if previous is None or (
                record.effective_at, index
            ) >= (
                previous[1].effective_at, previous[0]
            ):
                latest[record.source] = (index, record)
        return tuple(
            item[1] for item in sorted(
                latest.values(), key=lambda item: item[0]))

    def has_invalid_for(self, party_id: str, as_of: float) -> bool:
        for record in self.invalid_records:
            # An invalid envelope without an attributable party cannot be
            # assigned to every household. It remains visible in the
            # projection's invalid-record diagnostics but cannot cross scope.
            if record.party_id != party_id:
                continue
            if record.effective_at is not None \
                    and record.effective_at > as_of:
                continue
            return True
        return False

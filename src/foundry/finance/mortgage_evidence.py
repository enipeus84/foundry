"""Finance-owned manual evidence for Mortgage Freedom (RFC-007).

The event log remains the source of truth.  This module records a narrow
manual evidence envelope and folds it back into a read-only projection.
Assessment code consumes the projection; it never contains fixture values.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from numbers import Real
import re

from foundry.eventlog import EventLog


EVENT_KIND = "finance.mortgage_evidence.recorded"
VALUATION_BASES = frozenset({
    "index_estimate",
    "owner_estimate",
    "agent_appraisal",
})
_PURCHASE_MONTH = re.compile(r"^[0-9]{4}-(0[1-9]|1[0-2])$")

EVIDENCE_FIELDS = frozenset({
    "property_role",
    "purchase_price",
    "purchase_date",
    "initial_deposit",
    "acquisition_costs",
    "property_valuation",
    "valuation_basis",
    "lender",
    "original_advance",
    "mortgage_start",
    "balance",
    "repayment_type",
    "interest_type",
    "interest_rate",
    "monthly_payment",
    "payment_day",
    "original_term_months",
    "remaining_term_months",
    "fixed_rate_expiry",
    "recorded_overpayment",
    "reported_ltv",
})

_TEXT_FIELDS = frozenset({
    "property_role", "valuation_basis", "lender", "repayment_type",
    "interest_type",
})
_MONEY_FIELDS = frozenset({
    "purchase_price", "initial_deposit", "acquisition_costs",
    "property_valuation", "original_advance", "balance", "monthly_payment",
    "recorded_overpayment",
})
_POSITIVE_FIELDS = frozenset({
    "purchase_price", "purchase_date", "property_valuation",
    "original_advance", "mortgage_start", "monthly_payment",
    "original_term_months", "fixed_rate_expiry", "recorded_overpayment",
})
_RATIO_FIELDS = frozenset({"interest_rate", "reported_ltv"})


@dataclass(frozen=True)
class MortgageEvidence:
    obligation_id: str
    field: str
    value: str | float
    effective_at: float
    confidence: float
    source: str
    lineage: str
    event_id: str
    unit_or_currency: str | None = None


@dataclass(frozen=True)
class InvalidMortgageEvidence:
    event_id: str
    obligation_id: str | None
    effective_at: float | None


def _text(value, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
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
) -> None:
    if field == "purchase_date":
        if isinstance(value, str):
            if not _PURCHASE_MONTH.fullmatch(value):
                raise ValueError(
                    "purchase_date text must use YYYY-MM month precision")
            return
        if value <= 0:
            raise ValueError("purchase_date must be positive")
        return
    if field in _TEXT_FIELDS:
        if not isinstance(value, str):
            raise ValueError(f"{field} must be text")
        if field == "valuation_basis" and value not in VALUATION_BASES:
            raise ValueError(
                "valuation_basis must be index_estimate, owner_estimate, "
                "or agent_appraisal")
        return
    if isinstance(value, str):
        raise ValueError(f"{field} must be numeric")
    if field in _MONEY_FIELDS and unit_or_currency != "GBP":
        raise ValueError(f"{field} must be denominated in GBP")
    if field in _POSITIVE_FIELDS and value <= 0:
        raise ValueError(f"{field} must be positive")
    if field == "balance" and value < 0:
        raise ValueError("balance must be non-negative")
    if field in {"initial_deposit", "acquisition_costs"} and value < 0:
        raise ValueError(f"{field} must be non-negative")
    if field == "remaining_term_months" and value < 0:
        raise ValueError("remaining_term_months must be non-negative")
    if field == "original_term_months" and not value.is_integer():
        raise ValueError("original_term_months must be a whole number")
    if field in _RATIO_FIELDS and not 0 <= value <= 1:
        raise ValueError(f"{field} must be between zero and one")
    if field == "payment_day" and (
        not value.is_integer() or not 1 <= value <= 31
    ):
        raise ValueError("payment_day must be an integer between 1 and 31")


def record_mortgage_evidence(
    log: EventLog,
    obligation_id: str,
    field: str,
    value: str | float,
    effective_at: float,
    *,
    confidence: float,
    source: str,
    lineage: str,
    unit_or_currency: str | None = None,
    actor: str = "user",
) -> MortgageEvidence:
    """Append one attributed observation after validating the envelope."""
    obligation_id = _text(obligation_id, "obligation_id")
    field = _text(field, "field")
    if field not in EVIDENCE_FIELDS:
        raise ValueError("unsupported mortgage evidence field")
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
    if unit_or_currency is not None:
        unit_or_currency = _text(unit_or_currency, "unit_or_currency")
    _validate_field_value(field, value, unit_or_currency)

    event = log.append(EVENT_KIND, {
        "obligation_id": obligation_id,
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
    }, actor=actor)
    return MortgageEvidence(
        obligation_id, field, value, effective_at, confidence, source,
        lineage, event["id"], unit_or_currency)


class MortgageEvidenceProjection:
    """Tolerant fold whose invalid envelopes remain visible to assessors."""

    def __init__(self, log: EventLog):
        self.log = log
        self.records: dict[str, list[MortgageEvidence]] = {}
        self.invalid_event_ids: list[str] = []
        self.invalid_records: list[InvalidMortgageEvidence] = []
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
            obligation_id = _text(payload["obligation_id"], "obligation_id")
            field = _text(payload["field"], "field")
            if field not in EVIDENCE_FIELDS:
                raise ValueError("unsupported mortgage evidence field")
            value = payload["value"]
            if isinstance(value, str):
                value = _text(value, "value")
            else:
                value = _finite(value, "value")
            effective_at = _finite(payload["effective_at"], "effective_at")
            confidence = _finite(payload["confidence"], "confidence")
            if not 0.0 <= confidence <= 1.0:
                raise ValueError("confidence must be between zero and one")
            source = _text(payload["source"], "source")
            lineage = _text(payload["lineage"], "lineage")
            unit = payload.get("unit_or_currency")
            if unit is not None:
                unit = _text(unit, "unit_or_currency")
            _validate_field_value(field, value, unit)
            event_id = _text(event["id"], "event id")
            record = MortgageEvidence(
                obligation_id, field, value, effective_at, confidence,
                source, lineage, event_id, unit)
        except (KeyError, TypeError, ValueError):
            event_id = event.get("id")
            event_id = event_id if isinstance(event_id, str) else "unknown"
            payload = event.get("payload")
            obligation_id = None
            effective_at = None
            if isinstance(payload, dict):
                raw_obligation_id = payload.get("obligation_id")
                if isinstance(raw_obligation_id, str) \
                        and raw_obligation_id.strip():
                    obligation_id = raw_obligation_id.strip()
                raw_effective_at = payload.get("effective_at")
                if isinstance(raw_effective_at, Real) \
                        and not isinstance(raw_effective_at, bool) \
                        and math.isfinite(float(raw_effective_at)):
                    effective_at = float(raw_effective_at)
            self.invalid_event_ids.append(event_id)
            self.invalid_records.append(InvalidMortgageEvidence(
                event_id, obligation_id, effective_at))
            return
        self.records.setdefault(obligation_id, []).append(record)

    def for_obligation(
        self, obligation_id: str, as_of: float
    ) -> tuple[MortgageEvidence, ...]:
        return tuple(
            record for record in self.records.get(obligation_id, ())
            if record.effective_at <= as_of
        )

    def latest(
        self, obligation_id: str, field: str, as_of: float
    ) -> MortgageEvidence | None:
        matches = tuple(
            record for record in self.for_obligation(obligation_id, as_of)
            if record.field == field
        )
        if not matches:
            return None
        # Event-log order breaks equal-effective-date ties. A random UUID must
        # never decide which observation is current.
        return max(
            enumerate(matches),
            key=lambda item: (item[1].effective_at, item[0]),
        )[1]

    def has_invalid_for(self, obligation_id: str, as_of: float) -> bool:
        """Whether malformed evidence can affect this obligation and time."""
        represented = {record.event_id for record in self.invalid_records}
        if any(event_id not in represented
               for event_id in self.invalid_event_ids):
            return True  # Conservatively handle manually injected corruption.
        for record in self.invalid_records:
            if record.obligation_id is not None \
                    and record.obligation_id != obligation_id:
                continue
            if record.effective_at is not None \
                    and record.effective_at > as_of:
                continue
            return True
        return False

"""Attributed manual pension evidence for RFC-009.

The existing Finance entities carry pension accounts and valuations. This
narrow append-only envelope carries declarations that those entities cannot
represent: contribution rates and payments, scheme fees, DB entitlements and
State Pension forecasts. Rates and entitlements supersede; dated payments
accumulate and are never inferred from annual rates.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from numbers import Real

from foundry.eventlog import EventLog


EVENT_KIND = "finance.pension_evidence.recorded"

ACCOUNT_FIELDS = frozenset({
    "employee_contribution_annual",
    "employer_contribution_annual",
    "salary_sacrifice_annual",
    "contribution_payment_employee",
    "contribution_payment_employer",
    "annual_fee_percent",
    "db_annual_income_accrued",
    "db_normal_pension_age",
})
PARTY_FIELDS = frozenset({
    "state_pension_annual",
    "state_pension_age",
    "state_pension_basis",
})
EVIDENCE_FIELDS = ACCOUNT_FIELDS | PARTY_FIELDS
PAYMENT_FIELDS = frozenset({
    "contribution_payment_employee",
    "contribution_payment_employer",
})
RATE_FIELDS = frozenset({
    "employee_contribution_annual",
    "employer_contribution_annual",
    "salary_sacrifice_annual",
})
MONEY_FIELDS = RATE_FIELDS | PAYMENT_FIELDS | frozenset({
    "db_annual_income_accrued",
    "state_pension_annual",
})
AGE_FIELDS = frozenset({"db_normal_pension_age", "state_pension_age"})
STATE_PENSION_BASES = frozenset({
    "accrued_to_date",
    "forecast_with_continuing_contributions",
})


@dataclass(frozen=True)
class PensionEvidence:
    subject_id: str
    field: str
    value: str | float
    effective_at: float
    confidence: float
    source: str
    lineage: str
    event_id: str
    unit_or_currency: str | None = None


@dataclass(frozen=True)
class InvalidPensionEvidence:
    event_id: str
    subject_id: str | None
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


def _validate_value(
    field: str,
    value: str | float,
    unit_or_currency: str | None,
) -> None:
    if field == "state_pension_basis":
        if value not in STATE_PENSION_BASES:
            raise ValueError("unsupported State Pension basis")
        if unit_or_currency is not None:
            raise ValueError("state_pension_basis cannot carry a unit")
        return
    if isinstance(value, str):
        raise ValueError(f"{field} must be numeric")
    if value < 0:
        raise ValueError(f"{field} must be non-negative")
    if field in MONEY_FIELDS and unit_or_currency != "GBP":
        raise ValueError(f"{field} must be denominated in GBP")
    if field == "annual_fee_percent":
        if unit_or_currency != "fraction" or value > 1:
            raise ValueError(
                "annual_fee_percent must be a fraction between zero and one")
    elif field in AGE_FIELDS:
        if unit_or_currency != "years" or not 0 < value <= 120:
            raise ValueError(f"{field} must be an age in years")


def record_pension_evidence(
    log: EventLog,
    subject_id: str,
    field: str,
    value: str | float,
    effective_at: float,
    *,
    confidence: float,
    source: str,
    lineage: str,
    unit_or_currency: str | None = None,
    actor: str = "user",
) -> PensionEvidence:
    """Validate and append one pension declaration atomically."""
    subject_id = _text(subject_id, "subject_id")
    field = _text(field, "field")
    if field not in EVIDENCE_FIELDS:
        raise ValueError("unsupported pension evidence field")
    if isinstance(value, str):
        value = _text(value, "value")
    else:
        value = _finite(value, "value")
    effective_at = _finite(effective_at, "effective_at")
    confidence = _finite(confidence, "confidence")
    if not 0 <= confidence <= 1:
        raise ValueError("confidence must be between zero and one")
    source = _text(source, "source")
    lineage = _text(lineage, "lineage")
    if unit_or_currency is not None:
        unit_or_currency = _text(
            unit_or_currency, "unit_or_currency")
        if unit_or_currency != "fraction" \
                and unit_or_currency != "years":
            unit_or_currency = unit_or_currency.upper()
    _validate_value(field, value, unit_or_currency)

    event = log.append(EVENT_KIND, {
        "subject_id": subject_id,
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
    return PensionEvidence(
        subject_id,
        field,
        value,
        effective_at,
        confidence,
        source,
        lineage,
        event["id"],
        unit_or_currency,
    )


class PensionEvidenceProjection:
    """Tolerant deterministic replay with invalid envelopes quarantined."""

    def __init__(self, log: EventLog):
        self.log = log
        self.records: dict[str, list[PensionEvidence]] = {}
        self.invalid_event_ids: list[str] = []
        self.invalid_records: list[InvalidPensionEvidence] = []
        self.rebuild()

    @classmethod
    def empty(cls, log: EventLog) -> "PensionEvidenceProjection":
        """Create an empty projection for caller-managed historical replay."""
        projection = cls.__new__(cls)
        projection.log = log
        projection.records = {}
        projection.invalid_event_ids = []
        projection.invalid_records = []
        return projection

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
            subject_id = _text(payload["subject_id"], "subject_id")
            field = _text(payload["field"], "field")
            if field not in EVIDENCE_FIELDS:
                raise ValueError("unsupported pension evidence field")
            value = payload["value"]
            if isinstance(value, str):
                value = _text(value, "value")
            else:
                value = _finite(value, "value")
            effective_at = _finite(payload["effective_at"], "effective_at")
            confidence = _finite(payload["confidence"], "confidence")
            if not 0 <= confidence <= 1:
                raise ValueError("confidence must be between zero and one")
            source = _text(payload["source"], "source")
            lineage = _text(payload["lineage"], "lineage")
            unit = payload.get("unit_or_currency")
            if unit is not None:
                unit = _text(unit, "unit_or_currency")
                if unit not in ("fraction", "years"):
                    unit = unit.upper()
            _validate_value(field, value, unit)
            event_id = _text(event["id"], "event id")
            record = PensionEvidence(
                subject_id,
                field,
                value,
                effective_at,
                confidence,
                source,
                lineage,
                event_id,
                unit,
            )
        except (KeyError, TypeError, ValueError):
            event_id = event.get("id")
            event_id = event_id if isinstance(event_id, str) else "unknown"
            payload = event.get("payload")
            subject_id = None
            effective_at = None
            if isinstance(payload, dict):
                raw_subject = payload.get("subject_id")
                if isinstance(raw_subject, str) and raw_subject.strip():
                    subject_id = raw_subject.strip()
                raw_effective = payload.get("effective_at")
                if isinstance(raw_effective, Real) \
                        and not isinstance(raw_effective, bool) \
                        and math.isfinite(float(raw_effective)):
                    effective_at = float(raw_effective)
            self.invalid_event_ids.append(event_id)
            self.invalid_records.append(InvalidPensionEvidence(
                event_id, subject_id, effective_at))
            return
        self.records.setdefault(subject_id, []).append(record)

    def for_subject(
        self,
        subject_id: str,
        as_of: float,
        *,
        field: str | None = None,
    ) -> tuple[PensionEvidence, ...]:
        return tuple(
            record for record in self.records.get(subject_id, ())
            if record.effective_at <= as_of
            and (field is None or record.field == field)
        )

    def future_for(
        self,
        subject_id: str,
        as_of: float,
    ) -> tuple[PensionEvidence, ...]:
        return tuple(
            record for record in self.records.get(subject_id, ())
            if record.effective_at > as_of
        )

    def latest(
        self,
        subject_id: str,
        field: str,
        as_of: float,
    ) -> PensionEvidence | None:
        matches = self.for_subject(subject_id, as_of, field=field)
        if not matches:
            return None
        return max(
            enumerate(matches),
            key=lambda item: (item[1].effective_at, item[0]),
        )[1]

    def payments(
        self,
        subject_id: str,
        as_of: float,
    ) -> tuple[PensionEvidence, ...]:
        """Return every dated payment; payment declarations never supersede."""
        return tuple(
            record for record in self.for_subject(subject_id, as_of)
            if record.field in PAYMENT_FIELDS
        )

    def has_invalid_for(self, subject_ids, as_of: float) -> bool:
        subject_ids = frozenset(subject_ids)
        return any(
            record.subject_id in subject_ids
            and (
                record.effective_at is None
                or record.effective_at <= as_of
            )
            for record in self.invalid_records
        )

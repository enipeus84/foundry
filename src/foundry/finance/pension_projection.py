"""Immutable provider pension projections, distinct from pension valuations."""

from __future__ import annotations

from dataclasses import dataclass
import math
from numbers import Real

from foundry.eventlog import EventLog


EVENT_KIND = "finance.pension_provider_projection.recorded"


@dataclass(frozen=True)
class PensionProviderProjection:
    account_id: str
    provider: str
    observed_at: float
    retirement_age: float | None
    retirement_at: float | None
    fund_low: float
    fund_medium: float
    fund_high: float
    income_low: float
    income_medium: float
    income_high: float
    growth_low_percent: float
    growth_medium_percent: float
    growth_high_percent: float
    income_basis: str
    source: str
    lineage: str
    event_id: str


def _text(value, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _finite(value, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(float(value)):
        raise ValueError(f"{field} must be a finite number")
    return float(value)


def _money(value, field: str) -> float:
    value = _finite(value, field)
    if value < 0:
        raise ValueError(f"{field} must be non-negative")
    return value


def _scenarios(low, medium, high, field: str, *, money: bool) -> tuple[float, float, float]:
    convert = _money if money else _finite
    values = (convert(low, f"{field}_low"), convert(medium, f"{field}_medium"),
              convert(high, f"{field}_high"))
    if values != tuple(sorted(values)):
        raise ValueError(f"{field} scenarios must be low, medium, high")
    return values


def _from_payload(payload: dict, event_id: str) -> PensionProviderProjection:
    account_id = _text(payload["account_id"], "account_id")
    provider = _text(payload["provider"], "provider")
    observed_at = _finite(payload["observed_at"], "observed_at")
    fund_low, fund_medium, fund_high = _scenarios(
        payload["fund_low"], payload["fund_medium"], payload["fund_high"], "fund", money=True)
    income_low, income_medium, income_high = _scenarios(
        payload["income_low"], payload["income_medium"], payload["income_high"], "income", money=True)
    growth_low_percent, growth_medium_percent, growth_high_percent = _scenarios(
        payload["growth_low_percent"], payload["growth_medium_percent"],
        payload["growth_high_percent"], "growth", money=False)
    retirement_age, retirement_at = payload.get("retirement_age"), payload.get("retirement_at")
    if (retirement_age is None) == (retirement_at is None):
        raise ValueError("provide exactly one retirement age or retirement date")
    if retirement_age is not None:
        retirement_age = _finite(retirement_age, "retirement_age")
        if not 0 < retirement_age <= 120:
            raise ValueError("retirement_age must be between zero and 120")
    if retirement_at is not None:
        retirement_at = _finite(retirement_at, "retirement_at")
    return PensionProviderProjection(
        account_id, provider, observed_at, retirement_age, retirement_at,
        fund_low, fund_medium, fund_high, income_low, income_medium, income_high,
        growth_low_percent, growth_medium_percent, growth_high_percent,
        _text(payload["income_basis"], "income_basis"), _text(payload["source"], "source"),
        _text(payload["lineage"], "lineage"), _text(event_id, "event_id"))


def record_pension_provider_projection(log: EventLog, account_id: str, *, provider: str,
                                       observed_at: float, fund_low: float, fund_medium: float,
                                       fund_high: float, income_low: float, income_medium: float,
                                       income_high: float, growth_low_percent: float,
                                       growth_medium_percent: float, growth_high_percent: float,
                                       income_basis: str, source: str, lineage: str,
                                       retirement_age: float | None = None,
                                       retirement_at: float | None = None,
                                       actor: str = "user") -> PensionProviderProjection:
    """Append one complete provider illustration; no observation is overwritten."""
    payload = {
        "account_id": account_id, "provider": provider, "observed_at": observed_at,
        "fund_low": fund_low, "fund_medium": fund_medium, "fund_high": fund_high,
        "income_low": income_low, "income_medium": income_medium, "income_high": income_high,
        "growth_low_percent": growth_low_percent, "growth_medium_percent": growth_medium_percent,
        "growth_high_percent": growth_high_percent, "income_basis": income_basis,
        "source": source, "lineage": lineage,
    }
    if retirement_age is not None:
        payload["retirement_age"] = retirement_age
    if retirement_at is not None:
        payload["retirement_at"] = retirement_at
    _from_payload(payload, "validated")
    event = log.append(EVENT_KIND, payload, actor=actor)
    return _from_payload(event["payload"], event["id"])


class PensionProviderProjectionProjection:
    """Tolerant read model: malformed observations are quarantined."""

    def __init__(self, log: EventLog):
        self.log = log
        self.records: dict[str, list[PensionProviderProjection]] = {}
        self.invalid_event_ids: list[str] = []
        for event in log.events():
            if event.get("kind") == EVENT_KIND:
                self.apply(event)

    def apply(self, event: dict) -> None:
        try:
            record = _from_payload(event["payload"], event["id"])
        except (KeyError, TypeError, ValueError):
            self.invalid_event_ids.append(str(event.get("id", "unknown")))
            return
        self.records.setdefault(record.account_id, []).append(record)

    def for_account(self, account_id: str, as_of: float) -> tuple[PensionProviderProjection, ...]:
        return tuple(record for record in self.records.get(account_id, ()) if record.observed_at <= as_of)

    def latest(self, account_id: str, as_of: float) -> PensionProviderProjection | None:
        records = self.for_account(account_id, as_of)
        return max(enumerate(records), key=lambda item: (item[1].observed_at, item[0]))[1] if records else None

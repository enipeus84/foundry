"""RFC-013 capture contracts: declarative intent-to-draft adapters.

This module deliberately has no EventLog dependency.  A contract describes
what Operations may collect and produces an inert RFC-011 acquisition fact;
the existing provider, interpreter and confirmation gate remain the only
route to a canonical event.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
import math
import re
from typing import Any, Iterable, Mapping

from foundry.core.acquisition import AcquisitionError


MIN_VALID_AT = 0.0
MAX_VALID_AT = 253_402_300_799.0  # 9999-12-31T23:59:59Z


class EvidencePolicy(str, Enum):
    NONE = "NONE"
    OPTIONAL = "OPTIONAL"
    RECOMMENDED = "RECOMMENDED"
    REQUIRED = "REQUIRED"


@dataclass(frozen=True)
class CaptureField:
    """A renderer-neutral field definition owned by a capture contract."""

    name: str
    label: str
    input_type: str
    required: bool = True
    help_text: str = ""


@dataclass(frozen=True)
class CaptureValidation:
    """Small, explicit validation contract for a money-and-date capture."""

    amount_field: str = "amount"
    currency_field: str = "currency"
    valid_at_field: str = "valid_at"

    def validate(self, values: Mapping[str, str]) -> dict[str, Any]:
        try:
            amount = float(values[self.amount_field])
            valid_at = float(values[self.valid_at_field])
        except (KeyError, TypeError, ValueError) as exc:
            raise AcquisitionError("amount and valid_at must be numeric") from exc
        if not math.isfinite(amount) or amount < 0:
            raise AcquisitionError("amount must be a finite non-negative number")
        if not math.isfinite(valid_at):
            raise AcquisitionError("valid_at must be a finite timestamp")
        if not MIN_VALID_AT <= valid_at <= MAX_VALID_AT:
            raise AcquisitionError("valid_at is outside the supported Unix timestamp range")
        currency = str(values.get(self.currency_field, "")).upper()
        if not re.fullmatch(r"[A-Z]{3}", currency):
            raise AcquisitionError("currency must be a three-letter ISO code")
        return {self.amount_field: amount, self.currency_field: currency,
                self.valid_at_field: valid_at}


@dataclass(frozen=True)
class CanonicalMapper:
    """A declarative mapping from normalised capture data to one RFC-011 fact.

    ``$field`` resolves a normalised capture value; ``$subject_id`` and
    ``$capture_id`` are supplied by Operations.  No mapper can append an
    event, which keeps this layer on the inert side of the confirmation gate.
    """

    event_kind: str
    observation_kind: str
    payload: Mapping[str, str]
    value_field: str = "amount"
    unit_field: str = "currency"

    def map(self, values: Mapping[str, Any], *, subject_id: str,
            capture_id: str) -> dict[str, Any]:
        source = {**values, "subject_id": subject_id, "capture_id": capture_id}

        def resolve(value: str) -> Any:
            if not isinstance(value, str) or not value.startswith("$"):
                return value
            name = value[1:]
            if name not in source:
                raise AcquisitionError(f"canonical mapper references unknown field {name!r}")
            return source[name]

        return {
            "kind": self.observation_kind,
            "subject_id": subject_id,
            "valid_at": values["valid_at"],
            "value": values[self.value_field],
            "unit": values[self.unit_field],
            "canonical_event": {
                "kind": self.event_kind,
                "payload": {key: resolve(value) for key, value in self.payload.items()},
            },
        }


@dataclass(frozen=True)
class CaptureContract:
    """The complete, versioned contract exposed to an Operations renderer."""

    identifier: str
    version: str
    display_name: str
    description: str
    capabilities: tuple[str, ...]
    schema: tuple[CaptureField, ...]
    validation: CaptureValidation
    review_template: str
    evidence_policy: EvidencePolicy
    canonical_mapper: CanonicalMapper
    stream_properties: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9-]*", self.identifier):
            raise ValueError("capture contract identifier must be a lowercase slug")
        if not self.version:
            raise ValueError("capture contract version is required")
        if len({field.name for field in self.schema}) != len(self.schema):
            raise ValueError("capture contract schema contains duplicate fields")
        if not self.stream_properties:
            raise ValueError("capture contract must declare at least one stream property")

    def accepts_stream(self, property_name: str) -> bool:
        return property_name in self.stream_properties

    def normalise(self, values: Mapping[str, str]) -> dict[str, Any]:
        fields = {item.name: item for item in self.schema}
        unknown = set(values) - set(fields)
        if unknown:
            raise AcquisitionError("capture contains unsupported fields")
        missing = [name for name, item in fields.items() if item.required and not values.get(name, "").strip()]
        if missing:
            raise AcquisitionError("capture is missing required fields: " + ", ".join(missing))
        normalised = self.validation.validate(values)
        evidence_reference = values.get("evidence_reference", "").strip()
        if self.evidence_policy is EvidencePolicy.REQUIRED and not evidence_reference:
            raise AcquisitionError("this capture requires an evidence reference")
        if "evidence_reference" in fields:
            normalised["evidence_reference"] = evidence_reference
        return normalised

    def draft(self, values: Mapping[str, str], *, subject_id: str,
              capture_id: str) -> dict[str, Any]:
        return self.canonical_mapper.map(self.normalise(values), subject_id=subject_id,
                                         capture_id=capture_id)

    def capture_id(self, values: Mapping[str, Any], *, stream_id: str,
                   subject_id: str) -> str:
        """Stable identifier for a declared valuation draft.

        The id becomes part of immutable evidence, so it must be derived from
        the same normalised inputs that define capture identity.  Randomness
        here would bypass RFC-011 envelope idempotency.
        """
        identity = {"contract": self.identifier, "version": self.version,
                    "stream_id": stream_id, "subject_id": subject_id,
                    "values": dict(values)}
        encoded = json.dumps(identity, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False).encode("utf-8")
        return f"capture-{self.identifier}-{sha256(encoded).hexdigest()[:24]}"

    def review_summary(self, values: Mapping[str, Any], *, subject_id: str) -> str:
        return self.review_template.format(subject_id=subject_id, **values)


class CaptureContractRegistry:
    """Discoverable registry; Operations depends on this, never contract ids."""

    def __init__(self, contracts: Iterable[CaptureContract] = ()):
        self._contracts: dict[str, CaptureContract] = {}
        for contract in contracts:
            self.register(contract)

    def register(self, contract: CaptureContract) -> CaptureContract:
        if contract.identifier in self._contracts:
            raise ValueError(f"duplicate capture contract {contract.identifier!r}")
        self._contracts[contract.identifier] = contract
        return contract

    def discover(self) -> tuple[CaptureContract, ...]:
        return tuple(sorted(self._contracts.values(), key=lambda item: item.identifier))

    def get(self, identifier: str) -> CaptureContract | None:
        return self._contracts.get(identifier)


_REGISTRY = CaptureContractRegistry()


def register_capture_contract(contract: CaptureContract) -> CaptureContract:
    """Register a contract at import time; no Operations code needs editing."""
    return _REGISTRY.register(contract)


def capture_contract_registry() -> CaptureContractRegistry:
    return _REGISTRY


_MONEY_SCHEMA = (
    CaptureField("amount", "Balance or valuation", "number", help_text="A non-negative amount."),
    CaptureField("currency", "Currency", "text", help_text="Three-letter ISO currency code."),
    CaptureField("valid_at", "As at (Unix timestamp)", "number", help_text="When this value was true."),
    CaptureField("evidence_reference", "Evidence reference", "text", required=False,
                 help_text="Statement, valuation report, or other source reference."),
)


register_capture_contract(CaptureContract(
    identifier="pension-balance-update", version="1", display_name="Pension Balance Update",
    description="Record the stated current value of an existing pension account.",
    capabilities=("manual_capture", "finance_valuation", "review_required"), schema=_MONEY_SCHEMA,
    validation=CaptureValidation(),
    review_template="Review pension balance for {subject_id}: {currency} {amount:,.2f} at {valid_at:.0f}.",
    evidence_policy=EvidencePolicy.RECOMMENDED,
    canonical_mapper=CanonicalMapper("finance.valuation.declared", "pension_balance", {
        "entity_id": "$capture_id", "subject_id": "$subject_id", "amount": "$amount",
        "currency": "$currency", "as_of": "$valid_at",
    }), stream_properties=("pension_balance",),
))

register_capture_contract(CaptureContract(
    identifier="cash-balance-update", version="1", display_name="Cash Balance Update",
    description="Record a stated balance for an existing cash account.",
    capabilities=("manual_capture", "finance_reconciliation", "review_required"), schema=_MONEY_SCHEMA,
    validation=CaptureValidation(),
    review_template="Review cash balance for {subject_id}: {currency} {amount:,.2f} at {valid_at:.0f}.",
    evidence_policy=EvidencePolicy.OPTIONAL,
    canonical_mapper=CanonicalMapper("finance.account.reconciliation_observed", "cash_balance", {
        "entity_id": "$subject_id", "supplied_total": "$amount", "valid_at": "$valid_at",
    }), stream_properties=("cash_balance", "statement_total"),
))

register_capture_contract(CaptureContract(
    identifier="property-valuation-update", version="1", display_name="Property Valuation Update",
    description="Record a point-in-time valuation of an existing property asset.",
    capabilities=("manual_capture", "finance_valuation", "review_required"), schema=_MONEY_SCHEMA,
    validation=CaptureValidation(),
    review_template="Review property valuation for {subject_id}: {currency} {amount:,.2f} at {valid_at:.0f}.",
    evidence_policy=EvidencePolicy.REQUIRED,
    canonical_mapper=CanonicalMapper("finance.valuation.declared", "property_valuation", {
        "entity_id": "$capture_id", "subject_id": "$subject_id", "amount": "$amount",
        "currency": "$currency", "as_of": "$valid_at",
    }), stream_properties=("property_valuation",),
))

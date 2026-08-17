"""The one governed application operation for manual capture proposals."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path
import time
from typing import Any
from zoneinfo import ZoneInfo

from foundry.capture_contracts import CaptureContractRegistry, capture_contract_registry
from foundry.core.acquisition import (
    AcquisitionError, EnvelopeProjection, EvidenceVault, IdentityIndex,
    ManualAcquisitionProvider, ProposalInbox,
    ResolutionService, TelemetryStreamRegistry,
)
from foundry.core.capture_targets import CaptureTargetRegistry
from foundry.core.entities import EntityProjection
from foundry.eventlog import EventLog
from foundry.finance import vocab as finance_vocab
from foundry.finance.acquisition import FinanceManualInterpreter
from foundry.finance.capture_targets import FinanceCaptureTargetResolver, finance_asset_registry
from foundry.finance.entities import FinanceEntityProjection


_LONDON = ZoneInfo("Europe/London")
_RESOURCE_KINDS = {
    "pension": {"contract": "pension-balance-update", "label": "pension account",
                "plural": "pension accounts", "capture": "balance updates",
                "entity": "account", "types": ("pension",)},
    "cash": {"contract": "cash-balance-update", "label": "cash account",
             "plural": "cash accounts", "capture": "cash balance updates",
             "entity": "account", "types": ("checking", "savings")},
    "property": {"contract": "property-valuation-update", "label": "property",
                 "plural": "properties", "capture": "property valuation updates",
                 "entity": "asset", "types": ("property",)},
}


@dataclass(frozen=True)
class ProposalReceipt:
    envelope_id: str
    proposal_id: str


@dataclass(frozen=True)
class CaptureAudit:
    origin: str
    principal: str
    request_id: str


@dataclass(frozen=True)
class AvailabilityDiagnosis:
    state: str
    message: str
    action: str | None = None
    resource_kind: str | None = None


class CaptureService:
    """Creates inert acquisition proposals; confirmation remains elsewhere."""

    def __init__(self, log: EventLog, contracts: CaptureContractRegistry | None = None,
                 household_id: str | None = None):
        self.log = log
        self.contracts = contracts or capture_contract_registry()
        self.household_id = household_id

    def propose(self, contract_id: str, target_id: str, values: dict[str, Any], *,
                actor: str, channel: str, idempotency_key: str | None = None,
                audit: CaptureAudit | None = None) -> ProposalReceipt:
        contract = self.contracts.get(contract_id)
        if contract is None:
            raise LookupError(contract_id)
        household_id = self._household_for_target(contract, target_id)
        targets = CaptureTargetRegistry(
            self.log, FinanceCaptureTargetResolver(FinanceEntityProjection(self.log)))
        target = {item.id: item for item in targets.for_contract(household_id, contract)}.get(target_id)
        if target is None:
            raise LookupError(target_id)
        stream = target.stream
        if channel != stream.channel:
            raise AcquisitionError("capture channel does not match stream declaration")
        capture_values = dict(values)
        if "valid_at" in capture_values:
            capture_values["valid_at"] = str(_london_timestamp(capture_values["valid_at"]))
        normalised = contract.normalise(capture_values)
        capture_id = contract.capture_id(normalised, stream_id=stream.id, subject_id=stream.subject_id)
        fact = contract.canonical_mapper.map(normalised, subject_id=stream.subject_id, capture_id=capture_id)
        external_ref = idempotency_key or normalised.get("evidence_reference") or None
        payload = {"capture_contract": {"identifier": contract.identifier, "version": contract.version},
                   "review_summary": contract.review_summary(normalised, subject_id=stream.subject_id)}
        if audit is not None:
            payload["capture_audit"] = {"origin": audit.origin, "principal": audit.principal,
                                        "request_id": audit.request_id}
        return self.propose_fact(
            household_id, stream.id, fact, actor=actor, channel=channel,
            external_ref=external_ref,
            payload=payload,
        )

    def propose_fact(self, household_id: str, target_id: str, fact: dict[str, Any], *, actor: str,
                     channel: str, external_ref: str | None = None,
                     payload: dict[str, Any] | None = None) -> ProposalReceipt:
        """Compatibility entry for pre-contract Operations forms, still proposal-only."""
        streams = TelemetryStreamRegistry(self.log)
        stream = {item.id: item for item in streams.active_manual_streams(household_id)}.get(target_id)
        if stream is None:
            raise LookupError(target_id)
        if channel != stream.channel:
            raise AcquisitionError("capture channel does not match stream declaration")
        vault = EvidenceVault(_vault_root(), authorized=lambda permitted: permitted == actor)
        provider = ManualAcquisitionProvider(self.log, streams, vault, [stream.id])
        evidence = dict(payload or {})
        evidence["observations"] = [fact]
        envelope = provider.capture(
            stream.id, evidence, received_at=time.time(), actor=actor,
            source_identity=stream.source_identity, external_ref=external_ref)
        inbox = ProposalInbox(self.log)
        interpreter = FinanceManualInterpreter(
            vault, EnvelopeProjection(self.log), streams,
            ResolutionService(IdentityIndex(self.log), finance_asset_registry(self.log), inbox))
        proposal = interpreter.interpret(envelope.id, actor)
        return ProposalReceipt(envelope.id, proposal.id)

    def availability(self, household_id: str, contract_id: str, *,
                     bootstrap_diagnostics: tuple[object, ...] = ()) -> AvailabilityDiagnosis | None:
        kind = next((name for name, spec in _RESOURCE_KINDS.items()
                     if spec["contract"] == contract_id), None)
        if kind is None:
            return None
        spec = _RESOURCE_KINDS[kind]
        projection = FinanceEntityProjection(self.log)
        entities = (projection.accounts.values() if spec["entity"] == "account"
                    else projection.assets.values())
        matching = [entity for entity in entities if entity.status == "active" and
                    getattr(entity, "account_type" if spec["entity"] == "account" else "asset_category") in spec["types"]]
        if not matching:
            return AvailabilityDiagnosis(
                "no_resource_registered",
                f"No {spec['plural']} are currently registered for {spec['capture']}.",
                f"Register {spec['label']}", kind)
        members = EntityProjection(self.log).members_of(household_id)
        member_ids = {member.id for member in members if member.status == "active"}
        owned = [entity for entity in matching if any(
            link.target in member_ids and link.relation in finance_vocab.VALUE_OWNERSHIP_RELATIONS
            for link in entity.ownership)]
        if not owned:
            return AvailabilityDiagnosis(
                "no_active_owner_link",
                f"A {spec['label']} is registered, but it is not linked to an active household member.",
                "Review ownership")
        contract = self.contracts.get(contract_id)
        targets = CaptureTargetRegistry(
            self.log, FinanceCaptureTargetResolver(FinanceEntityProjection(self.log)))
        if contract is not None and targets.for_contract(household_id, contract):
            return AvailabilityDiagnosis("available", "Capture is available.")
        if bootstrap_diagnostics:
            return AvailabilityDiagnosis(
                "bootstrap_diagnostic",
                "Foundry could not prepare this capture from registered economic facts.",
                "Review capture setup")
        if kind == "property":
            return AvailabilityDiagnosis(
                "unavailable",
                "A property is registered, but Foundry has not established it as the household's primary residence.",
                "Review property and mortgage facts")
        return AvailabilityDiagnosis(
            "unavailable",
            "Foundry could not prepare this capture from registered economic facts.",
            "Review capture setup")

    def _household_for_target(self, contract, target_id: str) -> str:
        targets = CaptureTargetRegistry(
            self.log, FinanceCaptureTargetResolver(FinanceEntityProjection(self.log)))
        for household in EntityProjection(self.log).parties.values():
            if household.party_type != "household" or household.status != "active":
                continue
            if self.household_id is not None and household.id != self.household_id:
                continue
            if any(item.id == target_id for item in targets.for_contract(household.id, contract)):
                return household.id
        raise LookupError(target_id)


def _vault_root() -> str:
    root = os.environ.get("FOUNDRY_EVIDENCE_VAULT_PATH")
    return root or str(Path(os.environ.get("FOUNDRY_DATA_PATH", "foundry_data/events.jsonl")).with_suffix(".vault"))


def _london_timestamp(value: Any) -> float:
    if isinstance(value, str) and "T" in value:
        return datetime.fromisoformat(value).replace(tzinfo=_LONDON).timestamp()
    return float(value)

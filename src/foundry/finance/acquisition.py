"""Finance's RFC-011 adapter for the domain-neutral acquisition seam."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from foundry.core import vocab
from foundry.core.acquisition import (
    AcquisitionError,
    DomainDraftContract,
    EnvelopeProjection,
    EvidenceVault,
    ManualInterpreter,
    ResolutionService,
    TelemetryStreamRegistry,
)
from foundry.eventlog import EventLog


class FinanceManualDraftContract:
    """The bounded Finance vocabulary accepted from the manual interpreter.

    This belongs to Finance because Core must not know canonical Finance event
    names or their payloads.  Both interpretation and confirmation use the
    same contract so an inert proposal cannot widen the accepted surface.
    """

    interpreter_id = "manual-json"
    interpreter_version = "1"
    interpreter_class = "deterministic"

    _EVENTS = frozenset({
        "finance.account.declared",
        "finance.position.declared",
        "finance.position.updated",
        "finance.transaction.declared",
        "finance.account.reconciliation_observed",
        "finance.accessibility_profile.declared",
        "finance.accessibility_condition.declared",
        "finance.accessibility_condition.updated",
    })

    def validate_interpretation(self, draft: dict[str, Any]) -> None:
        if draft.get("kind") not in self._EVENTS or not isinstance(draft.get("payload"), dict):
            raise AcquisitionError("draft event is not in the approved Finance manual contract")

    def validate_confirmation(self, draft: dict[str, Any], observation: dict[str, Any]) -> None:
        self.validate_interpretation(draft)
        payload = draft["payload"]
        kind = draft["kind"]
        entity_id = payload.get("entity_id")
        if not isinstance(entity_id, str):
            raise AcquisitionError("Finance draft requires an entity id")
        if kind == "finance.account.declared":
            if not {"account_type", "currency"} <= set(payload):
                raise AcquisitionError("account draft is incomplete")
        elif kind == "finance.position.declared":
            required = {"account_id", "instrument", "quantity", "unit_price", "currency",
                        "cost_basis", "valuation_date", "market_value", "asset_category"}
            if not required <= set(payload):
                raise AcquisitionError("position draft is incomplete")
        elif kind == "finance.position.updated":
            if not ({"quantity", "unit_price", "valuation_date"} & set(payload)):
                raise AcquisitionError("position update has no observed field")
        elif kind == "finance.transaction.declared":
            if not {"account_id", "amount", "currency", "transaction_category", "ts"} <= set(payload):
                raise AcquisitionError("transaction draft is incomplete")
        elif kind == "finance.account.reconciliation_observed":
            if "supplied_total" not in payload:
                raise AcquisitionError("reconciliation draft is incomplete")
        elif kind == "finance.accessibility_profile.declared":
            if "components" not in payload:
                raise AcquisitionError("accessibility profile draft is incomplete")
        elif kind == "finance.accessibility_condition.declared":
            if payload.get("state", "pending") not in {"pending", "satisfied", "lapsed", "revoked"}:
                raise AcquisitionError("invalid accessibility condition state")
        elif kind == "finance.accessibility_condition.updated":
            if payload.get("state") not in {"satisfied", "lapsed", "revoked"}:
                raise AcquisitionError("accessibility conditions only move from pending to a terminal state")


FINANCE_MANUAL_DRAFT_CONTRACT: DomainDraftContract = FinanceManualDraftContract()


class FinanceManualInterpreter(ManualInterpreter):
    """Convenience adapter binding the generic interpreter to Finance."""

    def __init__(self, vault: EvidenceVault, envelopes: EnvelopeProjection,
                 streams: TelemetryStreamRegistry, resolver: ResolutionService):
        super().__init__(vault, envelopes, streams, resolver, FINANCE_MANUAL_DRAFT_CONTRACT)


@dataclass(frozen=True)
class AccessibilityCondition:
    id: str
    condition: str
    state: str
    subject_id: str
    provenance: tuple[str, ...]


class FinanceAccessibilityProjection:
    """Finance's use of Core's accessibility lifecycle contract."""

    def __init__(self, log: EventLog):
        self.log = log
        self.profiles: dict[str, dict[str, Any]] = {}
        self.conditions: dict[str, AccessibilityCondition] = {}
        self.rebuild()

    def rebuild(self) -> None:
        self.profiles, self.conditions = {}, {}
        for event in self.log.events():
            payload = event["payload"]
            if not isinstance(payload.get("provenance"), dict):
                continue
            if event["kind"] == "finance.accessibility_profile.declared":
                subject_id, components = payload.get("entity_id"), payload.get("components")
                if isinstance(subject_id, str) and isinstance(components, list):
                    self.profiles[subject_id] = {
                        "components": tuple(dict(item) for item in components if isinstance(item, dict))}
            elif event["kind"] == "finance.accessibility_condition.declared":
                condition_id, condition, subject_id = (payload.get("entity_id"), payload.get("condition"),
                                                        payload.get("subject_id"))
                state = payload.get("state", "pending")
                if (isinstance(condition_id, str) and isinstance(subject_id, str) and
                        condition in vocab.ACCESSIBILITY_CONDITION and
                        state in {"pending", "satisfied", "lapsed", "revoked"}):
                    self.conditions[condition_id] = AccessibilityCondition(
                        condition_id, condition, state, subject_id, (event["id"],))
            elif event["kind"] == "finance.accessibility_condition.updated":
                current = self.conditions.get(payload.get("entity_id"))
                state = payload.get("state")
                if (current is not None and state in {"satisfied", "lapsed", "revoked"} and
                        current.state == "pending"):
                    self.conditions[current.id] = AccessibilityCondition(
                        current.id, current.condition, state, current.subject_id,
                        current.provenance + (event["id"],))

    def profile_for(self, subject_id: str) -> dict[str, Any]:
        return self.profiles.get(subject_id, {"components": ()})

    def condition_states(self) -> dict[str, dict[str, str]]:
        return {condition_id: {"state": condition.state}
                for condition_id, condition in self.conditions.items()}

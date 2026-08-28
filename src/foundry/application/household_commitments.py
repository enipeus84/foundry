"""Governed household commitment commands and the denominator read.

The service is deliberately an application boundary.  It may read Mortgage
Freedom evidence while promoting it, but Financial Resilience only ever reads
the resulting Finance RecurringSeries.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any

from foundry.core.entities import EntityProjection
from foundry.core.principal_authority import PrincipalHouseholdAuthority
from foundry.core.scope import Subject
from foundry.eventlog import EventLog
from foundry.finance.entities import (
    FinanceEntityProjection, declare_recurring_series,
    validate_recurring_commitment,
)
from foundry.finance.metrics import FinanceMetricProvider
from foundry.finance.mortgage_evidence import MortgageEvidenceProjection
from foundry.finance import vocab


class HouseholdCommitmentDenied(PermissionError):
    """The requested commitment operation cannot safely be executed."""


def _digest(value: dict[str, Any]) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class HouseholdCommitmentService:
    log: EventLog
    principal: str
    household_id: str
    client: str = "mcp"
    witness_model: str = ""

    def _authorised(self) -> None:
        if not PrincipalHouseholdAuthority(self.log).permits_write(
                self.principal, self.household_id):
            raise HouseholdCommitmentDenied(
                "principal is not authorised to mutate this household")

    def _validate_request(self, values: dict[str, Any]) -> dict[str, Any]:
        """Validate without invoking a write helper.

        ``declare_recurring_series`` owns final validation at execution.  This
        gate checks the required envelope and resource references so proposals
        are inert and idempotent.
        """
        self._authorised()
        required = {"recurring_commitment_type", "amount", "currency", "cadence",
                    "direction", "essential_category", "basis", "effective_from",
                    "source_reference"}
        missing = sorted(key for key in required if key not in values)
        if missing:
            raise HouseholdCommitmentDenied(
                "commitment declaration is incomplete: " + ", ".join(missing))
        if values["recurring_commitment_type"] not in vocab.RECURRING_COMMITMENT_TYPE:
            raise HouseholdCommitmentDenied("unsupported recurring commitment type")
        try:
            validate_recurring_commitment(
                values["amount"], values["currency"], values["cadence"],
                values["direction"], values["essential_category"], values["basis"],
                values["effective_from"], values["source_reference"],
                values.get("derivation_reference"))
        except (TypeError, ValueError) as exc:
            raise HouseholdCommitmentDenied(str(exc)) from exc
        finance = FinanceEntityProjection(self.log)
        core = EntityProjection(self.log)
        member_ids = {person.id for person in core.members_of(self.household_id)}
        account_id = values.get("funding_account_id")
        obligation_id = values.get("settled_obligation_id")
        if values["basis"] != "not_applicable" and not (account_id or obligation_id):
            raise HouseholdCommitmentDenied(
                "a counted commitment requires a funding account or settled obligation")
        if account_id is not None and account_id not in finance.accounts:
            raise HouseholdCommitmentDenied("funding account is unavailable")
        if obligation_id is not None and obligation_id not in finance.obligations:
            raise HouseholdCommitmentDenied("settled obligation is unavailable")
        if account_id is not None and not any(
                link.target in member_ids
                for link in finance.accounts[account_id].ownership):
            raise HouseholdCommitmentDenied(
                "funding account is not owned by this household")
        if obligation_id is not None and not any(
                link.relation == "owes" and link.target in member_ids
                for link in finance.obligations[obligation_id].ownership):
            raise HouseholdCommitmentDenied(
                "settled obligation is not owed by this household")
        return dict(values)

    def propose(self, **values: Any) -> dict[str, Any]:
        request = self._validate_request(dict(values))
        digest = _digest(request)
        proposal_id = f"household-commitment-{digest[:24]}"
        for event in self.log.events():
            if event["kind"] == "application.household_commitment.proposed" \
                    and event["payload"].get("proposal_id") == proposal_id:
                return {"proposal_id": proposal_id, "state": "proposed"}
        self.log.append("application.household_commitment.proposed", {
            "proposal_id": proposal_id, "request_digest": digest,
            "household_id": self.household_id, "request": request,
            "principal": self.principal, "client": self.client,
            "witness_model": self.witness_model,
        }, actor=f"mcp:{self.principal}")
        return {"proposal_id": proposal_id, "state": "proposed"}

    def execute(self, *, proposal_id: str, command_id: str, **values: Any) -> dict[str, Any]:
        if not isinstance(command_id, str) or not command_id.strip():
            raise HouseholdCommitmentDenied("command_id is required for idempotent execution")
        request = self._validate_request(dict(values))
        digest = _digest(request)
        for event in self.log.events():
            if event["kind"] == "application.household_commitment.executed":
                payload = event["payload"]
                if payload.get("household_id") == self.household_id \
                        and payload.get("command_id") == command_id:
                    if payload.get("request_digest") != digest:
                        raise HouseholdCommitmentDenied(
                            "command id was already used for a different commitment")
                    return dict(payload["result"])
        proposal = next((event["payload"] for event in self.log.events()
                         if event["kind"] == "application.household_commitment.proposed"
                         and event["payload"].get("proposal_id") == proposal_id), None)
        if proposal is None or proposal.get("household_id") != self.household_id \
                or proposal.get("request_digest") != digest:
            raise HouseholdCommitmentDenied("proposal does not match the commitment")
        series = declare_recurring_series(
            self.log, actor=f"mcp:{self.principal}", **request)
        result = _series_result(series)
        self.log.append("application.household_commitment.executed", {
            "proposal_id": proposal_id, "command_id": command_id,
            "request_digest": digest, "household_id": self.household_id,
            "result": result, "principal": self.principal, "client": self.client,
            "witness_model": self.witness_model,
        }, actor=f"mcp:{self.principal}")
        return result

    def propose_mortgage_promotion(self, obligation_id: str, as_of: float) -> dict[str, Any]:
        self._authorised()
        request = self._mortgage_request(obligation_id, as_of)
        digest = _digest(request)
        proposal_id = f"mortgage-payment-promotion-{digest[:24]}"
        for event in self.log.events():
            if event["kind"] == "application.mortgage_payment_promotion.proposed" \
                    and event["payload"].get("proposal_id") == proposal_id:
                return {"proposal_id": proposal_id, "state": "proposed",
                        "source_evidence_id": request["source_evidence_id"]}
        self.log.append("application.mortgage_payment_promotion.proposed", {
            "proposal_id": proposal_id, "request_digest": digest,
            "household_id": self.household_id, "request": request,
            "principal": self.principal, "client": self.client,
            "witness_model": self.witness_model,
        }, actor=f"mcp:{self.principal}")
        return {"proposal_id": proposal_id, "state": "proposed",
                "source_evidence_id": request["source_evidence_id"]}

    def execute_mortgage_promotion(self, *, obligation_id: str, as_of: float,
                                   proposal_id: str, command_id: str) -> dict[str, Any]:
        if not isinstance(command_id, str) or not command_id.strip():
            raise HouseholdCommitmentDenied("command_id is required for idempotent execution")
        self._authorised()
        request = self._mortgage_request(obligation_id, as_of)
        digest = _digest(request)
        proposal = next((event["payload"] for event in self.log.events()
                         if event["kind"] == "application.mortgage_payment_promotion.proposed"
                         and event["payload"].get("proposal_id") == proposal_id), None)
        if proposal is None or proposal.get("household_id") != self.household_id \
                or proposal.get("request_digest") != digest:
            raise HouseholdCommitmentDenied(
                "mortgage-payment promotion is stale or does not match authoritative evidence")
        for event in self.log.events():
            if event["kind"] == "application.mortgage_payment_promotion.executed":
                payload = event["payload"]
                if payload.get("household_id") == self.household_id \
                        and payload.get("command_id") == command_id:
                    if payload.get("request_digest") != digest:
                        raise HouseholdCommitmentDenied(
                            "command id was already used for a different mortgage promotion")
                    return dict(payload["result"])
        finance = FinanceEntityProjection(self.log)
        existing = next((series for series in finance.recurring_series.values()
                         if series.derivation_reference == request["source_evidence_id"]), None)
        if existing is None:
            existing = declare_recurring_series(
                self.log, "mortgage_payment", request["amount"], request["currency"],
                actor=f"mcp:{self.principal}", cadence="month", direction="outflow",
                essential_category="housing", basis="contractual_derived",
                effective_from=request["effective_from"],
                source_reference=request["source_evidence_id"],
                derivation_reference=request["source_evidence_id"],
                settled_obligation_id=obligation_id,
                description="Promoted from canonical mortgage payment evidence")
        result = _series_result(existing)
        self.log.append("application.mortgage_payment_promotion.executed", {
            "proposal_id": proposal_id, "command_id": command_id,
            "request_digest": digest, "household_id": self.household_id,
            "result": result, "principal": self.principal, "client": self.client,
            "witness_model": self.witness_model,
        }, actor=f"mcp:{self.principal}")
        return result

    def _mortgage_request(self, obligation_id: str, as_of: float) -> dict[str, Any]:
        finance = FinanceEntityProjection(self.log)
        obligation = finance.obligations.get(obligation_id)
        if obligation is None or obligation.liability_category != "mortgage":
            raise HouseholdCommitmentDenied("mortgage obligation is unavailable")
        core = EntityProjection(self.log)
        member_ids = {person.id for person in core.members_of(self.household_id)}
        if not any(link.relation == "owes" and link.target in member_ids
                   for link in obligation.ownership):
            raise HouseholdCommitmentDenied(
                "mortgage obligation is not owed by this household")
        evidence = MortgageEvidenceProjection(self.log)
        if evidence.has_invalid_for(obligation_id, as_of):
            raise HouseholdCommitmentDenied("mortgage payment evidence is malformed")
        payment = evidence.latest(obligation_id, "monthly_payment", as_of)
        if payment is None or not isinstance(payment.value, float) \
                or payment.value <= 0 or payment.unit_or_currency is None:
            raise HouseholdCommitmentDenied("authoritative monthly mortgage payment evidence is unavailable")
        return {"obligation_id": obligation_id, "as_of": as_of,
                "amount": payment.value, "currency": payment.unit_or_currency,
                "effective_from": payment.effective_at,
                "source_evidence_id": payment.event_id}


def _series_result(series) -> dict[str, Any]:
    return {
        "series_id": series.id, "amount": series.amount, "currency": series.currency,
        "cadence": series.cadence, "direction": series.direction,
        "category": series.essential_category, "basis": series.basis,
        "effective_from": series.effective_from,
        "provenance": list(series.provenance),
        "reference": series.source_reference,
        "derivation": series.derivation_reference,
    }


@dataclass(frozen=True)
class EssentialOutflowQueryService:
    """Read-only operator view of denominator coverage and evidence needs."""

    log: EventLog
    household_id: str

    def inspect(self, as_of: float) -> dict[str, Any]:
        core = EntityProjection(self.log)
        finance = FinanceEntityProjection(self.log)
        provider = FinanceMetricProvider(finance, core)
        scope = Subject("party", self.household_id)
        people = provider._scope_persons(scope)
        if people is None or not people:
            raise LookupError("household scope is unavailable")
        currency = provider._target_currency(set(people) | {self.household_id})
        basis = provider.essential_outflow_basis(
            set(people), provider._attribute_to(scope), currency, as_of)
        categories = [{
            "category": item.category, "amount": item.amount, "basis": item.basis,
            "effective_date": item.effective_from,
            "provenance": list(item.provenance),
            "contractual": item.contractual, "observed": item.observed,
            "estimated": item.estimated,
        } for item in basis.categories]
        total = basis.monthly_amount or 0.0
        return {
            "as_of": as_of, "currency": currency,
            "available": basis.monthly_amount is not None,
            "monthly_amount": basis.monthly_amount,
            "categories": categories,
            "uncovered_categories": list(basis.uncovered_categories),
            "shares": {
                "contractual": sum(item.contractual for item in basis.categories) / total if total else 0.0,
                "observed": sum(item.observed for item in basis.categories) / total if total else 0.0,
                "estimated": sum(item.estimated for item in basis.categories) / total if total else 0.0,
            },
            "evidence_to_commission": [
                f"declare a contractual commitment, operator estimate, observed expenditure, or not_applicable basis for {category}"
                for category in basis.uncovered_categories],
            "limitations": list(basis.limitations),
        }

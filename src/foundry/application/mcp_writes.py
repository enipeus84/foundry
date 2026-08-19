"""One governed MCP command; it remains on the proposal side of confirmation."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any

from foundry.application.capture import CaptureAudit, CaptureService, ProposalReceipt
from foundry.capture_contracts import CaptureValidationError
from foundry.core.acquisition import AcquisitionError
from foundry.application.resources import (
    FinancialResourceCommandService, FinancialResourceQuery, ResourceCommandDenied, ResourceNotFound,
)
from foundry.core.principal_authority import PrincipalHouseholdAuthority
from foundry.eventlog import EventLog


class McpWriteDenied(PermissionError):
    """MCP writes fail closed when authority or an eligible command is absent."""


class McpClientSafeDenied(McpWriteDenied):
    """An explicitly reviewed, bounded refusal that MCP may disclose."""


@dataclass(frozen=True)
class ResourceProposalReceipt:
    proposal_id: str
    operation: str


@dataclass(frozen=True)
class FinancialObservationProposalReceipt:
    """The MCP-facing receipt for an inert, reviewable capture proposal."""

    proposal_id: str
    envelope_id: str
    contract_id: str
    contract_version: str
    resource_id: str
    review_summary: str
    command_id: str


def _proposal_digest(values: dict[str, Any]) -> str:
    return sha256(json.dumps(values, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class McpFinancialResourceWrites:
    log: EventLog
    principal: str
    household_id: str
    client: str
    witness_model: str

    def _propose(self, operation: str, values: dict[str, Any]) -> ResourceProposalReceipt:
        digest = _proposal_digest(values)
        proposal_id = f"resource-proposal-{digest[:24]}"
        for event in self.log.events():
            if (event["kind"] == "application.mcp_resource.proposed"
                    and event["payload"].get("proposal_id") == proposal_id):
                return ResourceProposalReceipt(proposal_id, operation)
        self.log.append("application.mcp_resource.proposed", {
            "proposal_id": proposal_id, "operation": operation,
            "request_digest": digest, "household_id": self.household_id,
            "request": values,
        }, actor=f"mcp:{self.principal}")
        return ResourceProposalReceipt(proposal_id, operation)

    def _proposal(self, proposal_id: str, operation: str, values: dict[str, Any]) -> None:
        if not proposal_id:
            raise McpWriteDenied("a valid prior proposal is required")
        digest = _proposal_digest(values)
        for event in self.log.events():
            payload = event["payload"]
            if (event["kind"] == "application.mcp_resource.proposed"
                    and payload.get("proposal_id") == proposal_id):
                if (payload.get("household_id") != self.household_id
                        or payload.get("operation") != operation
                        or payload.get("request_digest") != digest):
                    raise McpWriteDenied("proposal does not match the requested operation")
                return
        raise McpWriteDenied("a valid prior proposal is required")

    def propose_create(self, *, resource_type: str, currency: str, name: str | None = None,
                       provider: str | None = None, owner: str | None = None,
                       owners: list[str] | None = None,
                       liquidity_classification: str | None = None) -> ResourceProposalReceipt:
        return self._propose("create_financial_resource", {
            "household_id": self.household_id, "resource_type": resource_type,
            "currency": currency, "name": name, "provider": provider,
            "owner": owner, "owners": owners,
            "liquidity_classification": liquidity_classification,
        })

    def create(self, *, resource_type: str, currency: str, name: str | None = None,
               provider: str | None = None, owner: str | None = None,
               owners: list[str] | None = None, liquidity_classification: str | None = None,
               command_id: str, proposal_id: str | None = None) -> dict[str, Any]:
        if not command_id.strip():
            raise McpWriteDenied("command_id is required for idempotent execution")
        values = {"household_id": self.household_id, "resource_type": resource_type,
                  "currency": currency, "name": name, "provider": provider,
                  "owner": owner, "owners": owners,
                  "liquidity_classification": liquidity_classification}
        self._proposal(proposal_id or "", "create_financial_resource", values)
        try:
            return FinancialResourceCommandService(self.log).create_financial_resource(
                household_id=self.household_id, resource_type=resource_type, currency=currency,
                name=name, provider=provider, owner=owner, owners=owners,
                liquidity_classification=liquidity_classification,
                actor=f"mcp:{self.principal}", principal=self.principal, command_id=command_id,
                client=self.client, witness_model=self.witness_model)
        except ResourceCommandDenied as exc:
            raise McpWriteDenied(str(exc)) from exc

    def propose_update(self, *, resource_id: str, name: str,
                       reason: str = "metadata update") -> ResourceProposalReceipt:
        return self._propose("update_financial_resource", {
            "household_id": self.household_id, "resource_id": resource_id,
            "name": name, "reason": reason,
        })

    def update(self, *, resource_id: str, name: str, command_id: str,
               reason: str = "metadata update", proposal_id: str | None = None) -> dict[str, Any]:
        self._proposal(proposal_id or "", "update_financial_resource", {
            "household_id": self.household_id, "resource_id": resource_id,
            "name": name, "reason": reason,
        })
        try:
            return FinancialResourceCommandService(self.log).update_financial_resource(
                household_id=self.household_id, resource_id=resource_id, name=name,
                reason=reason, actor=f"mcp:{self.principal}", principal=self.principal,
                command_id=command_id, client=self.client, witness_model=self.witness_model)
        except (ResourceCommandDenied, ResourceNotFound) as exc:
            raise McpWriteDenied(str(exc)) from exc

    def propose_close(self, *, resource_id: str, reason: str = "closed") -> ResourceProposalReceipt:
        return self._propose("close_financial_resource", {
            "household_id": self.household_id, "resource_id": resource_id,
            "reason": reason,
        })

    def close(self, *, resource_id: str, command_id: str, reason: str = "closed",
              proposal_id: str | None = None) -> dict[str, Any]:
        self._proposal(proposal_id or "", "close_financial_resource", {
            "household_id": self.household_id, "resource_id": resource_id,
            "reason": reason,
        })
        try:
            return FinancialResourceCommandService(self.log).close_financial_resource(
                household_id=self.household_id, resource_id=resource_id, reason=reason,
                actor=f"mcp:{self.principal}", principal=self.principal,
                command_id=command_id, client=self.client, witness_model=self.witness_model)
        except (ResourceCommandDenied, ResourceNotFound) as exc:
            raise McpWriteDenied(str(exc)) from exc


@dataclass(frozen=True)
class McpBalanceCapture:
    log: EventLog
    principal: str
    household_id: str
    client: str
    witness_model: str

    def propose_financial_observation(
            self, *, resource_id: str, capture_contract_id: str, amount: float,
            currency: str, as_at: str, command_id: str,
            evidence_reference: str | None = None,
            valuation_basis: str | None = None, source: str | None = None,
    ) -> FinancialObservationProposalReceipt:
        """Validate and stage one existing contract for human confirmation.

        This is deliberately the only MCP financial-observation write path.
        Confirmation remains with the canonical acquisition confirmation gate.
        """
        if not isinstance(command_id, str) or not command_id.strip():
            raise McpClientSafeDenied("command_id is required for idempotent capture")
        if not PrincipalHouseholdAuthority(self.log).permits_write(self.principal, self.household_id):
            raise McpClientSafeDenied("principal is not authorised to mutate this household")

        query = FinancialResourceQuery(self.log, self.household_id)
        try:
            resource = query.get_financial_resource(resource_id)
            availability = query.capture_availability(resource_id)
        except ResourceNotFound as exc:
            raise McpClientSafeDenied("financial resource is unavailable") from exc
        operation = next((item for item in availability["supported_capture_operations"]
                          if item["contract_id"] == capture_contract_id), None)
        if operation is None:
            raise McpClientSafeDenied("capture contract is not available for this resource")

        values: dict[str, Any] = {
            "amount": str(amount), "currency": currency, "valid_at": as_at,
        }
        for name, value in (("evidence_reference", evidence_reference),
                            ("valuation_basis", valuation_basis), ("source", source)):
            if value is not None:
                values[name] = value
        request = {
            "operation": "propose_financial_observation",
            "household_id": self.household_id,
            "resource_id": resource_id,
            "capture_contract_id": capture_contract_id,
            "values": values,
            "principal": self.principal,
        }
        digest = _proposal_digest(request)
        for event in self.log.events():
            if event["kind"] != "application.mcp_capture.proposed":
                continue
            payload = event["payload"]
            if (payload.get("household_id") == self.household_id
                    and payload.get("command_id") == command_id):
                if payload.get("request_digest") != digest:
                    raise McpClientSafeDenied("command id was already used for a different capture")
                return FinancialObservationProposalReceipt(
                    payload["proposal_id"], payload["envelope_id"], payload["contract_id"],
                    payload["contract_version"], resource_id, payload["review_summary"], command_id)

        capture_service = CaptureService(self.log, household_id=self.household_id)
        try:
            contract, normalised = capture_service.normalise(capture_contract_id, values)
            review_summary = contract.review_summary(normalised, subject_id=resource_id)
            receipt = capture_service.propose(
                capture_contract_id, operation["target_id"], values,
                actor=f"mcp:{self.principal}", channel="manual", idempotency_key=command_id,
                audit=CaptureAudit("mcp", self.principal, command_id,
                                   self.client, self.witness_model))
        except LookupError as exc:
            # A target identifier is household-scoped; never reflect it through MCP.
            raise McpClientSafeDenied("capture target is unavailable") from exc
        except CaptureValidationError as exc:
            # This is the deliberately bounded capture-contract validation
            # vocabulary.  It is a ValueError subclass, so it must be handled
            # before generic parser or implementation failures.
            raise McpClientSafeDenied(str(exc)) from exc
        except (AcquisitionError, ValueError, TypeError) as exc:
            raise McpWriteDenied("financial observation proposal refused") from exc

        self.log.append("application.mcp_capture.proposed", {
            "operation": "propose_financial_observation", "command_id": command_id,
            "request_digest": digest, "household_id": self.household_id,
            "resource_id": resource_id, "contract_id": contract.identifier,
            "contract_version": contract.version, "proposal_id": receipt.proposal_id,
            "envelope_id": receipt.envelope_id, "review_summary": review_summary,
            "principal": self.principal, "client": self.client,
            "witness_model": self.witness_model,
        }, actor=f"mcp:{self.principal}")
        return FinancialObservationProposalReceipt(
            receipt.proposal_id, receipt.envelope_id, contract.identifier,
            contract.version, resource_id, review_summary, command_id)

    def record_account_balance(self, resource_id: str, amount: float, currency: str, as_at: str,
                               request_id: str, evidence_reference: str | None = None) -> ProposalReceipt:
        if not PrincipalHouseholdAuthority(self.log).permits_write(self.principal, self.household_id):
            raise McpWriteDenied("principal is not authorised to mutate this household")
        query = FinancialResourceQuery(self.log, self.household_id)
        try:
            resource = query.get_financial_resource(resource_id)
            availability = query.capture_availability(resource_id)
        except ResourceNotFound as exc:
            raise McpWriteDenied("account is unavailable") from exc
        if resource["resource_kind"] != "account":
            raise McpWriteDenied("resource does not support account balance capture")
        operation = next((item for item in availability["supported_capture_operations"]
                          if item["contract_id"] in {"cash-balance-update", "pension-balance-update"}), None)
        if operation is None:
            raise McpWriteDenied("account does not support governed balance capture")
        receipt = self.propose_financial_observation(
            resource_id=resource_id, capture_contract_id=operation["contract_id"],
            amount=amount, currency=currency, as_at=as_at, command_id=request_id,
            evidence_reference=evidence_reference)
        return ProposalReceipt(receipt.envelope_id, receipt.proposal_id)

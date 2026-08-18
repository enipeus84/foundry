"""One governed MCP command; it remains on the proposal side of confirmation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from foundry.application.capture import CaptureAudit, CaptureService, ProposalReceipt
from foundry.application.resources import (
    FinancialResourceCommandService, FinancialResourceQuery, ResourceCommandDenied, ResourceNotFound,
)
from foundry.core.principal_authority import PrincipalHouseholdAuthority
from foundry.eventlog import EventLog


class McpWriteDenied(PermissionError):
    """MCP writes fail closed when authority or an eligible command is absent."""


@dataclass(frozen=True)
class McpFinancialResourceWrites:
    log: EventLog
    principal: str
    household_id: str
    client: str
    witness_model: str

    def create(self, *, resource_type: str, currency: str, name: str | None = None,
               provider: str | None = None, owner: str | None = None,
               owners: list[str] | None = None, liquidity_classification: str | None = None,
               command_id: str) -> dict[str, Any]:
        if not command_id.strip():
            raise McpWriteDenied("command_id is required for idempotent execution")
        try:
            return FinancialResourceCommandService(self.log).create_financial_resource(
                household_id=self.household_id, resource_type=resource_type, currency=currency,
                name=name, provider=provider, owner=owner, owners=owners,
                liquidity_classification=liquidity_classification,
                actor=f"mcp:{self.principal}", principal=self.principal, command_id=command_id,
                client=self.client, witness_model=self.witness_model)
        except ResourceCommandDenied as exc:
            raise McpWriteDenied(str(exc)) from exc

    def update(self, *, resource_id: str, name: str, command_id: str,
               reason: str = "metadata update") -> dict[str, Any]:
        try:
            return FinancialResourceCommandService(self.log).update_financial_resource(
                household_id=self.household_id, resource_id=resource_id, name=name,
                reason=reason, actor=f"mcp:{self.principal}", principal=self.principal,
                command_id=command_id, client=self.client, witness_model=self.witness_model)
        except (ResourceCommandDenied, ResourceNotFound) as exc:
            raise McpWriteDenied(str(exc)) from exc

    def close(self, *, resource_id: str, command_id: str, reason: str = "closed") -> dict[str, Any]:
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
        values: dict[str, Any] = {"amount": str(amount), "currency": currency, "valid_at": as_at}
        if evidence_reference is not None:
            values["evidence_reference"] = evidence_reference
        return CaptureService(self.log, household_id=self.household_id).propose(
            operation["contract_id"], operation["target_id"], values,
            actor=f"mcp:{self.principal}", channel="manual", idempotency_key=request_id,
            audit=CaptureAudit("mcp", self.principal, request_id, self.client, self.witness_model))

"""Privileged MCP adapter for Foundry's governed financial-resource surface."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from foundry.application.mcp_context import (
    McpPrincipal, authenticated_principal_from_environment, query_for_mcp_principal,
)
from foundry.application.mcp_writes import McpBalanceCapture, McpFinancialResourceWrites, McpWriteDenied
from foundry.application.resources import FinancialResourceQuery, ResourceNotFound


def create_mcp_server(query: FinancialResourceQuery | None = None,
                      principal: McpPrincipal | None = None,
                      streamable_http_path: str = "/mcp", *, host: str = "127.0.0.1",
                      transport_security=None, auth=None, auth_server_provider=None) -> FastMCP:
    """Build the fixed three-tool MCP surface; no transport code knows event shapes."""
    active_principal = principal or authenticated_principal_from_environment()
    query = query or query_for_mcp_principal(active_principal)
    balance_capture = McpBalanceCapture(
        query.log, active_principal.email, active_principal.household_id,
        active_principal.client, active_principal.witness_model)
    resource_writes = McpFinancialResourceWrites(
        query.log, active_principal.email, active_principal.household_id,
        active_principal.client, active_principal.witness_model)
    server = FastMCP("Foundry", instructions="Governed financial-resource access.",
                     streamable_http_path=streamable_http_path, host=host,
                     transport_security=transport_security, auth=auth,
                     auth_server_provider=auth_server_provider)

    @server.tool()
    def list_financial_resources() -> dict:
        """List registered financial resources visible to the authenticated household."""
        resources = query.list_financial_resources()
        for resource in resources:
            resource["capture_availability"] = query.capture_availability(resource["id"])
        return {"resources": resources}

    @server.tool()
    def get_financial_resource(resource_id: str) -> dict:
        """Return one registered financial resource and its canonical provenance references."""
        try:
            result = query.get_financial_resource(resource_id)
            result["capture_availability"] = query.capture_availability(resource_id)
            return result
        except ResourceNotFound as exc:
            raise ValueError("unknown financial resource") from exc

    @server.tool()
    def create_financial_resource(resource_type: str, currency: str, owner: str | None = None,
                                  name: str | None = None, provider: str | None = None,
                                  owners: list[str] | None = None,
                                  liquidity_classification: str | None = None) -> dict:
        """Propose creation; this tool never mutates canonical financial state."""
        receipt = resource_writes.propose_create(
            resource_type=resource_type, currency=currency, owner=owner, owners=owners,
            name=name, provider=provider, liquidity_classification=liquidity_classification)
        return {"operation": "create_financial_resource", "state": "proposed",
                "proposal_id": receipt.proposal_id, "requires_execution": True,
                "resource_type": resource_type, "currency": currency,
                "owner": owner, "owners": owners, "name": name, "provider": provider,
                "liquidity_classification": liquidity_classification}

    @server.tool()
    def execute_create_financial_resource(resource_type: str, currency: str, command_id: str,
                                          proposal_id: str, owner: str | None = None,
                                          name: str | None = None, provider: str | None = None,
                                          owners: list[str] | None = None,
                                          liquidity_classification: str | None = None) -> dict:
        """Execute a previously proposed creation by its proposal receipt."""
        try:
            return resource_writes.create(resource_type=resource_type, currency=currency,
                                          owner=owner, owners=owners, command_id=command_id,
                                          proposal_id=proposal_id,
                                          name=name, provider=provider,
                                          liquidity_classification=liquidity_classification)
        except McpWriteDenied as exc:
            raise ValueError("financial resource creation refused") from exc

    @server.tool()
    def update_financial_resource(resource_id: str, name: str, reason: str = "metadata update") -> dict:
        receipt = resource_writes.propose_update(resource_id=resource_id, name=name, reason=reason)
        return {"operation": "update_financial_resource", "state": "proposed",
                "proposal_id": receipt.proposal_id, "resource_id": resource_id,
                "name": name, "reason": reason, "requires_execution": True}

    @server.tool()
    def execute_update_financial_resource(resource_id: str, name: str, command_id: str,
                                          proposal_id: str,
                                  reason: str = "metadata update") -> dict:
        """Execute a previously proposed resource rename."""
        try:
            return resource_writes.update(resource_id=resource_id, name=name,
                                          command_id=command_id, reason=reason, proposal_id=proposal_id)
        except McpWriteDenied as exc:
            raise ValueError("financial resource update refused") from exc

    @server.tool()
    def close_financial_resource(resource_id: str, reason: str = "closed") -> dict:
        """Propose closure without changing the canonical resource."""
        receipt = resource_writes.propose_close(resource_id=resource_id, reason=reason)
        return {"operation": "close_financial_resource", "state": "proposed",
                "proposal_id": receipt.proposal_id, "resource_id": resource_id,
                "reason": reason, "requires_execution": True}

    @server.tool()
    def execute_close_financial_resource(resource_id: str, command_id: str,
                                         proposal_id: str, reason: str = "closed") -> dict:
        """Execute a previously proposed resource closure."""
        try:
            return resource_writes.close(resource_id=resource_id, command_id=command_id,
                                         reason=reason, proposal_id=proposal_id)
        except McpWriteDenied as exc:
            raise ValueError("financial resource closure refused") from exc

    @server.tool()
    def explain_capture_availability(resource_id: str) -> dict:
        """Describe existing governed capture operations supported by one resource."""
        try:
            return query.capture_availability(resource_id)
        except ResourceNotFound as exc:
            raise ValueError("unknown financial resource") from exc

    @server.tool()
    def record_account_balance(resource_id: str, amount: float, currency: str, as_at: str,
                               request_id: str, evidence_reference: str | None = None) -> dict:
        """Create a reviewable governed balance-capture proposal for an authorised account."""
        try:
            receipt = balance_capture.record_account_balance(
                resource_id, amount, currency, as_at, request_id, evidence_reference)
        except (McpWriteDenied, ValueError) as exc:
            raise ValueError("account balance capture refused") from exc
        return {"proposal_id": receipt.proposal_id, "envelope_id": receipt.envelope_id,
                "state": "pending"}

    return server


def main() -> None:
    create_mcp_server().run(transport="stdio")


if __name__ == "__main__":
    main()

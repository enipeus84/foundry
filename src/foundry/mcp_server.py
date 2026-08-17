"""Privileged MCP adapter for Foundry's governed financial-resource surface."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from foundry.application.mcp_context import (
    McpPrincipal, authenticated_principal_from_environment, query_for_mcp_principal,
)
from foundry.application.mcp_writes import McpBalanceCapture, McpWriteDenied
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
    server = FastMCP("Foundry", instructions="Governed financial-resource access.",
                     streamable_http_path=streamable_http_path, host=host,
                     transport_security=transport_security, auth=auth,
                     auth_server_provider=auth_server_provider)

    @server.tool()
    def list_financial_resources() -> dict:
        """List registered financial resources visible to the authenticated household."""
        return {"resources": query.list_financial_resources()}

    @server.tool()
    def get_financial_resource(resource_id: str) -> dict:
        """Return one registered financial resource and its canonical provenance references."""
        try:
            return query.get_financial_resource(resource_id)
        except ResourceNotFound as exc:
            raise ValueError("unknown financial resource") from exc

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

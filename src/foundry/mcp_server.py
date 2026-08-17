"""Privileged, read-only MCP adapter for Foundry's financial-resource state."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from foundry.application.mcp_context import (
    McpPrincipal, authenticated_principal_from_environment, query_for_mcp_principal,
)
from foundry.application.resources import FinancialResourceQuery, ResourceNotFound


def create_mcp_server(query: FinancialResourceQuery | None = None,
                      principal: McpPrincipal | None = None) -> FastMCP:
    """Build the fixed three-tool MCP surface; no transport code knows event shapes."""
    active_principal = principal or authenticated_principal_from_environment()
    query = query or query_for_mcp_principal(active_principal)
    server = FastMCP("Foundry", instructions="Read-only governed financial-resource access.")

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

    return server


def main() -> None:
    create_mcp_server().run(transport="stdio")


if __name__ == "__main__":
    main()

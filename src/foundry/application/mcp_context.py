"""Authenticated application context for the privileged MCP boundary."""

from __future__ import annotations

from dataclasses import dataclass
import os

from foundry import webauth
from foundry.application.resources import FinancialResourceQuery
from foundry.core.entities import EntityProjection
from foundry.eventlog import EventLog


@dataclass(frozen=True)
class McpPrincipal:
    email: str
    household_id: str
    client: str
    witness_model: str


def authenticated_principal_from_environment() -> McpPrincipal:
    """Resolve a server-owned principal binding; tool arguments carry no authority."""
    token = os.environ.get("FOUNDRY_MCP_SESSION_TOKEN")
    household_id = os.environ.get("FOUNDRY_MCP_HOUSEHOLD_ID")
    client = os.environ.get("FOUNDRY_MCP_CLIENT")
    witness_model = os.environ.get("FOUNDRY_WITNESS_MODEL")
    if not token or not household_id or not client or not witness_model:
        raise PermissionError("Foundry MCP requires an authenticated principal and household binding")
    email = webauth.session_email(token, webauth.load_config())
    if email is None:
        raise PermissionError("Foundry MCP principal authentication failed")
    log = EventLog(os.environ.get("FOUNDRY_DATA_PATH", "foundry_data/events.jsonl"))
    household = EntityProjection(log).parties.get(household_id)
    if household is None or household.party_type != "household" or household.status != "active":
        raise PermissionError("Foundry MCP household binding is unavailable")
    return McpPrincipal(email, household_id, client, witness_model)


def remote_principal_from_environment() -> McpPrincipal:
    """Resolve the fixed, deployment-owned identity for remote MCP."""
    email = os.environ.get("FOUNDRY_MCP_PRINCIPAL", "").strip().lower()
    household_id = os.environ.get("FOUNDRY_MCP_HOUSEHOLD_ID")
    client = os.environ.get("FOUNDRY_MCP_CLIENT")
    witness_model = os.environ.get("FOUNDRY_WITNESS_MODEL")
    config = webauth.load_config()
    if not all((email, household_id, client, witness_model)):
        raise PermissionError("Foundry remote MCP is not configured")
    if not config.configured or email != config.allowed_email:
        raise PermissionError("Foundry remote MCP principal is not permitted")
    log = EventLog(os.environ.get("FOUNDRY_DATA_PATH", "foundry_data/events.jsonl"))
    household = EntityProjection(log).parties.get(household_id)
    if household is None or household.party_type != "household" or household.status != "active":
        raise PermissionError("Foundry MCP household binding is unavailable")
    return McpPrincipal(email, household_id, client, witness_model)


def query_for_mcp_principal(principal: McpPrincipal) -> FinancialResourceQuery:
    log = EventLog(os.environ.get("FOUNDRY_DATA_PATH", "foundry_data/events.jsonl"))
    return FinancialResourceQuery(log, principal.household_id)

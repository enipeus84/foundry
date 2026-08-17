"""RFC-021 Burn 02: authenticated, household-scoped MCP reads."""

from __future__ import annotations

import asyncio
import inspect
import os
import sys

import pytest

pytest.importorskip("mcp")
from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402

from foundry import webauth  # noqa: E402
from foundry.application.resources import FinancialResourceQuery, ResourceNotFound  # noqa: E402
from foundry.core.acquisition import AssetRegistration, TelemetryStream, TelemetryStreamRegistry  # noqa: E402
from foundry.core.entities import declare_party, join_household  # noqa: E402
from foundry.eventlog import EventLog  # noqa: E402
from foundry.finance import entities as finance  # noqa: E402
from foundry.finance.capture_targets import finance_asset_registry  # noqa: E402
from foundry.application.mcp_context import authenticated_principal_from_environment  # noqa: E402
import foundry.mcp_server as mcp_server  # noqa: E402


ALLOWED = "mcp@example.com"


@pytest.fixture(autouse=True)
def environment(monkeypatch, tmp_path):
    monkeypatch.setenv("FOUNDRY_ALLOWED_EMAIL", ALLOWED)
    monkeypatch.setenv("SESSION_SECRET", "unit-test-secret-0123456789abcdef")
    monkeypatch.setenv("FOUNDRY_DATA_PATH", str(tmp_path / "events.jsonl"))
    return tmp_path


def _world(path):
    log = EventLog(path / "events.jsonl")
    household = declare_party(log, "household")
    person = declare_party(log, "person")
    join_household(log, person.id, household.id)
    account = finance.declare_account(log, "checking", "GBP", name="Household cash")
    finance.link_ownership(log, "account", account.id, "owner", person.id)
    registry = finance_asset_registry(log)
    registry.register(AssetRegistration(account.id, "finance", household.id))
    TelemetryStreamRegistry(log).declare(TelemetryStream(
        id="cash-balance", subject_id=account.id, property="cash_balance", channel="manual",
        refresh_policy="annual", confirmation_policy="review_each", source_identity="user:mcp",
        unit_or_currency="GBP", validation_contract="numeric", household_id=household.id,
        expected_cadence="annual"))
    other_household = declare_party(log, "household")
    other_account = finance.declare_account(log, "checking", "GBP", name="Other cash")
    finance_asset_registry(log).register(AssetRegistration(other_account.id, "finance", other_household.id))
    return log, household, account, other_account


def test_resource_query_is_household_scoped_and_exposes_domain_shape(environment):
    log, household, account, other_account = _world(environment)
    query = FinancialResourceQuery(log, household.id)
    assert query.list_financial_resources() == [{
        "id": account.id, "resource_kind": "account", "resource_type": "checking",
        "name": "Household cash", "currency": "GBP", "status": "active",
        "liquidity_classification": None,
        "ownership": [{"relation": "owner", "subject_id": next(iter(
            finance.FinanceEntityProjection(log).accounts[account.id].ownership)).target}],
    }]
    resource = query.get_financial_resource(account.id)
    assert resource["provenance"]["event_ids"]
    assert query.capture_availability(account.id)["supported_capture_operations"] == [{
        "contract_id": "cash-balance-update", "contract_version": "1", "target_id": "cash-balance"}]
    with pytest.raises(ResourceNotFound):
        query.get_financial_resource(other_account.id)


def test_mcp_principal_requires_server_owned_authenticated_context(monkeypatch):
    monkeypatch.delenv("FOUNDRY_MCP_SESSION_TOKEN", raising=False)
    monkeypatch.delenv("FOUNDRY_MCP_HOUSEHOLD_ID", raising=False)
    with pytest.raises(PermissionError):
        authenticated_principal_from_environment()


def test_mcp_client_connects_and_cannot_cross_household(environment):
    log, household, account, other_account = _world(environment)
    token = webauth.session_token(ALLOWED, webauth.load_config())
    server = StdioServerParameters(
        command=sys.executable, args=["-m", "foundry.mcp_server"],
        env={**os.environ, "FOUNDRY_DATA_PATH": str(log.path),
             "FOUNDRY_MCP_SESSION_TOKEN": token, "FOUNDRY_MCP_HOUSEHOLD_ID": household.id},
    )

    async def exercise():
        async with stdio_client(server) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                assert {tool.name for tool in tools.tools} == {
                    "list_financial_resources", "get_financial_resource", "explain_capture_availability"}
                listed = await session.call_tool("list_financial_resources", {})
                assert account.id in listed.content[0].text
                available = await session.call_tool("explain_capture_availability", {"resource_id": account.id})
                assert "cash-balance-update" in available.content[0].text
                denied = await session.call_tool("get_financial_resource", {"resource_id": other_account.id})
                assert denied.isError
                malformed = await session.call_tool("get_financial_resource", {"resource_id": 7})
                assert malformed.isError

    asyncio.run(exercise())


def test_mcp_adapter_has_no_persistence_or_generic_query_surface():
    source = inspect.getsource(mcp_server)
    assert "EventLog" not in source
    assert "events.jsonl" not in source
    assert "query_events" not in source
    assert "append_event" not in source

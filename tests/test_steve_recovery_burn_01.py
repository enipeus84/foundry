"""Steve Recovery Burn 01: Pension Independence through MCP only."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import os
import sys

import pytest

pytest.importorskip("mcp")
from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402

from foundry import webauth  # noqa: E402
from foundry.application.pension_mission import PensionMissionQueryService  # noqa: E402
from foundry.core import grammar  # noqa: E402
from foundry.core.entities import EntityProjection  # noqa: E402
from foundry.core.mission_targets import TargetQuantity  # noqa: E402
from foundry.core.principal_authority import grant_principal_household_authority  # noqa: E402
from foundry.demo_data import build  # noqa: E402
from foundry.eventlog import EventLog  # noqa: E402
from foundry.finance import entities as finance  # noqa: E402
from foundry.finance.entities import FinanceEntityProjection  # noqa: E402
from foundry.finance.pension_assessment import POLICY_ID  # noqa: E402


ALLOWED = "mcp@example.com"


def test_mcp_commissions_and_evaluates_pension_independence(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    household = build(log, as_of=1_785_170_000.0)
    mission = next(
        item for item in EntityProjection(log).missions.values()
        if item.assessment_policy_id == POLICY_ID)
    # Production's RFC-016 declaration binds a household through its Mission
    # Target, not the retired Mission.household_id convenience field.
    grammar.update(log, "core", "mission", mission.id, {"household_id": None},
                   "exercise canonical target binding", actor="test")
    _, _, _, targets = PensionMissionQueryService(log, household.household_id)._composition()
    descriptor = targets.metric_resolver.describe(mission.target_metric)
    targets.declare(
        household_id=household.household_id, subject_id=household.household_id,
        mission_id=mission.id, metric_id=mission.target_metric,
        destination=TargetQuantity(735_000, descriptor.unit_or_currency, descriptor.dimension),
        destination_direction=descriptor.destination_direction, horizon_kind="derived",
        horizon_at=None, effective_from=log.get(mission.provenance[0])["ts"], actor="test")
    existing = FinanceEntityProjection(log).assumption_sets[mission.assumption_set_id]
    assumptions = {
        key: value for key, value in existing.assumptions.items()
        if not key.startswith("milestone_fraction_")
    }
    finance.archive_assumption_set(log, existing.id, "commissioning precondition")
    grant_principal_household_authority(log, ALLOWED, household.household_id, actor="test")

    env = {
        **os.environ,
        "FOUNDRY_ALLOWED_EMAIL": ALLOWED,
        "SESSION_SECRET": "unit-test-secret-0123456789abcdef",
        "FOUNDRY_DATA_PATH": str(log.path),
        "FOUNDRY_MCP_CLIENT": "acceptance-client",
        "FOUNDRY_WITNESS_MODEL": "acceptance-model",
        "FOUNDRY_MCP_HOUSEHOLD_ID": household.household_id,
    }
    env["FOUNDRY_MCP_SESSION_TOKEN"] = webauth.session_token(
        ALLOWED, webauth.AuthConfig(
            "test", "test", ALLOWED,
            env["SESSION_SECRET"].encode(), "", False))
    as_of = datetime.now(timezone.utc).isoformat()
    server = StdioServerParameters(
        command=sys.executable, args=["-m", "foundry.mcp_server"], env=env)

    async def exercise():
        async with stdio_client(server) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                inspected = await session.call_tool(
                    "inspect_pension_independence", {"as_of": as_of})
                diagnosis = json.loads(inspected.content[0].text)
                assert diagnosis["mission"]["id"] == mission.id
                assert diagnosis["evaluable"] is False
                assert diagnosis["blockers"] == ["active pension Assumption Set not found"]

                proposed = await session.call_tool(
                    "propose_mission_assumption_set",
                    {"mission_id": mission.id, "assumptions": assumptions})
                proposal = json.loads(proposed.content[0].text)
                executed = await session.call_tool(
                    "execute_mission_assumption_set", {
                        "mission_id": mission.id,
                        "assumptions": assumptions,
                        "proposal_id": proposal["proposal_id"],
                        "command_id": "steve-recovery-burn-01",
                    })
                assert not executed.isError

                value_response = await session.call_tool(
                    "get_current_pension_value", {"as_of": as_of})
                value = json.loads(value_response.content[0].text)
                assert value["current_pension_value"]["value"] == 62_000.0
                assert value["current_pension_value"]["status"] == "available"

                evaluated = await session.call_tool(
                    "evaluate_pension_independence", {"as_of": as_of})
                result = json.loads(evaluated.content[0].text)
                assert result["evaluable"] is True
                assert result["status"] == "Nominal"
                assert result["current_relevant_value"]["value"] == 62_000.0
                assert result["target"]["value"] == 735_000.0
                assert result["gap"]["value"] == 673_000.0
                assert result["horizon"]["planning_at"] is not None
                assert result["assumptions_used"]["id"]
                assert result["provenance"]["evidence_references"]
                assert result["blockers"] == []

                planning = await session.call_tool(
                    "explain_pension_independence_planning_point", {"as_of": as_of})
                explanation = json.loads(planning.content[0].text)
                assert explanation["mission"]["id"] == mission.id
                assert explanation["planning_point"]["planning_at"] is not None
                assert explanation["planning_point"]["participants"]
                assert explanation["compatibility"]["tolerance"] == "P1D"

    asyncio.run(exercise())

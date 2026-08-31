"""Burn 47c.5: governed amendment of canonical resource liquidity."""

from __future__ import annotations

import pytest

from foundry.application.mcp_context import McpPrincipal
from foundry.application.mcp_writes import McpFinancialResourceWrites, McpWriteDenied
from foundry.application.resources import FinancialResourceQuery
from foundry.core import grammar
from foundry.core.entities import EntityProjection, declare_party, join_household, update_party
from foundry.core.metrics import MetricRegistry, MetricRequest
from foundry.core.principal_authority import grant_principal_household_authority
from foundry.core.scope import Subject
from foundry.eventlog import EventLog
from foundry.finance import entities as finance
from foundry.finance.entities import FinanceEntityProjection
from foundry.finance.metrics import FinanceMetricProvider
from foundry.mcp_server import create_mcp_server


PRINCIPAL = "liquidity-operator@example.com"


def _world(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    household = declare_party(log, "household")
    chris = declare_party(log, "person")
    update_party(log, chris.id, {"name": "Chris"}, "test identity")
    join_household(log, chris.id, household.id)
    grant_principal_household_authority(log, PRINCIPAL, household.id, actor="test")
    writes = McpFinancialResourceWrites(log, PRINCIPAL, household.id, "test-client", "test-model")
    created = writes.propose_create(resource_type="isa", currency="GBP", name="Vida Cash ISA", owner="Chris")
    resource = writes.create(resource_type="isa", currency="GBP", name="Vida Cash ISA", owner="Chris",
                             command_id="create-vida", proposal_id=created.proposal_id)
    return log, household, resource, writes


def test_null_liquidity_is_amended_by_exact_governed_proposal_and_execution(tmp_path):
    log, household, resource, writes = _world(tmp_path)
    finance.declare_valuation(log, resource["id"], 20_280.90, "GBP", 1_787_996_800.0)
    before = FinancialResourceQuery(log, household.id).get_financial_resource(resource["id"])

    proposal = writes.propose_update(
        resource_id=resource["id"], liquidity_classification="near_liquid",
        reason="household explicitly classified the ISA")
    amended = writes.update(
        resource_id=resource["id"], liquidity_classification="near_liquid",
        reason="household explicitly classified the ISA", command_id="vida-liquidity-1",
        proposal_id=proposal.proposal_id)

    assert amended["liquidity_classification"] == "near_liquid"
    assert amended["name"] == before["name"]
    assert amended["currency"] == before["currency"]
    assert amended["ownership"] == before["ownership"]
    assert len(FinanceEntityProjection(log).valuations_of(resource["id"])) == 1
    update = [event for event in log.events() if event["kind"] == "finance.account.updated"][-1]
    assert update["payload"] == {
        "entity_id": resource["id"], "reason": "household explicitly classified the ISA",
        "liquidity_classification": "near_liquid",
    }
    read = FinancialResourceQuery(log, household.id).get_financial_resource(resource["id"])
    assert update["id"] in read["provenance"]["history_event_ids"]


@pytest.mark.parametrize("classification", ["cash", "NEAR_LIQUID", "", "liquidish"])
def test_invalid_liquidity_values_fail_closed_before_any_canonical_update(tmp_path, classification):
    log, _, resource, writes = _world(tmp_path)
    before = list(log.events())

    with pytest.raises(McpWriteDenied, match="liquidity_classification"):
        writes.propose_update(resource_id=resource["id"], liquidity_classification=classification,
                              reason="household classification")

    assert list(log.events()) == before


@pytest.mark.parametrize("classification", [
    "liquid", "near_liquid", "illiquid_short", "illiquid_long",
])
def test_every_existing_liquidity_vocabulary_value_is_a_valid_amendment(tmp_path, classification):
    log, household, resource, writes = _world(tmp_path)
    proposal = writes.propose_update(resource_id=resource["id"], liquidity_classification=classification,
                                     reason="household classification")

    amended = writes.update(resource_id=resource["id"], liquidity_classification=classification,
                            reason="household classification", command_id=f"classify-{classification}",
                            proposal_id=proposal.proposal_id)

    assert FinancialResourceQuery(log, household.id).get_financial_resource(
        resource["id"])["liquidity_classification"] == classification == amended["liquidity_classification"]


def test_cross_household_and_unauthorised_liquidity_amendments_fail_closed(tmp_path):
    log, _, resource, _ = _world(tmp_path)
    other = declare_party(log, "household")
    other_person = declare_party(log, "person")
    update_party(log, other_person.id, {"name": "Alex"}, "test identity")
    join_household(log, other_person.id, other.id)
    grant_principal_household_authority(log, PRINCIPAL, other.id, actor="test")
    cross_household = McpFinancialResourceWrites(log, PRINCIPAL, other.id, "test-client", "test-model")
    unauthorised = McpFinancialResourceWrites(log, "outsider@example.com", other.id, "test-client", "test-model")

    with pytest.raises(McpWriteDenied):
        cross_household.propose_update(resource_id=resource["id"], liquidity_classification="liquid",
                                       reason="not this household")
    with pytest.raises(McpWriteDenied, match="not authorised"):
        unauthorised.propose_update(resource_id=resource["id"], liquidity_classification="liquid",
                                    reason="not authorised")
    assert FinanceEntityProjection(log).accounts[resource["id"]].liquidity_classification is None


def test_stale_resource_state_noop_and_command_reuse_fail_closed(tmp_path):
    log, household, resource, writes = _world(tmp_path)
    stale = writes.propose_update(resource_id=resource["id"], liquidity_classification="liquid",
                                  reason="household classification")
    grammar.update(log, "finance", "account", resource["id"], {"name": "Vida ISA"},
                   "intervening canonical amendment")
    with pytest.raises(McpWriteDenied, match="does not match"):
        writes.update(resource_id=resource["id"], liquidity_classification="liquid",
                      reason="household classification", command_id="stale-1",
                      proposal_id=stale.proposal_id)

    current = writes.propose_update(resource_id=resource["id"], liquidity_classification="liquid",
                                    reason="household classification")
    first = writes.update(resource_id=resource["id"], liquidity_classification="liquid",
                          reason="household classification", command_id="replay-1",
                          proposal_id=current.proposal_id)
    assert writes.update(resource_id=resource["id"], liquidity_classification="liquid",
                         reason="household classification", command_id="replay-1",
                         proposal_id=current.proposal_id) == first
    with pytest.raises(McpWriteDenied, match="different request"):
        writes.update(resource_id=resource["id"], liquidity_classification="near_liquid",
                      reason="different classification", command_id="replay-1",
                      proposal_id="not-used")
    with pytest.raises(McpWriteDenied, match="already current"):
        writes.propose_update(resource_id=resource["id"], liquidity_classification="liquid",
                              reason="no change")
    assert FinancialResourceQuery(log, household.id).get_financial_resource(
        resource["id"])["liquidity_classification"] == "liquid"


def test_accessible_assets_consumes_the_amended_canonical_field_without_special_case(tmp_path):
    log, household, resource, writes = _world(tmp_path)
    as_of = 1_787_996_800.0
    finance.declare_transaction(log, resource["id"], 20_280.90, "GBP", "income", as_of)

    def accessible():
        registry = MetricRegistry()
        registry.register(FinanceMetricProvider(FinanceEntityProjection(log), EntityProjection(log)))
        return registry.dispatch(MetricRequest(
            "finance.accessible_assets", Subject("party", household.id), as_of))

    assert accessible().status == "unavailable"
    proposal = writes.propose_update(resource_id=resource["id"], liquidity_classification="near_liquid",
                                     reason="household classification")
    writes.update(resource_id=resource["id"], liquidity_classification="near_liquid",
                  reason="household classification", command_id="accessible-assets-1",
                  proposal_id=proposal.proposal_id)

    result = accessible()
    assert result.status == "available" and result.value == pytest.approx(20_280.90)


def test_mcp_update_surface_exposes_the_governed_liquidity_amendment(tmp_path):
    log, household, resource, _ = _world(tmp_path)
    principal = McpPrincipal(PRINCIPAL, household.id, "test-client", "test-model")
    server = create_mcp_server(FinancialResourceQuery(log, household.id), principal)
    propose = server._tool_manager.get_tool("update_financial_resource").fn
    execute = server._tool_manager.get_tool("execute_update_financial_resource").fn

    receipt = propose(resource_id=resource["id"], liquidity_classification="near_liquid",
                      reason="household classification")
    result = execute(resource_id=resource["id"], liquidity_classification="near_liquid",
                     reason="household classification", command_id="mcp-liquidity-1",
                     proposal_id=receipt["proposal_id"])

    assert receipt["state"] == "proposed" and receipt["requires_execution"] is True
    assert receipt["liquidity_classification"] == "near_liquid"
    assert result["liquidity_classification"] == "near_liquid"

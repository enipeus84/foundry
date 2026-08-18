"""Burn 07: governed MCP financial-resource management."""

import pytest

from foundry.application.mcp_writes import McpFinancialResourceWrites, McpWriteDenied
from foundry.application.resources import FinancialResourceCommandService, FinancialResourceQuery
from foundry.core.entities import declare_party, join_household, update_party
from foundry.core.principal_authority import grant_principal_household_authority
from foundry.eventlog import EventLog
from foundry.finance import entities as finance


PRINCIPAL = "mcp@example.com"


def _world(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    household = declare_party(log, "household")
    chris = declare_party(log, "person")
    update_party(log, chris.id, {"name": "Chris"}, "test identity")
    join_household(log, chris.id, household.id)
    grant_principal_household_authority(log, PRINCIPAL, household.id, actor="test")
    writes = McpFinancialResourceWrites(log, PRINCIPAL, household.id, "claude-code", "gpt-test")
    return log, household, writes


def test_confirmed_creation_is_canonical_idempotent_and_discovers_capture(tmp_path):
    log, household, writes = _world(tmp_path)
    before = list(log.events())
    with pytest.raises(McpWriteDenied):
        writes.create(resource_type="pension", currency="GBP", owner="Chris", command_id="cmd-1")
    assert list(log.events()) == before

    proposal = writes.propose_create(resource_type="pension", currency="GBP", provider="Aviva",
                                     owner="Chris")
    first = writes.create(resource_type="pension", currency="GBP", provider="Aviva",
                          owner="Chris", command_id="cmd-1", proposal_id=proposal.proposal_id)
    second = writes.create(resource_type="pension", currency="GBP", provider="Aviva",
                           owner="Chris", command_id="cmd-1", proposal_id=proposal.proposal_id)
    assert first["id"] == second["id"]
    assert first["resource_type"] == "pension"
    availability = FinancialResourceQuery(log, household.id).capture_availability(first["id"])
    assert availability["supported_capture_operations"][0]["contract_id"] == "pension-balance-update"
    assert sum(event["kind"] == "finance.account.declared" for event in log.events()) == 1


def test_update_and_close_are_metadata_lifecycle_commands_with_audit(tmp_path):
    log, household, writes = _world(tmp_path)
    create_proposal = writes.propose_create(resource_type="isa", currency="GBP", name="AJ Bell ISA",
                                            owner="Chris")
    resource = writes.create(resource_type="isa", currency="GBP", name="AJ Bell ISA",
                             owner="Chris", command_id="cmd-create",
                             proposal_id=create_proposal.proposal_id)
    update_proposal = writes.propose_update(resource_id=resource["id"],
                                            name="AJ Bell Stocks & Shares ISA")
    renamed = writes.update(resource_id=resource["id"], name="AJ Bell Stocks & Shares ISA",
                            command_id="cmd-update", proposal_id=update_proposal.proposal_id)
    assert renamed["name"] == "AJ Bell Stocks & Shares ISA"
    close_proposal = writes.propose_close(resource_id=resource["id"], reason="provider transfer")
    closed = writes.close(resource_id=resource["id"], reason="provider transfer",
                          command_id="cmd-close", proposal_id=close_proposal.proposal_id)
    assert closed["status"] == "closed"
    assert len(FinancialResourceQuery(log, household.id).list_financial_resources()) == 1
    assert sum(event["kind"] == "application.mcp_command.executed" for event in log.events()) == 3


def test_arbitrary_owner_ids_are_rejected(tmp_path):
    log, household, writes = _world(tmp_path)
    with pytest.raises(McpWriteDenied):
        writes.create(resource_type="isa", currency="GBP", owner="not-a-household-member",
                      command_id="cmd-owner", proposal_id=writes.propose_create(
                          resource_type="isa", currency="GBP", owner="not-a-household-member").proposal_id)


def test_execute_without_proposal_fails(tmp_path):
    log, household, writes = _world(tmp_path)
    with pytest.raises(McpWriteDenied, match="prior proposal"):
        writes.create(resource_type="isa", currency="GBP", owner="Chris", command_id="cmd-no-proposal")


def test_proposal_cannot_execute_a_different_operation(tmp_path):
    log, household, writes = _world(tmp_path)
    proposal = writes.propose_create(resource_type="isa", currency="GBP", owner="Chris", name="One")
    with pytest.raises(McpWriteDenied, match="does not match"):
        writes.create(resource_type="isa", currency="GBP", owner="Chris", name="Two",
                      command_id="cmd-mismatch", proposal_id=proposal.proposal_id)


def test_same_command_id_is_scoped_to_household(tmp_path):
    log, household, writes = _world(tmp_path)
    other_household = declare_party(log, "household")
    other_person = declare_party(log, "person")
    update_party(log, other_person.id, {"name": "Alex"}, "test identity")
    join_household(log, other_person.id, other_household.id)
    grant_principal_household_authority(log, PRINCIPAL, other_household.id, actor="test")
    other_writes = McpFinancialResourceWrites(log, PRINCIPAL, other_household.id, "claude-code", "gpt-test")
    first_proposal = writes.propose_create(resource_type="isa", currency="GBP", owner="Chris", name="First")
    second_proposal = other_writes.propose_create(resource_type="isa", currency="GBP", owner="Alex", name="Second")
    first = writes.create(resource_type="isa", currency="GBP", owner="Chris", name="First", command_id="shared-command",
                          proposal_id=first_proposal.proposal_id)
    second = other_writes.create(resource_type="isa", currency="GBP", owner="Alex", name="Second", command_id="shared-command",
                                 proposal_id=second_proposal.proposal_id)
    assert first["id"] != second["id"]

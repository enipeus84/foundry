"""Burn 07: governed MCP financial-resource management."""

import pytest

from foundry.application.mcp_writes import McpBalanceCapture, McpFinancialResourceWrites, McpWriteDenied
from foundry.core.acquisition import ProposalInbox
from foundry.application.resources import FinancialResourceCommandService, FinancialResourceQuery
from foundry.core.entities import EntityProjection, declare_party, join_household, update_party
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
    assert sum(event["kind"] == "core.telemetry_stream.declared" for event in log.events()) == 1


def test_isa_registration_provisions_cash_balance_capture_and_stages_observation(tmp_path):
    log, household, writes = _world(tmp_path)
    proposal = writes.propose_create(resource_type="isa", currency="GBP", name="AJ Bell ISA", owner="Chris")
    resource = writes.create(resource_type="isa", currency="GBP", name="AJ Bell ISA", owner="Chris",
                             command_id="isa-create", proposal_id=proposal.proposal_id)

    availability = FinancialResourceQuery(log, household.id).capture_availability(resource["id"])
    assert len(availability["supported_capture_operations"]) == 1
    operation = availability["supported_capture_operations"][0]
    assert operation["contract_id"] == "cash-balance-update"
    assert operation["contract_version"] == "1" and operation["target_id"]
    owner = EntityProjection(log).members_of(household.id)[0]
    assert resource["ownership"] == [{"relation": "owner", "subject_id": owner.id}]

    receipt = McpBalanceCapture(log, PRINCIPAL, household.id, "claude-code", "gpt-test").propose_financial_observation(
        resource_id=resource["id"], capture_contract_id="cash-balance-update", amount=12_345,
        currency="GBP", as_at="2026-08-19T10:30", command_id="isa-observation",
        evidence_reference="AJ Bell statement")
    assert receipt.contract_id == "cash-balance-update"
    assert ProposalInbox(log).proposals[receipt.proposal_id].state == "pending"
    assert not any(event["kind"] == "finance.account.reconciliation_observed" for event in log.events())


def test_unsupported_account_type_does_not_receive_arbitrary_capture_contract(tmp_path):
    log, household, writes = _world(tmp_path)
    proposal = writes.propose_create(resource_type="credit_card", currency="GBP", name="Card", owner="Chris")
    resource = writes.create(resource_type="credit_card", currency="GBP", name="Card", owner="Chris",
                             command_id="card-create", proposal_id=proposal.proposal_id)
    assert FinancialResourceQuery(log, household.id).capture_availability(resource["id"]) == {
        "resource_id": resource["id"], "supported_capture_operations": []}


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

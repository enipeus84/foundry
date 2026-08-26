"""Burn 07: governed MCP financial-resource management."""

import json

import pytest

from foundry.application.mcp_writes import (
    McpBalanceCapture, McpFinancialResourceWrites, McpMortgageEvidenceCapture,
    McpPensionProviderProjectionCapture,
    McpWriteDenied,
)
from foundry.core.acquisition import ProposalInbox
from foundry.application.mcp_context import McpPrincipal
from foundry.application.resources import FinancialResourceCommandService, FinancialResourceQuery
from foundry.mcp_server import create_mcp_server
from foundry.core.entities import EntityProjection, declare_party, join_household, update_party
from foundry.core.metrics import MetricRegistry
from foundry.core.mission_assessment import MissionAssessmentRegistry
from foundry.core.mission_targets import MissionTargetProjection
from foundry.core.principal_authority import grant_principal_household_authority
from foundry.eventlog import EventLog
from foundry.finance import entities as finance
from foundry.finance.entities import FinanceEntityProjection
from foundry.finance.mortgage_evidence import MortgageEvidenceProjection
from foundry.finance.mortgage_assessment import MortgageFreedomAssessor
from foundry.finance.mission_targets import FinanceTargetMetricResolver
from foundry.finance.missions import register_finance_mission_definitions


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


def test_pension_registration_provisions_and_stages_contract_backed_observation(tmp_path):
    log, household, writes = _world(tmp_path)
    proposal = writes.propose_create(resource_type="pension", currency="GBP", name="Aviva", owner="Chris")
    resource = writes.create(resource_type="pension", currency="GBP", name="Aviva", owner="Chris",
                             command_id="pension-create", proposal_id=proposal.proposal_id)

    capture = McpBalanceCapture(log, PRINCIPAL, household.id, "claude-code", "gpt-test")
    with pytest.raises(McpWriteDenied, match="currency must be a three-letter ISO code"):
        capture.propose_financial_observation(
            resource_id=resource["id"], capture_contract_id="pension-balance-update", amount=12_345,
            currency="GB", as_at="2026-08-19T10:30", command_id="invalid-pension-observation")

    receipt = capture.propose_financial_observation(
        resource_id=resource["id"], capture_contract_id="pension-balance-update", amount=12_345,
        currency="GBP", as_at="2026-08-19T10:30", command_id="pension-observation",
        evidence_reference="Aviva statement")
    assert receipt.contract_id == "pension-balance-update"
    assert ProposalInbox(log).proposals[receipt.proposal_id].state == "pending"
    assert not any(event["kind"] == "finance.valuation.declared" for event in log.events())


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


def test_mortgage_creation_is_a_governed_canonical_obligation_with_evidence(tmp_path):
    log, household, writes = _world(tmp_path)
    property_proposal = writes.propose_create(
        resource_type="property", currency="GBP", name="Home", owner="Chris")
    home = writes.create(resource_type="property", currency="GBP", name="Home", owner="Chris",
                         command_id="property-create", proposal_id=property_proposal.proposal_id)
    mortgage_proposal = writes.propose_create(
        resource_type="mortgage", currency="GBP", name="Home mortgage", owner="Chris",
        secured_property_id=home["id"])
    mortgage = writes.create(
        resource_type="mortgage", currency="GBP", name="Home mortgage", owner="Chris",
        secured_property_id=home["id"], command_id="mortgage-create",
        proposal_id=mortgage_proposal.proposal_id)

    assert mortgage["resource_kind"] == "obligation"
    assert mortgage["resource_type"] == "mortgage"
    assert mortgage["ownership"] == [
        {"relation": "owes", "subject_id": EntityProjection(log).members_of(household.id)[0].id},
        {"relation": "secures", "subject_id": home["id"]},
    ]
    assert mortgage["id"] in FinanceEntityProjection(log).obligations
    assert not FinanceEntityProjection(log).accounts.get(mortgage["id"])
    core = EntityProjection(log)
    definitions = MissionAssessmentRegistry()
    register_finance_mission_definitions(definitions)
    targets = MissionTargetProjection(
        log, core, definitions, FinanceTargetMetricResolver())
    scoped, secured, _, reason = MortgageFreedomAssessor(
        FinanceEntityProjection(log), core, MetricRegistry(),
        MortgageEvidenceProjection(log), targets)._scoped_mortgage(household.id)
    assert scoped.id == mortgage["id"] and secured.id == home["id"] and reason == ""

    capture = McpMortgageEvidenceCapture(log, PRINCIPAL, household.id, "claude-code", "gpt-test")
    values = dict(obligation_id=mortgage["id"], field="balance", value=242_540.09,
                  effective_at=1_785_170_000.0, confidence=.95, source="lender statement",
                  lineage="household supplied", unit_or_currency="GBP")
    receipt = capture.propose(**values)
    first = capture.execute(**values, proposal_id=receipt.proposal_id, command_id="mortgage-evidence")
    second = capture.execute(**values, proposal_id=receipt.proposal_id, command_id="mortgage-evidence")
    assert first == second
    assert MortgageEvidenceProjection(log).latest(mortgage["id"], "balance", values["effective_at"]) \
        .value == 242_540.09


def test_mortgage_rejects_unavailable_or_cross_household_collateral(tmp_path):
    log, _, writes = _world(tmp_path)
    with pytest.raises(McpWriteDenied, match="secured property"):
        writes.create(resource_type="mortgage", currency="GBP", name="Mortgage", owner="Chris",
                      secured_property_id="missing", command_id="bad-property", proposal_id=writes.propose_create(
                          resource_type="mortgage", currency="GBP", name="Mortgage", owner="Chris",
                          secured_property_id="missing").proposal_id)


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


def test_provider_projection_proposal_execute_is_exact_and_idempotent(tmp_path):
    log, household, writes = _world(tmp_path)
    resource = writes.create(resource_type="pension", currency="GBP", name="Aviva", owner="Chris",
                             command_id="pension", proposal_id=writes.propose_create(
                                 resource_type="pension", currency="GBP", name="Aviva", owner="Chris").proposal_id)
    capture = McpPensionProviderProjectionCapture(log, PRINCIPAL, household.id, "claude-code", "gpt-test")
    values = dict(provider="Aviva", currency="GBP", observed_at=1_786_000_000.0, retirement_age=68.0,
                  retirement_at=None, fund_low=380_000.0, fund_medium=604_000.0, fund_high=1_100_000.0,
                  income_low=22_500.0, income_medium=43_800.0, income_high=96_600.0,
                  growth_low_percent=-.8, growth_medium_percent=2.2, growth_high_percent=5.1,
                  income_basis="Provider illustration", source="Aviva statement", lineage="household supplied")
    proposal = capture.propose(resource_id=resource["id"], values=values)
    assert not any(event["kind"] == "finance.pension_provider_projection.recorded" for event in log.events())
    first = capture.execute(resource_id=resource["id"], values=values, proposal_id=proposal.proposal_id,
                            command_id="projection-1")
    second = capture.execute(resource_id=resource["id"], values=values, proposal_id=proposal.proposal_id,
                             command_id="projection-1")
    assert first == second and first["medium_projected_value"] == 604_000.0
    assert sum(event["kind"] == "finance.pension_provider_projection.recorded" for event in log.events()) == 1
    with pytest.raises(McpWriteDenied):
        capture.execute(resource_id=resource["id"], values={**values, "fund_medium": 605_000.0},
                        proposal_id=proposal.proposal_id, command_id="projection-2")


def _projection_values():
    """The exact evidenced Aviva age-67 illustration, as supplied by MyAviva."""
    return dict(provider="Aviva", observed_at=1_787_443_200.0, currency="GBP",
                retirement_age=67.0, retirement_at=None,
                fund_low=590_240.0, fund_medium=660_256.0, fund_high=730_766.0,
                income_low=35_774.0, income_medium=40_661.0, income_high=45_964.0,
                growth_low_percent=1.5, growth_medium_percent=3.5, growth_high_percent=5.5,
                income_basis="annuity", source="MyAviva",
                lineage="MyAviva screenshot 2026-08-23")


def _mcp_pension_world(tmp_path):
    log, household, writes = _world(tmp_path)
    resource = writes.create(resource_type="pension", currency="GBP", name="Aviva", owner="Chris",
                             command_id="pension", proposal_id=writes.propose_create(
                                 resource_type="pension", currency="GBP", name="Aviva",
                                 owner="Chris").proposal_id)
    principal = McpPrincipal(PRINCIPAL, household.id, "claude-code", "gpt-test")
    server = create_mcp_server(FinancialResourceQuery(log, household.id), principal)
    return log, resource, server


def _tool(server, name):
    return server._tool_manager.get_tool(name).fn


def test_provider_projection_proposal_receipt_is_json_serializable(tmp_path):
    """Regression: the MCP wrapper must not leak non-serializable objects into the request."""
    log, resource, server = _mcp_pension_world(tmp_path)
    before = list(log.events())

    receipt = _tool(server, "propose_pension_provider_projection")(
        resource_id=resource["id"], **_projection_values())

    json.dumps(receipt)
    assert receipt["state"] == "proposed" and receipt["requires_execution"] is True
    assert receipt["resource_id"] == resource["id"]
    assert receipt["proposal_id"].startswith("pension-provider-projection-")
    assert "660,256" in receipt["summary"] and "age 67" in receipt["summary"]
    appended = list(log.events())[len(before):]
    assert [event["kind"] for event in appended] == [
        "application.mcp_pension_provider_projection.proposed"]
    assert not any(event["kind"] == "finance.pension_provider_projection.recorded"
                   for event in log.events())


def test_provider_projection_execute_requires_matching_proposal_and_is_idempotent(tmp_path):
    log, resource, server = _mcp_pension_world(tmp_path)
    values = _projection_values()
    propose = _tool(server, "propose_pension_provider_projection")
    execute = _tool(server, "execute_pension_provider_projection")

    receipt = propose(resource_id=resource["id"], **values)

    with pytest.raises(ValueError):
        execute(resource_id=resource["id"], proposal_id="pension-provider-projection-bogus",
                command_id="cmd-1", **values)

    first = execute(resource_id=resource["id"], proposal_id=receipt["proposal_id"],
                    command_id="cmd-1", **values)
    second = execute(resource_id=resource["id"], proposal_id=receipt["proposal_id"],
                     command_id="cmd-1", **values)
    json.dumps(first)
    assert first == second
    assert first["medium_projected_value"] == 660_256.0
    assert first["planning_age"] == 67.0
    assert sum(event["kind"] == "finance.pension_provider_projection.recorded"
               for event in log.events()) == 1

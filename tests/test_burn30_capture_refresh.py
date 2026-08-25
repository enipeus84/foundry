"""Burn 30: capture availability refreshes when its canonical prerequisites change.

Burn 29 proved that recording ``property_role=primary_residence`` made the
property canonically eligible for valuation capture, but the capture registry
only learned that at the next runtime bootstrap.  These tests pin the
deterministic refresh at the mutation boundary.
"""

from __future__ import annotations

from foundry.application.mcp_writes import (
    McpFinancialResourceWrites, McpMortgageEvidenceCapture,
)
from foundry.application.resources import FinancialResourceQuery
from foundry.core.entities import declare_party, join_household, update_party
from foundry.core.principal_authority import grant_principal_household_authority
from foundry.eventlog import EventLog


PRINCIPAL = "mcp@example.com"
NOW = 1_787_616_000.0


def _contracts(log, household, resource_id):
    return {
        operation["contract_id"] for operation in
        FinancialResourceQuery(log, household.id)
        .capture_availability(resource_id)["supported_capture_operations"]
    }


def _streams(log):
    return [event for event in log.events()
            if event["kind"] == "core.telemetry_stream.declared"]


def _world(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    household = declare_party(log, "household")
    christopher = declare_party(log, "person")
    fiona = declare_party(log, "person")
    update_party(log, christopher.id, {"name": "Christopher"}, "test identity")
    update_party(log, fiona.id, {"name": "Fiona"}, "test identity")
    join_household(log, christopher.id, household.id)
    join_household(log, fiona.id, household.id)
    grant_principal_household_authority(log, PRINCIPAL, household.id, actor="test")
    writes = McpFinancialResourceWrites(
        log, PRINCIPAL, household.id, "claude-code", "gpt-test")
    return log, household, writes


def _property(writes):
    return writes.create(
        resource_type="property", currency="GBP", name="Tomcroy House",
        owners=["Christopher", "Fiona"], command_id="property-create",
        proposal_id=writes.propose_create(
            resource_type="property", currency="GBP", name="Tomcroy House",
            owners=["Christopher", "Fiona"]).proposal_id)


def _mortgage(writes, home):
    return writes.create(
        resource_type="mortgage", currency="GBP", name="Home mortgage",
        owners=["Christopher", "Fiona"], secured_property_id=home["id"],
        command_id="mortgage-create",
        proposal_id=writes.propose_create(
            resource_type="mortgage", currency="GBP", name="Home mortgage",
            owners=["Christopher", "Fiona"], secured_property_id=home["id"]).proposal_id)


def _record(capture, obligation_id, field, value, *, command_id,
            unit_or_currency=None):
    values = dict(obligation_id=obligation_id, field=field, value=value,
                  effective_at=NOW - 10 * 86_400.0, confidence=.95,
                  source="National Westminster Bank Plc statement",
                  lineage="household supplied", unit_or_currency=unit_or_currency)
    receipt = capture.propose(**values)
    return capture.execute(**values, proposal_id=receipt.proposal_id,
                           command_id=command_id)


def test_property_alone_has_no_valuation_capture(tmp_path):
    log, household, writes = _world(tmp_path)
    home = _property(writes)

    assert _contracts(log, household, home["id"]) == set()


def test_mortgage_without_property_role_still_has_no_valuation_capture(tmp_path):
    log, household, writes = _world(tmp_path)
    home = _property(writes)
    mortgage = _mortgage(writes, home)
    capture = McpMortgageEvidenceCapture(
        log, PRINCIPAL, household.id, "claude-code", "gpt-test")

    _record(capture, mortgage["id"], "balance", 241_728.15,
            command_id="balance", unit_or_currency="GBP")

    assert _contracts(log, household, home["id"]) == set()


def test_recording_primary_residence_refreshes_capture_immediately(tmp_path):
    log, household, writes = _world(tmp_path)
    home = _property(writes)
    mortgage = _mortgage(writes, home)
    capture = McpMortgageEvidenceCapture(
        log, PRINCIPAL, household.id, "claude-code", "gpt-test")
    assert _contracts(log, household, home["id"]) == set()

    _record(capture, mortgage["id"], "property_role", "primary_residence",
            command_id="property-role")

    # No process restart and no unrelated resource creation.
    assert _contracts(log, household, home["id"]) == {"property-valuation-update"}


def test_refresh_declares_exactly_one_stream_and_is_idempotent(tmp_path):
    log, household, writes = _world(tmp_path)
    home = _property(writes)
    mortgage = _mortgage(writes, home)
    capture = McpMortgageEvidenceCapture(
        log, PRINCIPAL, household.id, "claude-code", "gpt-test")

    _record(capture, mortgage["id"], "property_role", "primary_residence",
            command_id="property-role")
    after_first = _streams(log)
    # A replayed command, and a fresh command carrying the same fact.
    _record(capture, mortgage["id"], "property_role", "primary_residence",
            command_id="property-role")
    _record(capture, mortgage["id"], "property_role", "primary_residence",
            command_id="property-role-again")

    subjects = [event["payload"]["subject_id"] for event in _streams(log)]
    assert subjects.count(home["id"]) == 1
    assert _streams(log) == after_first
    assert _contracts(log, household, home["id"]) == {"property-valuation-update"}


def test_unrelated_evidence_does_not_change_eligibility(tmp_path):
    log, household, writes = _world(tmp_path)
    home = _property(writes)
    mortgage = _mortgage(writes, home)
    capture = McpMortgageEvidenceCapture(
        log, PRINCIPAL, household.id, "claude-code", "gpt-test")
    _record(capture, mortgage["id"], "property_role", "primary_residence",
            command_id="property-role")
    baseline = _streams(log)

    for index, (field, value, unit) in enumerate((
        ("balance", 241_728.15, "GBP"),
        ("lender", "National Westminster Bank Plc", None),
        ("interest_rate", .0433, None),
        ("monthly_payment", 1_701.47, "GBP"),
    )):
        _record(capture, mortgage["id"], field, value,
                command_id=f"unrelated-{index}", unit_or_currency=unit)

    assert _streams(log) == baseline
    assert _contracts(log, household, home["id"]) == {"property-valuation-update"}


def test_refresh_writes_no_canonical_financial_evidence(tmp_path):
    """The refresh hook may declare capture targets and nothing else."""
    log, household, writes = _world(tmp_path)
    home = _property(writes)
    mortgage = _mortgage(writes, home)
    capture = McpMortgageEvidenceCapture(
        log, PRINCIPAL, household.id, "claude-code", "gpt-test")
    before = {event["id"] for event in log.events()}

    _record(capture, mortgage["id"], "property_role", "primary_residence",
            command_id="property-role")

    added = [event for event in log.events() if event["id"] not in before]
    assert {event["kind"] for event in added} <= {
        "application.mcp_mortgage_evidence.proposed",
        "application.mcp_mortgage_evidence.executed",
        "finance.mortgage_evidence.recorded",
        "core.asset_registration.registered",
        "core.telemetry_stream.declared",
    }
    assert not any(event["kind"].startswith("finance.valuation") for event in added)
    assert not any(event["kind"].startswith("core.acquisition") for event in added)

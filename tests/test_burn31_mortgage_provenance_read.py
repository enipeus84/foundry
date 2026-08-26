"""Burn 31: governed read-only provenance for mortgage evidence and Targets.

These reads must prove two things without changing anything: whether the
Burn 29 mortgage evidence exists and resolves for the canonical assessor, and
where a Mission Target's horizon came from.
"""

from __future__ import annotations

import json

import pytest

from foundry.application.mcp_context import McpPrincipal
from foundry.application.mortgage_mission import MortgageMissionQueryError
from foundry.application.mission_serialization import iso
from foundry.application.resources import FinancialResourceQuery
from foundry.core.entities import EntityProjection
from foundry.core.mission_assessment import MissionAssessmentRegistry
from foundry.core.mission_targets import (
    MissionTargetProjection, TargetQuantity,
)
from foundry.finance.mission_targets import FinanceTargetMetricResolver
from foundry.finance.missions import register_finance_mission_definitions
from foundry.finance.mortgage_assessment import DAY
from foundry.finance.mortgage_evidence import record_mortgage_evidence
from foundry.mcp_server import create_mcp_server

from test_burn30_mortgage_freedom_read import (
    BURN29_EVIDENCE, NOW, PRINCIPAL, _assumptions, _burn29_world,
    _declare_mortgage_mission, _service, _tool,
)


AS_OF = "2026-08-25T00:00:00Z"
#: 16 April 2043 — the production horizon Burn 31 must be able to trace.
HORIZON_2043 = 2_312_755_200.0


def _targets(log):
    definitions = MissionAssessmentRegistry()
    register_finance_mission_definitions(definitions)
    return MissionTargetProjection(
        log, EntityProjection(log), definitions, FinanceTargetMetricResolver())


def _declared_at(log, mission) -> float:
    """A Mission Target may never precede its Mission's declaration."""
    return float(log.get(mission.provenance[0])["ts"])


def _as_of_after(log, mission, seconds: float = 60.0) -> str:
    return iso(_declared_at(log, mission) + seconds)


def _declare_target(log, household, mission, *, horizon_at, after=1.0,
                    basis=None, supersedes=None, actor="user"):
    return _targets(log).declare(
        household_id=household.id, subject_id=household.id, mission_id=mission.id,
        metric_id="finance.mortgage_balance",
        destination=TargetQuantity(0.0, "GBP", "currency"),
        destination_direction="lower_is_better", horizon_kind="by_date",
        horizon_at=horizon_at, effective_from=_declared_at(log, mission) + after,
        basis=basis, supersedes=supersedes, actor=actor)


# ------------------------------------------------------------------ evidence

def test_burn29_evidence_is_returned_with_full_attribution(tmp_path):
    log, household, _, mortgage = _burn29_world(tmp_path)

    result = _service(log, household).evidence_history(as_of=AS_OF)

    assert result["obligation_state"] == "resolved"
    assert result["obligation_id"] == mortgage["id"]
    assert result["record_count"] == len(BURN29_EVIDENCE)
    assert {record["field"] for record in result["records"]} == set(BURN29_EVIDENCE)
    for record in result["records"]:
        assert record["value"] == BURN29_EVIDENCE[record["field"]]
        assert record["effective_at"] is not None
        assert record["confidence"] == .95
        assert record["source"] == "National Westminster Bank Plc statement"
        assert record["lineage"] == "household supplied"
        assert record["event_id"]
        assert record["is_current"] is True
    json.dumps(result)


def test_evidence_history_reports_assessor_resolution_of_required_fields(tmp_path):
    log, household, _, _ = _burn29_world(tmp_path)

    resolution = _service(log, household).evidence_history(
        as_of=AS_OF)["required_field_resolution"]

    assert resolution["required_count"] == 12
    assert resolution["resolved_count"] == 12
    assert resolution["missing"] == []
    assert resolution["below_confidence_floor"] == []
    assert resolution["assessor_resolves_all_required"] is True


def test_missing_required_evidence_is_named_exactly(tmp_path):
    partial = {field: value for field, value in BURN29_EVIDENCE.items()
               if field not in {"balance", "interest_rate"}}
    log, household, _, _ = _burn29_world(tmp_path, evidence_fields=partial)

    resolution = _service(log, household).evidence_history(
        as_of=AS_OF)["required_field_resolution"]

    assert resolution["missing"] == ["balance", "interest_rate"]
    assert resolution["resolved_count"] == 10
    assert resolution["assessor_resolves_all_required"] is False


def test_superseded_observations_remain_visible_and_only_one_is_current(tmp_path):
    log, household, _, mortgage = _burn29_world(tmp_path)
    record_mortgage_evidence(
        log, mortgage["id"], "balance", 238_000.0, NOW - 2 * DAY,
        confidence=.95, source="lender portal", lineage="household supplied",
        unit_or_currency="GBP")

    result = _service(log, household).evidence_history(as_of=AS_OF, field="balance")

    assert result["record_count"] == 2
    current = [record for record in result["records"] if record["is_current"]]
    assert len(current) == 1
    assert current[0]["value"] == 238_000.0
    assert result["fields"]["balance"]["observation_count"] == 2


def test_low_confidence_evidence_is_flagged_not_suppressed(tmp_path):
    log, household, _, mortgage = _burn29_world(tmp_path)
    record_mortgage_evidence(
        log, mortgage["id"], "balance", 238_000.0, NOW - 2 * DAY,
        confidence=.2, source="recollection", lineage="household supplied",
        unit_or_currency="GBP")

    result = _service(log, household).evidence_history(as_of=AS_OF)
    resolution = result["required_field_resolution"]

    assert resolution["below_confidence_floor"] == ["balance"]
    assert resolution["assessor_resolves_all_required"] is False
    assert result["fields"]["balance"]["current"]["below_assessor_confidence_floor"] is True


def test_evidence_history_refuses_another_households_obligation(tmp_path):
    log, household, _, _ = _burn29_world(tmp_path)

    result = _service(log, household).evidence_history(
        obligation_id="not-this-households-obligation", as_of=AS_OF)

    assert result["obligation_state"] == "unresolved"
    assert result["reason"] == "obligation is not authorised for this household"
    assert result["records"] == []
    assert result["required_field_resolution"] is None


def test_evidence_history_rejects_unsupported_field(tmp_path):
    log, household, _, _ = _burn29_world(tmp_path)

    with pytest.raises(MortgageMissionQueryError):
        _service(log, household).evidence_history(field="not_a_field")


def test_evidence_history_is_side_effect_free(tmp_path):
    log, household, _, _ = _burn29_world(tmp_path)
    service = _service(log, household)
    first = service.evidence_history(as_of=AS_OF)
    before = list(log.events())

    second = service.evidence_history(as_of=AS_OF)

    assert list(log.events()) == before
    assert first == second


# ------------------------------------------------------------------ targets

def test_target_history_traces_the_horizon_to_its_declaration(tmp_path):
    log, household, _, _ = _burn29_world(tmp_path)
    mission = _declare_mortgage_mission(
        log, household, assumption_set_id=_assumptions(log).id, declare_target=False)
    declared = _declare_target(
        log, household, mission, horizon_at=HORIZON_2043,
        basis="lender redemption illustration", actor="christopher")

    result = _service(log, household).target_history(
        as_of=_as_of_after(log, mission))

    assert result["target_count"] == 1
    entry = result["targets"][0]
    assert entry["id"] == declared.id
    assert entry["state"] == "in_force"
    assert result["in_force_target_id"] == declared.id
    assert entry["target_value"] == 0.0
    assert entry["unit_or_currency"] == "GBP"
    assert entry["metric_id"] == "finance.mortgage_balance"
    assert entry["horizon_kind"] == "by_date"
    assert entry["horizon_at"] == "2043-04-16T00:00:00Z"
    assert entry["basis"] == "lender redemption illustration"
    assert entry["declaration_event_id"] == declared.provenance[0]
    assert entry["declaration"]["actor"] == "christopher"
    assert entry["declaration"]["recorded_at"] is not None
    json.dumps(result)


def test_superseded_targets_stay_visible_with_their_state(tmp_path):
    log, household, _, _ = _burn29_world(tmp_path)
    mission = _declare_mortgage_mission(
        log, household, assumption_set_id=_assumptions(log).id, declare_target=False)
    original = _declare_target(
        log, household, mission, horizon_at=HORIZON_2043 + 365 * DAY,
        after=1.0, basis="original commissioning")
    replacement = _declare_target(
        log, household, mission, horizon_at=HORIZON_2043, after=2.0,
        basis="corrected horizon", supersedes=original.id)

    result = _service(log, household).target_history(
        as_of=_as_of_after(log, mission))

    assert result["target_count"] == 2
    by_id = {entry["id"]: entry for entry in result["targets"]}
    assert by_id[original.id]["state"] == "superseded"
    assert by_id[original.id]["superseded_by"] == [replacement.id]
    assert by_id[replacement.id]["state"] == "in_force"
    assert by_id[replacement.id]["supersedes"] == original.id
    assert result["in_force_target_id"] == replacement.id


def test_target_history_exposes_mission_destination_metadata(tmp_path):
    """The assessor gates on Mission metadata; the read must make it visible."""
    log, household, _, _ = _burn29_world(tmp_path)
    mission = _declare_mortgage_mission(
        log, household, assumption_set_id=_assumptions(log).id, declare_target=False)
    _declare_target(log, household, mission, horizon_at=HORIZON_2043)

    metadata = _service(log, household).target_history(
        as_of=_as_of_after(log, mission))["mission_destination_metadata"]

    assert metadata["target_value"] == 0.0
    assert metadata["target_date"] is not None
    assert metadata["provenance"] == list(mission.provenance)


def test_absent_mission_is_reported_not_manufactured(tmp_path):
    log, household, _, _ = _burn29_world(tmp_path)

    result = _service(log, household).target_history()

    assert result["mission"] is None
    assert result["mission_state"] == "not_declared"
    assert result["targets"] == []
    assert result["in_force_target_id"] is None


def test_target_history_refuses_an_unauthorised_mission(tmp_path):
    log, household, _, _ = _burn29_world(tmp_path)
    _declare_mortgage_mission(log, household, assumption_set_id=_assumptions(log).id)

    with pytest.raises(MortgageMissionQueryError):
        _service(log, household).target_history(mission_id="another-mission")


def test_target_history_is_side_effect_free(tmp_path):
    log, household, _, _ = _burn29_world(tmp_path)
    mission = _declare_mortgage_mission(
        log, household, assumption_set_id=_assumptions(log).id, declare_target=False)
    _declare_target(log, household, mission, horizon_at=HORIZON_2043)
    service = _service(log, household)
    as_of = _as_of_after(log, mission)
    first = service.target_history(as_of=as_of)
    before = list(log.events())

    second = service.target_history(as_of=as_of)

    assert list(log.events()) == before
    assert first == second


# ------------------------------------------------------------------ MCP surface

def test_both_reads_are_registered_and_never_mutate(tmp_path):
    log, household, _, mortgage = _burn29_world(tmp_path)
    mission = _declare_mortgage_mission(
        log, household, assumption_set_id=_assumptions(log).id, declare_target=False)
    _declare_target(log, household, mission, horizon_at=HORIZON_2043)
    server = create_mcp_server(
        FinancialResourceQuery(log, household.id),
        McpPrincipal(PRINCIPAL, household.id, "claude-code", "gpt-test"))
    before = list(log.events())

    evidence = _tool(server, "get_mortgage_evidence_history")(as_of=AS_OF)
    targets = _tool(server, "get_mission_target_history")(
        as_of=_as_of_after(log, mission))

    assert list(log.events()) == before
    assert evidence["obligation_id"] == mortgage["id"]
    assert evidence["record_count"] == len(BURN29_EVIDENCE)
    assert targets["in_force_target_id"] is not None
    json.dumps(evidence)
    json.dumps(targets)

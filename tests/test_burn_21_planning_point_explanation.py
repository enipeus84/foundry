"""Burn 21: governed explanation of Pension Independence planning compatibility."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from itertools import count

import pytest

from foundry.application.pension_mission import PensionMissionQueryService
from foundry.core import grammar
from foundry.core.entities import EntityProjection, declare_party, join_household
from foundry.core.identity import declare_person_date_of_birth
from foundry.core.mission_assessment import MissionAssessmentRegistry
from foundry.core.mission_targets import MissionTargetProjection, TargetQuantity
from foundry.demo_data import build
from foundry.eventlog import EventLog
from foundry.finance import entities as finance
from foundry.finance.mission_targets import FinanceTargetMetricResolver
from foundry.finance.missions import register_finance_mission_definitions
from foundry.finance.pension_assessment import DAY, POLICY_ID
from foundry.finance.pension_projection import record_pension_provider_projection


AS_OF = datetime(2026, 8, 21, 23, tzinfo=timezone.utc).timestamp()


@pytest.fixture(autouse=True)
def deterministic_event_clock(monkeypatch):
    clock = count(AS_OF - 10_000, step=.001)
    monkeypatch.setattr("foundry.eventlog.time.time", clock.__next__)


def _world(tmp_path, *, person_target=False):
    log = EventLog(tmp_path / "events.jsonl")
    household = build(log, as_of=AS_OF)
    core = EntityProjection(log)
    mission = next(item for item in core.missions.values()
                   if item.assessment_policy_id == POLICY_ID)
    grammar.update(log, "core", "mission", mission.id, {"household_id": None},
                   "exercise canonical target binding", actor="test")
    definitions = MissionAssessmentRegistry()
    register_finance_mission_definitions(definitions)
    targets = MissionTargetProjection(log, EntityProjection(log), definitions,
                                      FinanceTargetMetricResolver())
    descriptor = targets.metric_resolver.describe(mission.target_metric)
    targets.declare(
        household_id=household.household_id,
        subject_id=household.alex_id if person_target else household.household_id,
        mission_id=mission.id, metric_id=mission.target_metric,
        destination=TargetQuantity(735_000, descriptor.unit_or_currency, descriptor.dimension),
        destination_direction=descriptor.destination_direction, horizon_kind="derived",
        horizon_at=None, effective_from=AS_OF - 1, actor="test")
    return log, household, mission


def _provider(log, account_id, *, retirement_at=None, retirement_age=None,
              observed_at=AS_OF - DAY):
    return record_pension_provider_projection(
        log, account_id, provider="Aviva", currency="GBP", observed_at=observed_at,
        retirement_at=retirement_at, retirement_age=retirement_age,
        fund_low=300_000, fund_medium=400_000, fund_high=500_000,
        income_low=20_000, income_medium=30_000, income_high=40_000,
        growth_low_percent=1.0, growth_medium_percent=2.0, growth_high_percent=3.0,
        income_basis="Provider illustration", source="Aviva statement",
        lineage="household supplied statement")


def test_explanation_uses_assessor_horizon_and_reports_provider_delta(tmp_path):
    log, household, mission = _world(tmp_path)
    service = PensionMissionQueryService(log, household.household_id)
    baseline = service.explain_planning_point(mission.id, "2026-08-21T23:00:00Z")
    planning_at = baseline["planning_point"]["planning_at"]
    assert baseline["planning_point"]["selection_rule"] == (
        "latest active adult participant State Pension age")
    assert len(baseline["planning_point"]["participants"]) == 2
    assert baseline["planning_point"]["driving_participant_ids"] == [household.sam_id]
    assert all(item["state_pension_age_evidence_reference"]
               for item in baseline["planning_point"]["participants"])

    finance.declare_pension_projection_authority(
        log, household.alex_pension_id, projection_authority="provider_managed", reason="test")
    event = _provider(log, household.alex_pension_id, retirement_age=68)
    result = service.explain_planning_point(mission.id, "2026-08-21T23:00:00Z")

    provider = result["provider_projections"]
    assert result["planning_point"]["planning_at"] == planning_at
    assert provider[0]["latest_provider_projection"]["evidence_reference"] == event.event_id
    assert provider[0]["latest_provider_projection"]["retirement_at"] is None
    assert provider[0]["record_planning_at"] is not None
    assert provider[0]["absolute_delta_seconds"] > DAY
    assert provider[0]["compatibility_result"] is False
    assert result["compatibility"] == {
        "tolerance_seconds": DAY, "tolerance": "P1D",
        "provider_mode_active": True, "result": False}
    assert json.loads(json.dumps(result)) == result
    # The Mission-specific response exposes neither child nor generic resource state.
    rendered = json.dumps(result)
    assert household.emily_id not in rendered
    assert "current_pension_value" not in rendered


def test_explanation_scopes_a_single_adult_participant_to_the_mission_subject(tmp_path):
    log, household, mission = _world(tmp_path, person_target=True)
    result = PensionMissionQueryService(log, household.household_id).explain_planning_point(
        mission.id, "2026-08-21T23:00:00Z")
    assert [item["participant_id"] for item in result["planning_point"]["participants"]] == [
        household.alex_id]
    assert result["planning_point"]["driving_participant_ids"] == [household.alex_id]


@pytest.mark.parametrize("offset, compatible", [(DAY, True), (DAY + 1, False)])
def test_explanation_preserves_one_day_provider_compatibility_boundary(
        tmp_path, offset, compatible):
    log, household, mission = _world(tmp_path)
    service = PensionMissionQueryService(log, household.household_id)
    baseline = service.explain_planning_point(mission.id, "2026-08-21T23:00:00Z")
    planning_at = datetime.fromisoformat(
        baseline["planning_point"]["planning_at"].replace("Z", "+00:00")).timestamp()
    finance.declare_pension_projection_authority(
        log, household.alex_pension_id, projection_authority="provider_managed", reason="test")
    finance.declare_pension_projection_authority(
        log, household.sam_pension_id, projection_authority="provider_managed", reason="test")
    _provider(log, household.alex_pension_id, retirement_at=planning_at - offset)
    _provider(log, household.sam_pension_id, retirement_at=planning_at)

    result = service.explain_planning_point(mission.id, "2026-08-21T23:00:00Z")
    assert result["provider_projections"][0]["absolute_delta_seconds"] == offset
    assert result["provider_projections"][0]["compatibility_result"] is compatible
    assert result["compatibility"]["result"] is compatible
    # The actual assessor remains the authority for the same fail-closed result.
    assert (result["assessment"]["status"] != "unavailable") is compatible


def test_explanation_includes_observed_provider_evidence_without_provider_authority(tmp_path):
    log, household, mission = _world(tmp_path)
    service = PensionMissionQueryService(log, household.household_id)
    baseline = service.explain_planning_point(mission.id, "2026-08-21T23:00:00Z")
    planning_at = datetime.fromisoformat(
        baseline["planning_point"]["planning_at"].replace("Z", "+00:00")).timestamp()
    incompatible = _provider(
        log, household.alex_pension_id, retirement_at=planning_at - DAY - 1)
    _provider(log, household.sam_pension_id, retirement_at=planning_at)

    result = service.explain_planning_point(mission.id, "2026-08-21T23:00:00Z")

    by_resource = {item["resource_id"]: item for item in result["provider_projections"]}
    alex = by_resource[household.alex_pension_id]
    assert alex["projection_authority"] is None
    assert alex["provider_projection_required"] is False
    assert alex["latest_provider_projection"]["evidence_reference"] == incompatible.event_id
    assert alex["compatibility_result"] is False
    assert alex["resolution_error"] is None
    assert result["compatibility"]["provider_mode_active"] is True
    assert result["compatibility"]["result"] is False
    assert result["assessment"]["status"] == "unavailable"
    assert "planning point is incompatible" in result["assessment"]["blocker"]


def test_explanation_separates_date_compatibility_from_stale_record_usability(tmp_path):
    log, household, mission = _world(tmp_path)
    service = PensionMissionQueryService(log, household.household_id)
    baseline = service.explain_planning_point(mission.id, "2026-08-21T23:00:00Z")
    planning_at = datetime.fromisoformat(
        baseline["planning_point"]["planning_at"].replace("Z", "+00:00")).timestamp()
    finance.declare_pension_projection_authority(
        log, household.alex_pension_id, projection_authority="provider_managed", reason="test")
    finance.declare_pension_projection_authority(
        log, household.sam_pension_id, projection_authority="provider_managed", reason="test")
    stale_at = AS_OF - 551 * DAY
    _provider(log, household.alex_pension_id, retirement_at=planning_at, observed_at=stale_at)
    _provider(log, household.sam_pension_id, retirement_at=planning_at, observed_at=stale_at)

    result = service.explain_planning_point(mission.id, "2026-08-21T23:00:00Z")

    assert result["compatibility"]["result"] is True
    assert all(item["record_stale"] is True for item in result["provider_projections"])
    assert all(item["record_freshness_result"] is False
               for item in result["provider_projections"])
    assert result["assessment"]["status"] == "unavailable"
    assert "current provider projection required" in result["assessment"]["blocker"]


def test_explanation_fails_closed_when_participant_state_pension_evidence_is_missing(tmp_path):
    log, household, mission = _world(tmp_path)
    unknown = declare_party(log, "person")
    join_household(log, unknown.id, household.household_id)
    declare_person_date_of_birth(log, unknown.id, "1980-01-01", actor="test")
    result = PensionMissionQueryService(log, household.household_id).explain_planning_point(
        mission.id, "2026-08-21T23:00:00Z")
    assert result["planning_point"]["planning_at"] is None
    assert unknown.id in result["planning_point"]["calculation_error"]
    assert result["provider_projections"] == []
    assert result["compatibility"]["result"] is None

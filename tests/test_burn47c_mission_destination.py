from __future__ import annotations

import pytest

from foundry.application.mission_destination import (
    MissionDestinationDenied, MissionDestinationService,
)
from foundry.core import grammar
from foundry.core.entities import (
    EntityProjection, abandon_mission, achieve_mission, declare_mission, declare_party,
)
from foundry.core.mission_assessment import MissionAssessmentRegistry
from foundry.core.mission_targets import MissionTargetProjection, TargetQuantity
from foundry.core.principal_authority import grant_principal_household_authority
from foundry.eventlog import EventLog
from foundry.finance.mission_targets import FinanceTargetMetricResolver
from foundry.finance.missions import register_finance_mission_definitions
from foundry.finance.resilience_assessment import POLICY_ID as RESILIENCE_POLICY_ID


PRINCIPAL = "operator@example.com"
M1 = "finance.liquidity_runway"
M2 = "finance.mortgage_payment_runway"


def _targets(log: EventLog) -> MissionTargetProjection:
    definitions = MissionAssessmentRegistry()
    register_finance_mission_definitions(definitions)
    return MissionTargetProjection(log, EntityProjection(log), definitions, FinanceTargetMetricResolver())


def _world(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    household = declare_party(log, "household")
    mission = declare_mission(log, "Financial Resilience", target_metric=M1,
                              assessment_policy_id=RESILIENCE_POLICY_ID,
                              household_id=household.id)
    grant_principal_household_authority(log, PRINCIPAL, household.id, actor="test")
    return log, household, mission, MissionDestinationService(log, PRINCIPAL, household.id)


def _propose(service: MissionDestinationService, mission_id: str, metric: str = M2,
             reason: str = "household approved revised measurement"):
    return service.propose_mission_target_metric(
        mission_id=mission_id, target_metric=metric, reason=reason)


def _declare_target(log: EventLog, household_id: str, mission_id: str):
    projection = _targets(log)
    mission = EntityProjection(log).missions[mission_id]
    declaration = log.get(mission.provenance[0])
    assert declaration is not None
    return projection.declare(
        household_id=household_id, subject_id=household_id, mission_id=mission_id,
        metric_id=M1, destination=TargetQuantity(30.0, "months", "duration_months"),
        destination_direction="higher_is_better", horizon_kind="none", horizon_at=None,
        effective_from=declaration["ts"], basis="original runway destination")


def _close_mission(log: EventLog, mission_id: str, reason: str):
    return grammar.close(log, "core", "mission", mission_id, reason)


def test_authorised_proposal_executes_exact_canonical_metric_update(tmp_path):
    log, household, mission, service = _world(tmp_path)
    proposal = _propose(service, mission.id)
    result = service.execute_mission_target_metric(
        mission_id=mission.id, target_metric=M2,
        reason="household approved revised measurement", proposal_id=proposal["proposal_id"],
        command_id="metric-change-1")

    updates = [event for event in log.events() if event["kind"] == "core.mission.updated"]
    assert result["previous_target_metric"] == M1 and result["target_metric"] == M2
    assert EntityProjection(log).missions[mission.id].target_metric == M2
    assert len(updates) == 1
    assert updates[0]["payload"] == {
        "entity_id": mission.id, "reason": "household approved revised measurement",
        "target_metric": M2,
    }
    assert result["provenance"] == [updates[0]["id"]]


def test_in_force_target_blocks_proposal_and_stale_execution(tmp_path):
    log, household, mission, service = _world(tmp_path)
    target = _declare_target(log, household.id, mission.id)
    with pytest.raises(MissionDestinationDenied, match="currently in force"):
        _propose(service, mission.id)

    _targets(log).withdraw(household_id=household.id, target_id=target.id, reason="withdrawn first")
    proposal = _propose(service, mission.id)
    _declare_target(log, household.id, mission.id)
    with pytest.raises(MissionDestinationDenied, match="currently in force"):
        service.execute_mission_target_metric(
            mission_id=mission.id, target_metric=M2,
            reason="household approved revised measurement", proposal_id=proposal["proposal_id"],
            command_id="blocked-after-proposal")


def test_execution_refuses_proposal_stale_against_mission_history(tmp_path):
    log, _, mission, service = _world(tmp_path)
    proposal = _propose(service, mission.id)
    grammar.update(log, "core", "mission", mission.id, {"target_value": 42.0},
                   reason="unrelated mission refinement")
    with pytest.raises(MissionDestinationDenied, match="stale"):
        service.execute_mission_target_metric(
            mission_id=mission.id, target_metric=M2,
            reason="household approved revised measurement", proposal_id=proposal["proposal_id"],
            command_id="stale-command")


@pytest.mark.parametrize("metric", ["finance.unknown", ""])
def test_unknown_metrics_are_refused(tmp_path, metric):
    _, _, mission, service = _world(tmp_path)
    with pytest.raises(MissionDestinationDenied):
        _propose(service, mission.id, metric=metric)


def test_descriptor_direction_incompatibility_is_refused(tmp_path):
    _, _, mission, service = _world(tmp_path)
    with pytest.raises(MissionDestinationDenied, match="direction"):
        _propose(service, mission.id, metric="finance.mortgage_balance")


def test_cross_household_mutation_is_refused(tmp_path):
    log, _, mission, _ = _world(tmp_path)
    other = declare_party(log, "household")
    grant_principal_household_authority(log, PRINCIPAL, other.id, actor="test")
    service = MissionDestinationService(log, PRINCIPAL, other.id)
    with pytest.raises(MissionDestinationDenied, match="not authorised"):
        _propose(service, mission.id)


@pytest.mark.parametrize("close", [achieve_mission, abandon_mission, _close_mission])
def test_non_active_missions_are_refused(tmp_path, close):
    log, _, mission, service = _world(tmp_path)
    close(log, mission.id, reason="terminal")
    with pytest.raises(MissionDestinationDenied, match="not active"):
        _propose(service, mission.id)


def test_noop_and_empty_reason_are_refused(tmp_path):
    _, _, mission, service = _world(tmp_path)
    with pytest.raises(MissionDestinationDenied, match="already current"):
        _propose(service, mission.id, metric=M1)
    with pytest.raises(MissionDestinationDenied, match="reason"):
        _propose(service, mission.id, reason=" ")


def test_execution_is_idempotent_and_command_digest_bound(tmp_path):
    log, _, mission, service = _world(tmp_path)
    proposal = _propose(service, mission.id)
    first = service.execute_mission_target_metric(
        mission_id=mission.id, target_metric=M2,
        reason="household approved revised measurement", proposal_id=proposal["proposal_id"],
        command_id="replayable-command")
    assert service.execute_mission_target_metric(
        mission_id=mission.id, target_metric=M2,
        reason="household approved revised measurement", proposal_id=proposal["proposal_id"],
        command_id="replayable-command") == first

    reverse = _propose(service, mission.id, metric=M1, reason="reverse measurement")
    with pytest.raises(MissionDestinationDenied, match="different operation"):
        service.execute_mission_target_metric(
            mission_id=mission.id, target_metric=M1, reason="reverse measurement",
            proposal_id=reverse["proposal_id"], command_id="replayable-command")


def test_withdrawn_historical_target_remains_readable_after_metric_change(tmp_path):
    log, household, mission, service = _world(tmp_path)
    target = _declare_target(log, household.id, mission.id)
    _targets(log).withdraw(household_id=household.id, target_id=target.id, reason="metric change")
    proposal = _propose(service, mission.id)
    service.execute_mission_target_metric(
        mission_id=mission.id, target_metric=M2,
        reason="household approved revised measurement", proposal_id=proposal["proposal_id"],
        command_id="preserve-history")

    replay = _targets(log)
    assert replay.targets[target.id].metric_id == M1
    assert replay.targets[target.id].destination == TargetQuantity(30.0, "months", "duration_months")
    assert replay.targets[target.id].provenance == target.provenance

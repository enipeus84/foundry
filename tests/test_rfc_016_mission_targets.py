from __future__ import annotations

from pathlib import Path

import pytest

from foundry.core.entities import EntityProjection, declare_mission, declare_party
from foundry.core.mission_assessment import MissionAssessmentRegistry, MissionDefinition
from foundry.core.mission_targets import (
    MetricDescriptor, MissionTargetError, MissionTargetProjection, TargetQuantity,
)
from foundry.eventlog import EventLog
from foundry.finance.mission_targets import FinanceTargetMetricResolver


class Resolver:
    def __init__(self, descriptor: MetricDescriptor | None):
        self.descriptor = descriptor

    def describe(self, metric_id: str):
        return self.descriptor if self.descriptor and self.descriptor.metric_id == metric_id else None


def _projection(tmp_path: Path):
    log = EventLog(tmp_path / "events.jsonl")
    household = declare_party(log, "household")
    mission = declare_mission(log, "Test", target_metric="example.metric", assessment_policy_id="example.policy")
    entities = EntityProjection(log)
    definitions = MissionAssessmentRegistry()
    definitions.register_definition(MissionDefinition("test", "Test", 1, "higher_is_better", assessment_policy_id="example.policy"))
    target_projection = MissionTargetProjection(
        log, entities, definitions, Resolver(MetricDescriptor("example.metric", "currency", "GBP", "higher_is_better")))
    return log, household, mission, target_projection


def _declare(projection, household_id, mission_id, *, effective_from, supersedes=None):
    return projection.declare(
        household_id=household_id, mission_id=mission_id, metric_id="example.metric",
        destination=TargetQuantity(100.0, "GBP", "currency"),
        destination_direction="higher_is_better", horizon_kind="none", horizon_at=None,
        effective_from=effective_from, supersedes=supersedes,
    )


def test_mission_target_replay_supersession_and_as_of_are_deterministic(tmp_path):
    log, household, mission, projection = _projection(tmp_path)
    declared_at = log.get(mission.provenance[0])["ts"]
    first = _declare(projection, household.id, mission.id, effective_from=declared_at + 10)
    second = _declare(projection, household.id, mission.id, effective_from=declared_at + 20, supersedes=first.id)

    replay = MissionTargetProjection(log, projection.entities, projection.definitions, projection.metric_resolver)
    assert projection.in_force(mission.id, declared_at + 15).id == first.id
    assert projection.in_force(mission.id, declared_at + 25).id == second.id
    assert replay.in_force(mission.id, declared_at + 15).id == first.id
    assert replay.in_force(mission.id, declared_at + 25).id == second.id


def test_withdrawal_is_generic_closure_and_stops_current_resolution(tmp_path):
    log, household, mission, projection = _projection(tmp_path)
    declared_at = log.get(mission.provenance[0])["ts"]
    target = _declare(projection, household.id, mission.id, effective_from=declared_at + 1)
    projection.withdraw(household_id=household.id, target_id=target.id, reason="changed mind")
    event = list(log.events())[-1]
    assert event["kind"] == "core.mission_target.closed"
    assert "status" not in event["payload"]
    assert projection.in_force(mission.id, event["ts"] + 1) is None


def test_prohibited_updated_event_refuses_target(tmp_path):
    log, household, mission, projection = _projection(tmp_path)
    declared_at = log.get(mission.provenance[0])["ts"]
    target = _declare(projection, household.id, mission.id, effective_from=declared_at + 1)
    log.append("core.mission_target.updated", {"entity_id": target.id, "reason": "forbidden"})
    replay = MissionTargetProjection(log, projection.entities, projection.definitions, projection.metric_resolver)
    assert mission.id in replay.conflicts
    assert replay.in_force(mission.id, declared_at + 2) is None


def test_target_declaration_fails_closed_for_unknown_metric_and_wrong_unit(tmp_path):
    log, household, mission, projection = _projection(tmp_path)
    declared_at = log.get(mission.provenance[0])["ts"]
    with pytest.raises(MissionTargetError):
        projection.declare(household_id=household.id, mission_id=mission.id, metric_id="unknown",
                           destination=TargetQuantity(1, "GBP", "currency"), destination_direction="higher_is_better",
                           horizon_kind="none", horizon_at=None, effective_from=declared_at + 1)
    with pytest.raises(MissionTargetError):
        projection.declare(household_id=household.id, mission_id=mission.id, metric_id="example.metric",
                           destination=TargetQuantity(1, "USD", "currency"), destination_direction="higher_is_better",
                           horizon_kind="none", horizon_at=None, effective_from=declared_at + 1)
    assert not [event for event in log.events() if event["kind"].startswith("core.mission_target.")]


def test_finance_descriptor_seam_is_closed_and_core_is_neutral():
    resolver = FinanceTargetMetricResolver()
    assert resolver.describe("finance.liquidity_runway") == MetricDescriptor(
        "finance.liquidity_runway", "duration_months", "months", "higher_is_better")
    core_source = Path("src/foundry/core/mission_targets.py").read_text()
    assert "foundry.finance" not in core_source

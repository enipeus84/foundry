from __future__ import annotations

from itertools import count
from pathlib import Path

import pytest

from foundry.core import grammar
from foundry.core.entities import EntityProjection, declare_mission, declare_party, join_household
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


class MetricTimelineResolver:
    def describe(self, metric_id: str):
        if metric_id in {"example.metric.m1", "example.metric.m2"}:
            return MetricDescriptor(metric_id, "currency", "GBP", "higher_is_better")
        return None


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
        household_id=household_id, subject_id=household_id, mission_id=mission_id, metric_id="example.metric",
        destination=TargetQuantity(100.0, "GBP", "currency"),
        destination_direction="higher_is_better", horizon_kind="none", horizon_at=None,
        effective_from=effective_from, supersedes=supersedes,
    )


def _payload(log, target_id):
    return next(event["payload"] for event in log.events()
                if event["kind"] == "core.mission_target.declared" and event["payload"]["entity_id"] == target_id).copy()


def _metric_timeline_projection(log: EventLog) -> MissionTargetProjection:
    definitions = MissionAssessmentRegistry()
    definitions.register_definition(MissionDefinition(
        "timeline", "Timeline", 1, "higher_is_better", assessment_policy_id="timeline.policy"))
    return MissionTargetProjection(log, EntityProjection(log), definitions, MetricTimelineResolver())


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


def test_replay_preserves_target_history_across_mission_metric_changes(tmp_path, monkeypatch):
    monkeypatch.setattr("foundry.eventlog.time.time", count(1_000.0, 10.0).__next__)
    log = EventLog(tmp_path / "events.jsonl")
    household = declare_party(log, "household")
    mission = declare_mission(log, "Metric timeline", target_metric="example.metric.m1",
                              assessment_policy_id="timeline.policy")
    projection = _metric_timeline_projection(log)
    mission_declaration = log.get(mission.provenance[0])
    assert mission_declaration is not None

    first = projection.declare(
        household_id=household.id, subject_id=household.id, mission_id=mission.id,
        metric_id="example.metric.m1", destination=TargetQuantity(100.0, "GBP", "currency"),
        destination_direction="higher_is_better", horizon_kind="none", horizon_at=None,
        effective_from=mission_declaration["ts"], basis="original M1 destination",
    )
    first_declaration = log.get(first.provenance[0])
    assert first_declaration is not None
    projection.withdraw(household_id=household.id, target_id=first.id, reason="metric revision")
    withdrawal = list(log.events())[-1]
    metric_change = grammar.update(
        log, "core", "mission", mission.id, {"target_metric": "example.metric.m2"},
        reason="mission metric changed",
    )
    projection.entities.rebuild()

    with pytest.raises(MissionTargetError, match="metric does not match"):
        projection.declare(
            household_id=household.id, subject_id=household.id, mission_id=mission.id,
            metric_id="example.metric.m1", destination=TargetQuantity(100.0, "GBP", "currency"),
            destination_direction="higher_is_better", horizon_kind="none", horizon_at=None,
            effective_from=metric_change["ts"],
        )
    second = projection.declare(
        household_id=household.id, subject_id=household.id, mission_id=mission.id,
        metric_id="example.metric.m2", destination=TargetQuantity(200.0, "GBP", "currency"),
        destination_direction="higher_is_better", horizon_kind="none", horizon_at=None,
        effective_from=metric_change["ts"] + 10.0, basis="replacement M2 destination",
    )

    replay = _metric_timeline_projection(log)
    historical = replay.targets[first.id]
    assert historical.metric_id == "example.metric.m1"
    assert historical.destination == TargetQuantity(100.0, "GBP", "currency")
    assert historical.provenance == (first_declaration["id"],)
    assert f"invalid:{first.id}" not in replay.conflicts
    assert replay.in_force(mission.id, withdrawal["ts"] - 1.0).id == first.id
    assert replay.in_force(mission.id, withdrawal["ts"]) is None
    assert replay.in_force(mission.id, metric_change["ts"] + 1.0) is None
    assert replay.in_force(mission.id, metric_change["ts"] + 10.0).id == second.id


def test_replay_rejects_target_inconsistent_with_metric_at_its_declaration(tmp_path, monkeypatch):
    monkeypatch.setattr("foundry.eventlog.time.time", count(1_000.0, 10.0).__next__)
    log = EventLog(tmp_path / "events.jsonl")
    household = declare_party(log, "household")
    mission = declare_mission(log, "Metric timeline", target_metric="example.metric.m1",
                              assessment_policy_id="timeline.policy")
    mission_declaration = log.get(mission.provenance[0])
    assert mission_declaration is not None
    target_id = "inconsistent-at-declaration"
    log.append("core.mission_target.declared", {
        "entity_id": target_id, "mission_id": mission.id, "household_id": household.id,
        "subject_id": household.id, "metric_id": "example.metric.m2",
        "destination_value": 100.0, "destination_unit": "GBP", "destination_dimension": "currency",
        "destination_direction": "higher_is_better", "horizon_kind": "none",
        "effective_from": mission_declaration["ts"],
    })
    grammar.update(log, "core", "mission", mission.id, {"target_metric": "example.metric.m2"},
                   reason="later metric change")

    replay = _metric_timeline_projection(log)
    assert target_id not in replay.targets
    assert replay.conflicts[f"invalid:{target_id}"] == (target_id,)
    assert replay.in_force(mission.id, 9_999.0) is None


def test_prohibited_updated_event_refuses_target(tmp_path):
    log, household, mission, projection = _projection(tmp_path)
    declared_at = log.get(mission.provenance[0])["ts"]
    target = _declare(projection, household.id, mission.id, effective_from=declared_at + 1)
    log.append("core.mission_target.updated", {"entity_id": target.id, "reason": "forbidden"})
    replay = MissionTargetProjection(log, projection.entities, projection.definitions, projection.metric_resolver)
    assert mission.id in replay.conflicts
    assert replay.in_force(mission.id, declared_at + 2) is None


@pytest.mark.parametrize("kind", ["updated", "closed", "hostile"])
def test_invalid_lifecycle_before_declaration_permanently_poisoned(tmp_path, kind):
    log, household, mission, projection = _projection(tmp_path)
    declared_at = log.get(mission.provenance[0])["ts"]
    target_id = "hostile-target"
    log.append(f"core.mission_target.{kind}", {"entity_id": target_id, "reason": "hostile"})
    payload = {
        "entity_id": target_id, "mission_id": mission.id, "household_id": household.id,
        "metric_id": "example.metric", "destination_value": 100, "destination_unit": "GBP",
        "destination_dimension": "currency", "destination_direction": "higher_is_better",
        "horizon_kind": "none", "effective_from": declared_at + 1,
    }
    log.append("core.mission_target.declared", payload)
    replay = MissionTargetProjection(log, projection.entities, projection.definitions, projection.metric_resolver)
    assert mission.id in replay.conflicts
    assert replay.in_force(mission.id, declared_at + 2) is None


def test_target_declaration_fails_closed_for_unknown_metric_and_wrong_unit(tmp_path):
    log, household, mission, projection = _projection(tmp_path)
    declared_at = log.get(mission.provenance[0])["ts"]
    with pytest.raises(MissionTargetError):
        projection.declare(household_id=household.id, subject_id=household.id, mission_id=mission.id, metric_id="unknown",
                           destination=TargetQuantity(1, "GBP", "currency"), destination_direction="higher_is_better",
                           horizon_kind="none", horizon_at=None, effective_from=declared_at + 1)
    with pytest.raises(MissionTargetError):
        projection.declare(household_id=household.id, subject_id=household.id, mission_id=mission.id, metric_id="example.metric",
                           destination=TargetQuantity(1, "USD", "currency"), destination_direction="higher_is_better",
                           horizon_kind="none", horizon_at=None, effective_from=declared_at + 1)
    assert not [event for event in log.events() if event["kind"].startswith("core.mission_target.")]


def test_basis_is_optional_and_limited_to_500_unicode_characters(tmp_path):
    log, household, mission, projection = _projection(tmp_path)
    declared_at = log.get(mission.provenance[0])["ts"]
    projection.declare(household_id=household.id, subject_id=household.id, mission_id=mission.id, metric_id="example.metric",
                       destination=TargetQuantity(1, "GBP", "currency"), destination_direction="higher_is_better",
                       horizon_kind="none", horizon_at=None, effective_from=declared_at + 1, basis="£" * 500)
    with pytest.raises(MissionTargetError):
        projection.declare(household_id=household.id, subject_id=household.id, mission_id=mission.id, metric_id="example.metric",
                           destination=TargetQuantity(1, "GBP", "currency"), destination_direction="higher_is_better",
                           horizon_kind="none", horizon_at=None, effective_from=declared_at + 2, basis="£" * 501)


def test_duplicate_active_targets_are_conflicts_and_never_resolve(tmp_path):
    log, household, mission, projection = _projection(tmp_path)
    declared_at = log.get(mission.provenance[0])["ts"]
    first = _declare(projection, household.id, mission.id, effective_from=declared_at + 1)
    duplicate = _payload(log, first.id)
    duplicate["entity_id"] = "duplicate-target"
    log.append("core.mission_target.declared", duplicate)
    replay = MissionTargetProjection(log, projection.entities, projection.definitions, projection.metric_resolver)
    assert mission.id in replay.conflicts
    assert replay.in_force(mission.id, declared_at + 2) is None


def test_cross_household_and_invalid_supersession_chains_are_conflicts(tmp_path):
    log, household, mission, projection = _projection(tmp_path)
    other_household = declare_party(log, "household")
    projection.entities.rebuild()
    declared_at = log.get(mission.provenance[0])["ts"]
    first = _declare(projection, household.id, mission.id, effective_from=declared_at + 1)
    successor = _payload(log, first.id)
    successor.update(entity_id="cross-household", household_id=other_household.id,
                     subject_id=other_household.id, supersedes=first.id,
                     effective_from=declared_at + 2)
    log.append("core.mission_target.declared", successor)
    replay = MissionTargetProjection(log, projection.entities, projection.definitions, projection.metric_resolver)
    assert mission.id in replay.conflicts
    assert replay.in_force(mission.id, declared_at + 3) is None


def test_t1_e_rejects_double_cross_mission_and_cyclic_supersession(tmp_path):
    log, household, mission, projection = _projection(tmp_path)
    declared_at = log.get(mission.provenance[0])["ts"]
    first = _declare(projection, household.id, mission.id, effective_from=declared_at + 1)
    template = _payload(log, first.id)
    for target_id in ("double-one", "double-two"):
        payload = {**template, "entity_id": target_id, "supersedes": first.id,
                   "effective_from": declared_at + 2}
        log.append("core.mission_target.declared", payload)
    replay = MissionTargetProjection(log, projection.entities, projection.definitions, projection.metric_resolver)
    assert mission.id in replay.conflicts

    cycle_log, cycle_household, cycle_mission, cycle_projection = _projection(tmp_path / "cycle")
    cycle_at = cycle_log.get(cycle_mission.provenance[0])["ts"]
    payload = {
        "mission_id": cycle_mission.id, "household_id": cycle_household.id,
        "metric_id": "example.metric", "destination_value": 100, "destination_unit": "GBP",
        "destination_dimension": "currency", "destination_direction": "higher_is_better",
        "horizon_kind": "none", "effective_from": cycle_at + 1,
    }
    cycle_log.append("core.mission_target.declared", {**payload, "entity_id": "cycle-a", "supersedes": "cycle-b"})
    cycle_log.append("core.mission_target.declared", {**payload, "entity_id": "cycle-b", "supersedes": "cycle-a"})
    cycle_replay = MissionTargetProjection(cycle_log, cycle_projection.entities,
                                           cycle_projection.definitions, cycle_projection.metric_resolver)
    assert cycle_mission.id in cycle_replay.conflicts

    other = declare_mission(log, "Other", target_metric="example.metric", assessment_policy_id="other.policy")
    projection.entities.rebuild()
    projection.definitions.register_definition(MissionDefinition(
        "other", "Other", 2, "higher_is_better", assessment_policy_id="other.policy"))
    cross = {**template, "entity_id": "cross-mission", "mission_id": other.id,
             "supersedes": first.id, "effective_from": declared_at + 2}
    log.append("core.mission_target.declared", cross)
    cross_replay = MissionTargetProjection(log, projection.entities, projection.definitions, projection.metric_resolver)
    assert other.id in cross_replay.conflicts


def test_finance_descriptor_seam_is_closed_and_core_is_neutral():
    resolver = FinanceTargetMetricResolver()
    assert resolver.describe("finance.liquidity_runway") == MetricDescriptor(
        "finance.liquidity_runway", "duration_months", "months", "higher_is_better")
    core_source = (Path(__file__).resolve().parents[1] / "src/foundry/core/mission_targets.py").read_text()
    assert "foundry.finance" not in core_source


def test_new_target_subject_must_be_household_or_active_member(tmp_path):
    log, household, mission, projection = _projection(tmp_path)
    member = declare_party(log, "person")
    join_household(log, member.id, household.id)
    projection.entities.rebuild()
    declared_at = log.get(mission.provenance[0])["ts"]

    target = projection.declare(
        household_id=household.id, subject_id=member.id, mission_id=mission.id,
        metric_id="example.metric", destination=TargetQuantity(100, "GBP", "currency"),
        destination_direction="higher_is_better", horizon_kind="none", horizon_at=None,
        effective_from=declared_at + 1,
    )

    assert target.subject_id == member.id
    assert _payload(log, target.id)["subject_id"] == member.id


def test_new_target_rejects_missing_or_outside_subject_and_legacy_replays_none(tmp_path):
    log, household, mission, projection = _projection(tmp_path)
    other_household = declare_party(log, "household")
    outsider = declare_party(log, "person")
    join_household(log, outsider.id, other_household.id)
    projection.entities.rebuild()
    declared_at = log.get(mission.provenance[0])["ts"]
    kwargs = dict(
        household_id=household.id, mission_id=mission.id, metric_id="example.metric",
        destination=TargetQuantity(100, "GBP", "currency"),
        destination_direction="higher_is_better", horizon_kind="none", horizon_at=None,
        effective_from=declared_at + 1,
    )
    with pytest.raises(MissionTargetError):
        projection.declare(**kwargs)
    with pytest.raises(MissionTargetError):
        projection.declare(subject_id=outsider.id, **kwargs)

    legacy_id = "legacy-target"
    log.append("core.mission_target.declared", {
        "entity_id": legacy_id, "mission_id": mission.id, "household_id": household.id,
        "metric_id": "example.metric", "destination_value": 100, "destination_unit": "GBP",
        "destination_dimension": "currency", "destination_direction": "higher_is_better",
        "horizon_kind": "none", "effective_from": declared_at + 2,
    })
    replay = MissionTargetProjection(log, projection.entities, projection.definitions, projection.metric_resolver)
    assert replay.targets[legacy_id].subject_id is None
    assert replay.targets[legacy_id].subject_id != household.id

"""Frozen replay matrix for DEBT-016-P3-01 Mission Target dormancy."""

from __future__ import annotations

from itertools import count
from pathlib import Path

from foundry.core import grammar
from foundry.core.entities import EntityProjection, declare_party
from foundry.core.mission_assessment import MissionAssessmentRegistry, MissionDefinition
from foundry.core.mission_targets import (
    MetricDescriptor, MissionTargetProjection, TargetQuantity,
)
from foundry.eventlog import EventLog


class Resolver:
    def describe(self, metric_id: str):
        if metric_id == "example.metric":
            return MetricDescriptor(metric_id, "currency", "GBP", "higher_is_better")
        return None


def _declare_mission(log: EventLog, mission_id: str) -> dict:
    return grammar.declare(log, "core", "mission", mission_id, {
        "name": mission_id,
        "target_metric": "example.metric",
        "target_value": None,
        "target_range": None,
        "target_date": None,
        "tolerance": None,
        "assessment_policy_id": "example.policy",
        "assumption_set_id": None,
    })


def _projection(log: EventLog) -> MissionTargetProjection:
    definitions = MissionAssessmentRegistry()
    definitions.register_definition(MissionDefinition(
        "example", "Example", 1, "higher_is_better",
        assessment_policy_id="example.policy",
    ))
    return MissionTargetProjection(log, EntityProjection(log), definitions, Resolver())


def _world(tmp_path: Path, monkeypatch, *mission_ids: str):
    monkeypatch.setattr("foundry.eventlog.time.time", count(1_000.0, 10.0).__next__)
    log = EventLog(tmp_path / "events.jsonl")
    household = declare_party(log, "household")
    declarations = {mission_id: _declare_mission(log, mission_id) for mission_id in mission_ids}
    return log, household, declarations, _projection(log)


def _declare_target(projection: MissionTargetProjection, household_id: str,
                    mission_id: str, effective_from: float, *, supersedes: str | None = None):
    return projection.declare(
        household_id=household_id,
        subject_id=household_id,
        mission_id=mission_id,
        metric_id="example.metric",
        destination=TargetQuantity(100.0, "GBP", "currency"),
        destination_direction="higher_is_better",
        horizon_kind="none",
        horizon_at=None,
        effective_from=effective_from,
        supersedes=supersedes,
    )


def _close(log: EventLog, mission_id: str, *, status: str = "on_track") -> dict:
    return log.append("core.mission.closed", {
        "entity_id": mission_id,
        "reason": "terminal canonical history",
        "status": status,
    })


def test_active_target_and_historical_queries_survive_complete_closure_replay(tmp_path, monkeypatch):
    log, household, declarations, projection = _world(tmp_path, monkeypatch, "mission-a")
    declared_at = declarations["mission-a"]["ts"]
    target = _declare_target(projection, household.id, "mission-a", declared_at + 1)
    assert projection.in_force("mission-a", declared_at + 2).id == target.id

    closure = _close(log, "mission-a")
    replay = _projection(log)
    assert replay.in_force("mission-a", closure["ts"] - 1).id == target.id
    assert replay.in_force("mission-a", closure["ts"]) is None
    assert replay.in_force("mission-a", closure["ts"] + 1) is None


def test_withdrawal_and_supersession_keep_existing_preclosure_semantics(tmp_path, monkeypatch):
    log, household, declarations, projection = _world(tmp_path, monkeypatch, "withdrawn", "superseded")
    withdrawn_at = declarations["withdrawn"]["ts"]
    withdrawn = _declare_target(projection, household.id, "withdrawn", withdrawn_at + 1)
    projection.withdraw(household_id=household.id, target_id=withdrawn.id, reason="operator withdrawal")
    withdrawal = list(log.events())[-1]
    withdrawn_closure = _close(log, "withdrawn")
    replay = _projection(log)
    assert replay.in_force("withdrawn", withdrawal["ts"] - 1).id == withdrawn.id
    assert replay.in_force("withdrawn", withdrawal["ts"]) is None
    assert replay.in_force("withdrawn", withdrawn_closure["ts"] + 1) is None

    superseded_at = declarations["superseded"]["ts"]
    first = _declare_target(projection, household.id, "superseded", superseded_at + 1)
    second = _declare_target(projection, household.id, "superseded", superseded_at + 2, supersedes=first.id)
    superseded_closure = _close(log, "superseded")
    replay = _projection(log)
    assert replay.in_force("superseded", superseded_closure["ts"] - 1).id == second.id
    assert replay.in_force("superseded", superseded_closure["ts"]) is None


def test_mission_closure_is_isolated_and_later_redeclaration_cannot_resurrect(tmp_path, monkeypatch):
    log, household, declarations, projection = _world(tmp_path, monkeypatch, "mission-a", "mission-b")
    _declare_target(projection, household.id, "mission-a", declarations["mission-a"]["ts"] + 1)
    target_b = _declare_target(projection, household.id, "mission-b", declarations["mission-b"]["ts"] + 1)
    closure = _close(log, "mission-a")
    log.append("core.mission.declared", declarations["mission-a"]["payload"].copy())

    replay = _projection(log)
    assert replay.in_force("mission-a", closure["ts"] + 1) is None
    assert replay.in_force("mission-b", closure["ts"] + 1).id == target_b.id


def test_earliest_applicable_closure_governs_and_predeclaration_closure_is_ignored(tmp_path, monkeypatch):
    log, household, declarations, projection = _world(tmp_path, monkeypatch, "mission-a")
    target = _declare_target(projection, household.id, "mission-a", declarations["mission-a"]["ts"] + 1)
    first_closure = _close(log, "mission-a")
    _close(log, "mission-a", status="unrecognised-but-terminal")
    replay = _projection(log)
    assert replay.in_force("mission-a", first_closure["ts"] - 1).id == target.id
    assert replay.in_force("mission-a", first_closure["ts"]) is None

    pre_log, pre_household, _, _ = _world(tmp_path / "pre", monkeypatch, "other")
    pre_log.append("core.mission.closed", {"entity_id": "future", "reason": "forged early closure"})
    future_declaration = _declare_mission(pre_log, "future")
    pre_projection = _projection(pre_log)
    future_target = _declare_target(pre_projection, pre_household.id, "future", future_declaration["ts"] + 1)
    assert pre_projection.in_force("future", future_declaration["ts"] + 2).id == future_target.id


def test_malformed_or_unrelated_mission_history_is_restrictive_only_and_replay_is_deterministic(tmp_path, monkeypatch):
    log, household, declarations, projection = _world(tmp_path, monkeypatch, "mission-a", "mission-b")
    target_a = _declare_target(projection, household.id, "mission-a", declarations["mission-a"]["ts"] + 1)
    target_b = _declare_target(projection, household.id, "mission-b", declarations["mission-b"]["ts"] + 1)
    log.append("core.mission.closed", {"entity_id": "", "reason": "malformed"})
    log.append("core.mission.closed", {"entity_id": 7, "reason": "malformed"})
    log.append("core.mission.closed", {"entity_id": "unknown", "reason": "unrelated"})
    log.append("core.mission.closed.extra", {"entity_id": "mission-a", "reason": "wrong kind"})

    first = _projection(log)
    second = _projection(log)
    as_of = 9_999.0
    assert first.in_force("mission-a", as_of).id == target_a.id
    assert first.in_force("mission-b", as_of).id == target_b.id
    assert second.in_force("mission-a", as_of) == first.in_force("mission-a", as_of)
    assert second.in_force("mission-b", as_of) == first.in_force("mission-b", as_of)

    log.append("core.mission.closed", {"reason": "missing entity id"})
    first.rebuild()
    assert first.in_force("mission-a", as_of).id == target_a.id
    assert first.in_force("mission-b", as_of).id == target_b.id

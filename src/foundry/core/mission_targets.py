"""RFC-016 Mission Target projection and canonical write gate.

Mission Targets are immutable declarations.  This module owns no Finance
vocabulary and never changes a Mission or an assessment contract.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from numbers import Real
from typing import Protocol

from foundry.eventlog import EventLog

from . import grammar, vocab
from .entities import EntityProjection
from .mission_assessment import MissionDefinition

PREFIX = "core"
TYPE = "mission_target"
MAX_BASIS_LENGTH = 500


class MissionTargetError(ValueError):
    """A target declaration is inadmissible and must not be appended."""


def _finite(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(float(value)):
        raise MissionTargetError(f"{field_name} must be a finite number")
    return float(value)


def _text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MissionTargetError(f"{field_name} must be a non-empty string")
    return value.strip()


@dataclass(frozen=True)
class TargetQuantity:
    value: float
    unit_or_currency: str
    dimension: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _finite(self.value, "target quantity value"))
        object.__setattr__(self, "unit_or_currency", _text(self.unit_or_currency, "target quantity unit"))
        if self.dimension not in vocab.TARGET_DIMENSION:
            raise MissionTargetError("unsupported target quantity dimension")


@dataclass(frozen=True)
class MetricDescriptor:
    metric_id: str
    dimension: str
    unit_or_currency: str
    destination_direction: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "metric_id", _text(self.metric_id, "metric id"))
        if self.dimension not in vocab.TARGET_DIMENSION:
            raise MissionTargetError("unsupported metric dimension")
        object.__setattr__(self, "unit_or_currency", _text(self.unit_or_currency, "metric unit"))
        if self.destination_direction not in vocab.DESTINATION_DIRECTION:
            raise MissionTargetError("unsupported metric destination direction")


class TargetMetricResolver(Protocol):
    def describe(self, metric_id: str) -> MetricDescriptor | None: ...


class MissionDefinitionResolver(Protocol):
    def definition_for_policy(self, policy_id: str) -> MissionDefinition | None: ...


@dataclass(frozen=True)
class MissionTarget:
    id: str
    mission_id: str
    household_id: str
    metric_id: str
    destination: TargetQuantity
    destination_direction: str
    horizon_kind: str
    horizon_at: float | None
    effective_from: float
    tolerance: TargetQuantity | None = None
    basis: str | None = None
    supersedes: str | None = None
    provenance: tuple[str, ...] = ()
    history: tuple[str, ...] = ()
    declared_at: float = 0.0
    closed_at: float | None = None


class MissionTargetProjection:
    """Rebuildable, fail-closed Mission Target projection."""

    def __init__(self, log: EventLog, entities: EntityProjection,
                 definitions: MissionDefinitionResolver,
                 metric_resolver: TargetMetricResolver):
        self.log, self.entities = log, entities
        self.definitions, self.metric_resolver = definitions, metric_resolver
        self.targets: dict[str, MissionTarget] = {}
        self.conflicts: dict[str, tuple[str, ...]] = {}
        self._invalid_target_ids: set[str] = set()
        self._mission_closed_at: dict[str, float] = {}
        self.rebuild()

    def rebuild(self) -> None:
        self.targets, self.conflicts, self._invalid_target_ids, self._mission_closed_at = {}, {}, set(), {}
        declared_mission_ids: set[str] = set()
        for event in self.log.events():
            kind = event["kind"]
            payload = event["payload"]
            if kind == "core.mission.declared":
                mission_id = payload.get("entity_id")
                if isinstance(mission_id, str) and mission_id:
                    declared_mission_ids.add(mission_id)
            elif kind == "core.mission.closed":
                mission_id = payload.get("entity_id")
                if (isinstance(mission_id, str) and mission_id in declared_mission_ids
                        and mission_id not in self._mission_closed_at):
                    self._mission_closed_at[mission_id] = event["ts"]
            if event["kind"].startswith(f"{PREFIX}.{TYPE}."):
                self._apply(event)
        self._detect_conflicts()

    def _conflict(self, mission_id: str, *target_ids: str) -> None:
        known = set(self.conflicts.get(mission_id, ()))
        known.update(target_id for target_id in target_ids if target_id)
        self.conflicts[mission_id] = tuple(sorted(known))

    def _apply(self, event: dict) -> None:
        payload = event["payload"]
        target_id = payload.get("entity_id")
        if not isinstance(target_id, str) or not target_id:
            return
        verb = grammar.verb(event["kind"])
        if verb == "updated":
            prior = self.targets.get(target_id)
            self._invalidate(target_id, prior)
            return
        if verb == "declared":
            try:
                target = self._target_from_event(event)
            except (KeyError, TypeError, ValueError, MissionTargetError):
                self._conflict(f"invalid:{target_id}", target_id)
                return
            if target_id in self.targets:
                self._conflict(target.mission_id, target_id)
                return
            self.targets[target_id] = target
            if target_id in self._invalid_target_ids:
                self._conflict(target.mission_id, target_id)
            return
        target = self.targets.get(target_id)
        if target is None:
            self._invalidate(target_id, None)
        elif verb == "closed":
            self.targets[target_id] = MissionTarget(**{**target.__dict__, "closed_at": event["ts"],
                                                        "history": target.history + (event["id"],)})
        else:
            self._invalidate(target_id, target)

    def _invalidate(self, target_id: str, target: MissionTarget | None) -> None:
        """Poison an invalid lifecycle stream permanently for this replay."""
        self._invalid_target_ids.add(target_id)
        if target is not None:
            self._conflict(target.mission_id, target_id)

    def _target_from_event(self, event: dict) -> MissionTarget:
        p = event["payload"]
        destination = TargetQuantity(p["destination_value"], p["destination_unit"], p["destination_dimension"])
        tolerance = None
        if p.get("tolerance_value") is not None or p.get("tolerance_unit") is not None:
            tolerance = TargetQuantity(p.get("tolerance_value"), p.get("tolerance_unit"), p["destination_dimension"])
        horizon_kind = p["horizon_kind"]
        horizon_at = p.get("horizon_at")
        if horizon_kind not in vocab.TARGET_HORIZON_KIND:
            raise MissionTargetError("unsupported target horizon kind")
        if p["destination_direction"] not in vocab.DESTINATION_DIRECTION:
            raise MissionTargetError("unsupported target destination direction")
        if horizon_kind == "by_date":
            horizon_at = _finite(horizon_at, "target horizon")
        elif horizon_at is not None:
            raise MissionTargetError("only by_date targets may carry a horizon")
        target = MissionTarget(
            id=p["entity_id"], mission_id=_text(p["mission_id"], "mission id"),
            household_id=_text(p["household_id"], "household id"), metric_id=_text(p["metric_id"], "metric id"),
            destination=destination, destination_direction=p["destination_direction"],
            horizon_kind=horizon_kind, horizon_at=horizon_at,
            effective_from=_finite(p["effective_from"], "target effective_from"),
            tolerance=tolerance, basis=p.get("basis"), supersedes=p.get("supersedes"),
            provenance=(event["id"],), history=(event["id"],), declared_at=event["ts"],
        )
        if target.basis is not None and (not isinstance(target.basis, str)
                                         or len(target.basis) > MAX_BASIS_LENGTH):
            raise MissionTargetError("target basis exceeds the 500 character limit")
        self._validate_loaded_target(target)
        return target

    def _validate_loaded_target(self, target: MissionTarget) -> None:
        """Apply declaration gates during replay as well as before append."""
        household = self.entities.parties.get(target.household_id)
        mission = self.entities.missions.get(target.mission_id)
        if household is None or household.party_type != "household" or mission is None:
            raise MissionTargetError("Mission Target references unknown canonical state")
        if mission.target_metric != target.metric_id:
            raise MissionTargetError("Mission Target metric does not match Mission")
        declaration = self.log.get(mission.provenance[0]) if mission.provenance else None
        if declaration is None or target.effective_from < float(declaration["ts"]):
            raise MissionTargetError("target effective_from precedes Mission declaration")
        definition = self.definitions.definition_for_policy(mission.assessment_policy_id or "")
        descriptor = self.metric_resolver.describe(target.metric_id)
        if definition is None or descriptor is None:
            raise MissionTargetError("Mission Target metric is not described")
        if (target.destination.dimension != descriptor.dimension
                or target.destination.unit_or_currency != descriptor.unit_or_currency
                or target.destination_direction != descriptor.destination_direction
                or target.destination_direction != definition.destination_direction):
            raise MissionTargetError("Mission Target does not agree with its descriptor")
        if target.tolerance and (target.tolerance.dimension != target.destination.dimension
                                 or target.tolerance.unit_or_currency != target.destination.unit_or_currency):
            raise MissionTargetError("Mission Target tolerance is incompatible")

    def _detect_conflicts(self) -> None:
        by_mission: dict[str, list[MissionTarget]] = {}
        for target in self.targets.values():
            by_mission.setdefault(target.mission_id, []).append(target)
        for mission_id, grouped in by_mission.items():
            households = {target.household_id for target in grouped}
            if len(households) > 1:
                self._conflict(mission_id, *(target.id for target in grouped))
            successors: dict[str, list[MissionTarget]] = {}
            for target in grouped:
                if target.supersedes:
                    predecessor = self.targets.get(target.supersedes)
                    if (predecessor is None or predecessor.mission_id != mission_id
                            or predecessor.household_id != target.household_id
                            or predecessor.closed_at is not None):
                        self._conflict(mission_id, target.id, target.supersedes)
                    successors.setdefault(target.supersedes, []).append(target)
            for predecessor_id, children in successors.items():
                if len(children) > 1:
                    self._conflict(mission_id, predecessor_id, *(child.id for child in children))
            active = [target for target in grouped
                      if target.closed_at is None and target.id not in successors]
            if len(active) > 1:
                self._conflict(mission_id, *(target.id for target in active))
            for target in grouped:
                seen: set[str] = set()
                cursor = target
                while cursor.supersedes:
                    if cursor.id in seen or cursor.supersedes not in self.targets:
                        self._conflict(mission_id, target.id, cursor.id, cursor.supersedes)
                        break
                    seen.add(cursor.id)
                    cursor = self.targets[cursor.supersedes]

    def declare(self, *, household_id: str, mission_id: str, metric_id: str,
                destination: TargetQuantity, destination_direction: str,
                horizon_kind: str, horizon_at: float | None, effective_from: float,
                tolerance: TargetQuantity | None = None, basis: str | None = None,
                supersedes: str | None = None, actor: str = "user") -> MissionTarget:
        self._validate_declaration(household_id, mission_id, metric_id, destination,
                                   destination_direction, horizon_kind, horizon_at,
                                   effective_from, tolerance, basis, supersedes)
        target_id = grammar.new_id()
        payload = {"entity_id": target_id, "mission_id": mission_id, "household_id": household_id,
                   "metric_id": metric_id, "destination_value": destination.value,
                   "destination_unit": destination.unit_or_currency,
                   "destination_dimension": destination.dimension,
                   "destination_direction": destination_direction, "horizon_kind": horizon_kind,
                   "effective_from": float(effective_from)}
        if horizon_at is not None:
            payload["horizon_at"] = float(horizon_at)
        if tolerance is not None:
            payload.update(tolerance_value=tolerance.value, tolerance_unit=tolerance.unit_or_currency)
        if basis is not None:
            payload["basis"] = basis
        if supersedes is not None:
            payload["supersedes"] = supersedes
        grammar.declare(self.log, PREFIX, TYPE, target_id, payload, actor=actor)
        self.rebuild()
        return self.targets[target_id]

    def withdraw(self, *, household_id: str, target_id: str, reason: str, actor: str = "user") -> MissionTarget:
        target = self.targets.get(target_id)
        if target is None or target.household_id != household_id:
            raise MissionTargetError("unknown Mission Target")
        if target.closed_at is not None:
            raise MissionTargetError("Mission Target is already withdrawn")
        grammar.close(self.log, PREFIX, TYPE, target_id, _text(reason, "withdrawal reason"), actor=actor)
        self.rebuild()
        return self.targets[target_id]

    def _validate_declaration(self, household_id: str, mission_id: str, metric_id: str,
                              destination: TargetQuantity, direction: str, horizon_kind: str,
                              horizon_at: float | None, effective_from: float,
                              tolerance: TargetQuantity | None, basis: str | None,
                              supersedes: str | None) -> None:
        _text(household_id, "household id"); _text(mission_id, "mission id"); _text(metric_id, "metric id")
        _finite(effective_from, "target effective_from")
        if direction not in vocab.DESTINATION_DIRECTION or horizon_kind not in vocab.TARGET_HORIZON_KIND:
            raise MissionTargetError("unsupported target direction or horizon")
        if horizon_kind == "by_date":
            _finite(horizon_at, "target horizon")
        elif horizon_at is not None:
            raise MissionTargetError("only by_date targets may carry a horizon")
        if tolerance and (tolerance.dimension != destination.dimension or tolerance.unit_or_currency != destination.unit_or_currency):
            raise MissionTargetError("target tolerance must have the destination unit and dimension")
        if basis is not None and (not isinstance(basis, str) or len(basis) > MAX_BASIS_LENGTH):
            raise MissionTargetError("target basis must be text of at most 500 characters")
        household = self.entities.parties.get(household_id)
        mission = self.entities.missions.get(mission_id)
        if household is None or household.party_type != "household" or mission is None or mission.target_metric != metric_id:
            raise MissionTargetError("Mission Target metric does not match an existing Mission")
        declaration = self.log.get(mission.provenance[0]) if mission.provenance else None
        if declaration is None or float(effective_from) < float(declaration["ts"]):
            raise MissionTargetError("target effective_from precedes Mission declaration")
        definition = self.definitions.definition_for_policy(mission.assessment_policy_id or "")
        descriptor = self.metric_resolver.describe(metric_id)
        if definition is None or descriptor is None:
            raise MissionTargetError("Mission Target metric is not described")
        if (destination.dimension != descriptor.dimension or destination.unit_or_currency != descriptor.unit_or_currency
                or direction != descriptor.destination_direction or direction != definition.destination_direction):
            raise MissionTargetError("Mission Target does not agree with its metric or Mission definition")
        existing = [target for target in self.targets.values() if target.mission_id == mission_id]
        if existing and any(target.household_id != household_id for target in existing):
            raise MissionTargetError("Mission is bound to another household")
        if supersedes is None:
            if any(target.closed_at is None and not self._is_superseded(target.id) for target in existing):
                raise MissionTargetError("duplicate active Mission Target")
        else:
            predecessor = self.targets.get(supersedes)
            if (predecessor is None or predecessor.mission_id != mission_id
                    or predecessor.household_id != household_id or predecessor.closed_at is not None
                    or self._is_superseded(supersedes)):
                raise MissionTargetError("invalid Mission Target supersession")

    def _is_superseded(self, target_id: str, as_of: float | None = None) -> bool:
        return any(target.supersedes == target_id and (as_of is None or target.effective_from <= as_of)
                   for target in self.targets.values())

    def in_force(self, mission_id: str, as_of: float) -> MissionTarget | None:
        _finite(as_of, "target as_of")
        closed_at = self._mission_closed_at.get(mission_id)
        if closed_at is not None and as_of >= closed_at:
            return None
        if mission_id in self.conflicts:
            return None
        candidates = [target for target in self.targets.values()
                      if target.mission_id == mission_id and target.effective_from <= as_of
                      and (target.closed_at is None or target.closed_at > as_of)
                      and not self._is_superseded(target.id, as_of)]
        return candidates[0] if len(candidates) == 1 else None

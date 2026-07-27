"""Domain-neutral Mission Assessment contract (RFC-005).

`MetricResult` deliberately represents one scalar metric. A mission
assessment is a richer composition: current telemetry, schedule status,
phase, trajectory, a forecast envelope, and scenario-modelled actions.
Putting those fields on `MetricResult` would make a scalar dispatch
contract own product orchestration it cannot understand.

Core owns only the shapes and routing. Each product domain implements a
`MissionAssessmentProvider` and registers it at the composition root.
Nothing in this module imports a product domain, appends an event, or
calls a model.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .metrics import MetricResult
from .scope import Subject
from ..errors import DuplicateMissionAssessmentError


@dataclass(frozen=True)
class MissionAssessmentRequest:
    mission_id: str
    policy_id: str
    scope: Subject
    as_of: float


@dataclass(frozen=True)
class TrajectoryPoint:
    at: float
    value: float


@dataclass(frozen=True)
class ForecastPoint:
    at: float
    low: float
    base: float
    high: float


@dataclass(frozen=True)
class MissionPhaseAssessment:
    id: str
    label: str
    lower_bound: float
    upper_bound: float | None
    completion: float
    order: int = 0
    unit_or_currency: str | None = None
    is_current: bool = False
    is_complete: bool = False
    completes_mission: bool = False
    estimated_at: float | None = None


@dataclass(frozen=True)
class MissionMargin:
    pace_percent: float | None
    schedule_buffer_days: float | None
    description: str


@dataclass(frozen=True)
class DeltaV:
    days: float | None
    lookback_days: int
    description: str
    months: int | None = None
    direction: str | None = None
    resolution: str = "month"


@dataclass(frozen=True)
class RecommendationAssessment:
    action: str
    scenario_id: str
    estimated_delta_v_days: float | None
    status: str = "available"
    action_type: str = ""
    action_label: str = ""
    amount: float | None = None
    unit_or_currency: str | None = None
    cadence: str | None = None
    adjustment_key: str = ""
    estimated_delta_v_months: int | None = None
    delta_v_direction: str | None = None
    limitations: tuple[str, ...] = ()
    assumption_references: tuple[str, ...] = ()
    evidence_references: tuple[str, ...] = ()


@dataclass(frozen=True)
class MissionAssessment:
    mission_id: str
    policy_id: str
    scope: Subject
    as_of: float
    status: str
    calculation_version: str
    current_value: MetricResult | None = None
    mission_complete: bool = False
    eta: float | None = None
    flight_status_id: str = ""
    flight_status_label: str = ""
    phase: MissionPhaseAssessment | None = None
    phases: tuple[MissionPhaseAssessment, ...] = ()
    mission_margin: MissionMargin | None = None
    delta_v: DeltaV | None = None
    trajectory: tuple[TrajectoryPoint, ...] = ()
    forecast: tuple[ForecastPoint, ...] = ()
    telemetry: tuple[MetricResult, ...] = ()
    recommendations: tuple[RecommendationAssessment, ...] = ()
    input_references: tuple[str, ...] = ()
    evidence_references: tuple[str, ...] = ()
    assumption_references: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    confidence_basis: str = ""
    forecast_resolution: str = "month"
    # Backward-compatible V1 field. New renderers use `phases`, which
    # carries complete bounds, unit, order, completion and ETA metadata.
    phase_thresholds: tuple[tuple[str, float], ...] = ()

    @classmethod
    def unavailable(cls, request: MissionAssessmentRequest, reason: str,
                    calculation_version: str = "") -> "MissionAssessment":
        return cls(
            mission_id=request.mission_id, policy_id=request.policy_id,
            scope=request.scope, as_of=request.as_of, status="unavailable",
            calculation_version=calculation_version, limitations=(reason,),
        )


class MissionAssessmentProvider(Protocol):
    def owned_policy_ids(self) -> frozenset[str]:
        """Which stable Mission assessment policy identifiers this domain owns."""
        ...

    def assess(self, request: MissionAssessmentRequest) -> MissionAssessment:
        """Deterministic, read-only assessment. No model call or event append."""
        ...


class MissionAssessmentRegistry:
    """`policy_id -> exactly one provider`; routing only."""

    def __init__(self) -> None:
        self._providers: dict[str, MissionAssessmentProvider] = {}

    def register(self, provider: MissionAssessmentProvider) -> None:
        owned = provider.owned_policy_ids()
        for policy_id in owned:
            existing = self._providers.get(policy_id)
            if existing is not None and existing is not provider:
                raise DuplicateMissionAssessmentError(
                    f"{policy_id!r} is already registered to {existing!r}; "
                    f"{provider!r} cannot also claim it")
        for policy_id in owned:
            self._providers[policy_id] = provider

    def owned_policy_ids(self) -> frozenset[str]:
        return frozenset(self._providers)

    def dispatch(self, request: MissionAssessmentRequest) -> MissionAssessment:
        provider = self._providers.get(request.policy_id)
        if provider is None:
            return MissionAssessment.unavailable(
                request, "no provider registered for this assessment policy")
        return provider.assess(request)

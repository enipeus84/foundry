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

from datetime import datetime, timezone
from dataclasses import dataclass
import math
from numbers import Real
import re
from typing import Protocol

from .metrics import MetricResult
from .scope import Subject
from .vocab import (
    DESTINATION_DIRECTION,
    INSTRUMENT_APPLICABILITY,
    MISSION_CONFIDENCE,
    MISSION_MARGIN,
    MISSION_TRAJECTORY,
    TELEMETRY_FORMAT,
    TELEMETRY_REGION,
    TRAJECTORY_MOVEMENT,
)
from ..errors import DuplicateMissionAssessmentError


_SAFE_MISSION_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_MAX_DISPLAY_GROUP_LENGTH = 80


def _require_text(value, field: str, *, allow_empty: bool = False) -> None:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise ValueError(f"{field} must be a string"
                         + (" " if allow_empty else " and must not be empty"))


def _require_finite(value, field: str, *, allow_none: bool = False) -> None:
    if value is None and allow_none:
        return
    if isinstance(value, bool) or not isinstance(value, Real) \
            or not math.isfinite(float(value)):
        raise ValueError(f"{field} must be a finite number")


def _require_utc_timestamp(
    value,
    field: str,
    *,
    allow_none: bool = False,
) -> None:
    _require_finite(value, field, allow_none=allow_none)
    if value is None:
        return
    try:
        datetime.fromtimestamp(float(value), tz=timezone.utc)
    except (OSError, OverflowError, ValueError):
        raise ValueError(f"{field} must be a representable UTC timestamp") \
            from None


@dataclass(frozen=True)
class MissionDefinition:
    """Discoverable mission metadata; it never contains assessment results."""

    slug: str
    label: str
    order: int
    destination_direction: str
    definition: str = ""
    assessment_policy_id: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.slug, "mission slug")
        if not _SAFE_MISSION_SLUG.fullmatch(self.slug):
            raise ValueError("mission slug must be lowercase kebab-case")
        _require_text(self.label, "mission label")
        if isinstance(self.order, bool) or not isinstance(self.order, int) \
                or self.order < 0:
            raise ValueError("mission order must be a non-negative integer")
        _require_text(self.destination_direction, "destination direction")
        if self.destination_direction not in DESTINATION_DIRECTION:
            raise ValueError("unsupported destination direction")
        _require_text(self.definition, "mission definition", allow_empty=True)
        if self.assessment_policy_id is not None:
            _require_text(
                self.assessment_policy_id, "assessment policy id")


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
class InstrumentApplicability:
    """Declared meaning and availability of optional mission instruments."""

    eta: str = "applicable"
    delta_v: str = "applicable"
    trajectory: str = "applicable"
    forecast: str = "applicable"
    margin: str = "applicable"

    def __post_init__(self) -> None:
        for field, value in (
            ("eta", self.eta),
            ("delta_v", self.delta_v),
            ("trajectory", self.trajectory),
            ("forecast", self.forecast),
            ("margin", self.margin),
        ):
            _require_text(value, f"{field} applicability")
            if value not in INSTRUMENT_APPLICABILITY:
                raise ValueError(f"unsupported {field} applicability")


@dataclass(frozen=True)
class MissionMilestone:
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
    destination_direction: str = "higher_is_better"
    destination_value: float | None = None

    def __post_init__(self) -> None:
        _require_text(self.id, "milestone id")
        _require_text(self.label, "milestone label")
        _require_finite(self.lower_bound, "milestone lower bound")
        _require_finite(
            self.upper_bound, "milestone upper bound", allow_none=True)
        if (
            self.upper_bound is not None
            and self.upper_bound <= self.lower_bound
        ):
            raise ValueError("milestone upper bound must exceed lower bound")
        _require_finite(self.completion, "milestone completion")
        if not 0.0 <= self.completion <= 1.0:
            raise ValueError("milestone completion must be between zero and one")
        if isinstance(self.order, bool) or not isinstance(self.order, int) \
                or self.order < 0:
            raise ValueError("milestone order must be a non-negative integer")
        if self.unit_or_currency is not None:
            _require_text(self.unit_or_currency, "milestone unit")
        for field, value in (
            ("is_current", self.is_current),
            ("is_complete", self.is_complete),
            ("completes_mission", self.completes_mission),
        ):
            if not isinstance(value, bool):
                raise ValueError(f"milestone {field} must be boolean")
        _require_finite(
            self.estimated_at, "milestone estimate", allow_none=True)
        _require_text(self.destination_direction, "destination direction")
        if self.destination_direction not in DESTINATION_DIRECTION:
            raise ValueError("unsupported destination direction")
        _require_finite(
            self.destination_value,
            "milestone destination value",
            allow_none=True,
        )

    @property
    def target_value(self) -> float:
        if self.destination_value is not None:
            return self.destination_value
        return self.lower_bound


@dataclass(frozen=True)
class MissionMargin:
    pace_percent: float | None
    schedule_buffer_days: float | None
    description: str
    state: str | None = None
    label: str = ""
    value: float | None = None
    unit_or_currency: str | None = None
    format_kind: str = "plain"

    def __post_init__(self) -> None:
        _require_finite(
            self.pace_percent, "mission pace margin", allow_none=True)
        _require_finite(
            self.schedule_buffer_days,
            "mission schedule buffer",
            allow_none=True,
        )
        _require_text(self.description, "mission margin description")
        if self.state is not None:
            _require_text(self.state, "mission margin")
            if self.state not in MISSION_MARGIN:
                raise ValueError("unsupported mission margin")
        _require_text(self.label, "mission margin label", allow_empty=True)
        _require_finite(self.value, "mission margin value", allow_none=True)
        if self.unit_or_currency is not None:
            _require_text(self.unit_or_currency, "mission margin unit")
        if self.format_kind not in TELEMETRY_FORMAT:
            raise ValueError("unsupported mission margin format")


@dataclass(frozen=True)
class MissionConfidence:
    state: str
    basis: str

    def __post_init__(self) -> None:
        _require_text(self.state, "mission confidence")
        if self.state not in MISSION_CONFIDENCE:
            raise ValueError("unsupported mission confidence")
        _require_text(self.basis, "mission confidence basis")


@dataclass(frozen=True)
class TelemetryItem:
    result: MetricResult
    label: str
    format_kind: str = "plain"
    qualifier: str = ""
    display_region: str = "drilldown"
    display_group: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.result, MetricResult):
            raise ValueError("telemetry result must be a MetricResult")
        _require_text(self.label, "telemetry label")
        if self.format_kind not in TELEMETRY_FORMAT:
            raise ValueError("unsupported telemetry format")
        _require_text(
            self.qualifier, "telemetry qualifier", allow_empty=True)
        _require_text(self.display_region, "telemetry display region")
        if self.display_region not in TELEMETRY_REGION:
            raise ValueError("unsupported telemetry display region")
        _require_text(
            self.display_group, "telemetry display group", allow_empty=True)
        if self.display_region == "essential" and self.display_group:
            raise ValueError(
                "essential telemetry cannot declare a display group")
        if self.display_group and (
            not self.display_group.strip()
            or len(self.display_group) > _MAX_DISPLAY_GROUP_LENGTH
        ):
            raise ValueError("invalid telemetry display group")


@dataclass(frozen=True)
class DeltaV:
    days: float | None
    lookback_days: int
    description: str
    months: int | None = None
    direction: str | None = None
    resolution: str = "month"
    period_label: str = ""
    reference_start_at: float | None = None
    reference_start_label: str = ""
    reference_destination_at: float | None = None
    reference_destination_label: str = ""

    def __post_init__(self) -> None:
        _require_finite(self.days, "delta-v days", allow_none=True)
        if (
            isinstance(self.lookback_days, bool)
            or not isinstance(self.lookback_days, int)
            or self.lookback_days < 0
        ):
            raise ValueError("delta-v lookback must be a non-negative integer")
        _require_text(self.description, "delta-v description")
        if self.months is not None and (
            isinstance(self.months, bool) or not isinstance(self.months, int)
        ):
            raise ValueError("delta-v months must be an integer")
        if self.direction not in (None, "accelerated", "delayed"):
            raise ValueError("unsupported delta-v direction")
        _require_text(self.resolution, "delta-v resolution")
        _require_text(
            self.period_label, "delta-v period label", allow_empty=True)
        for field, value in (
            ("reference start", self.reference_start_at),
            ("reference destination", self.reference_destination_at),
        ):
            _require_utc_timestamp(
                value, f"delta-v {field}", allow_none=True)
        for field, value in (
            ("reference start", self.reference_start_label),
            ("reference destination", self.reference_destination_label),
        ):
            _require_text(
                value, f"delta-v {field} label", allow_empty=True)
        for at, label, field in (
            (
                self.reference_start_at,
                self.reference_start_label,
                "reference start",
            ),
            (
                self.reference_destination_at,
                self.reference_destination_label,
                "reference destination",
            ),
        ):
            if (at is None) != (not label):
                raise ValueError(
                    f"delta-v {field} time and label must be supplied together")


@dataclass(frozen=True)
class MissionTrajectoryView:
    """Domain-neutral trajectory instrument consumed by Mission Console."""

    state: str | None
    tone: str
    movement: str = "unknown"
    destination_direction: str = "higher_is_better"
    history: str = "unavailable"
    forecast: str = "unavailable"
    intercept_at: float | None = None
    intercept_label: str = ""
    recent_change: DeltaV | None = None
    confidence_state: str = "Insufficient"
    evidence_note: str = ""

    def __post_init__(self) -> None:
        if self.state is not None and self.state not in MISSION_TRAJECTORY:
            raise ValueError("unsupported mission trajectory")
        if self.tone not in ("", "green", "amber", "red", "none"):
            raise ValueError("unsupported trajectory presentation tone")
        if self.movement not in TRAJECTORY_MOVEMENT:
            raise ValueError("unsupported trajectory movement")
        if self.destination_direction not in DESTINATION_DIRECTION:
            raise ValueError("unsupported destination direction")
        for field, value in (("history", self.history), ("forecast", self.forecast)):
            if value not in INSTRUMENT_APPLICABILITY:
                raise ValueError(f"unsupported trajectory {field} applicability")
        _require_utc_timestamp(
            self.intercept_at, "trajectory intercept", allow_none=True)
        _require_text(
            self.intercept_label, "trajectory intercept label", allow_empty=True)
        if self.recent_change is not None \
                and not isinstance(self.recent_change, DeltaV):
            raise ValueError("trajectory recent change must be DeltaV")
        if self.confidence_state not in MISSION_CONFIDENCE:
            raise ValueError("unsupported trajectory confidence")
        _require_text(
            self.evidence_note, "trajectory evidence note", allow_empty=True)


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
    trajectory_state: str | None = None
    trajectory_tone: str = ""
    confidence: MissionConfidence | None = None
    current_milestone: MissionMilestone | None = None
    milestones: tuple[MissionMilestone, ...] = ()
    flight_status_id: str = ""
    flight_status_label: str = ""
    mission_margin: MissionMargin | None = None
    delta_v: DeltaV | None = None
    trajectory: tuple[TrajectoryPoint, ...] = ()
    forecast: tuple[ForecastPoint, ...] = ()
    telemetry: tuple[TelemetryItem, ...] = ()
    recommendations: tuple[RecommendationAssessment, ...] = ()
    input_references: tuple[str, ...] = ()
    evidence_references: tuple[str, ...] = ()
    assumption_references: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    confidence_basis: str = ""
    forecast_resolution: str = "month"
    applicability: InstrumentApplicability = InstrumentApplicability()

    def __post_init__(self) -> None:
        if (
            self.trajectory_state is not None
            and self.trajectory_state not in MISSION_TRAJECTORY
        ):
            raise ValueError("unsupported mission trajectory")
        if self.trajectory_tone not in ("", "green", "amber", "red", "none"):
            raise ValueError("unsupported trajectory presentation tone")

    @classmethod
    def unavailable(cls, request: MissionAssessmentRequest, reason: str,
                    calculation_version: str = "") -> "MissionAssessment":
        return cls(
            mission_id=request.mission_id, policy_id=request.policy_id,
            scope=request.scope, as_of=request.as_of, status="unavailable",
            calculation_version=calculation_version,
            confidence=MissionConfidence("Insufficient", reason),
            limitations=(reason,),
            applicability=InstrumentApplicability(
                eta="unavailable",
                delta_v="unavailable",
                trajectory="unavailable",
                forecast="unavailable",
                margin="unavailable",
            ),
        )


class MissionAssessmentProvider(Protocol):
    def owned_policy_ids(self) -> frozenset[str]:
        """Which stable Mission assessment policy identifiers this domain owns."""
        ...

    def assess(self, request: MissionAssessmentRequest) -> MissionAssessment:
        """Deterministic, read-only assessment. No model call or event append."""
        ...


class MissionAssessmentRegistry:
    """Definition discovery plus isolated `policy_id` provider routing."""

    def __init__(self) -> None:
        self._providers: dict[str, MissionAssessmentProvider] = {}
        self._definitions: dict[str, MissionDefinition] = {}
        self._definitions_by_policy: dict[str, MissionDefinition] = {}
        self._definitions_by_order: dict[int, MissionDefinition] = {}

    def register_definition(self, definition: MissionDefinition) -> None:
        existing = self._definitions.get(definition.slug)
        if existing is not None and existing != definition:
            raise DuplicateMissionAssessmentError(
                f"mission slug {definition.slug!r} is already registered")
        order_owner = self._definitions_by_order.get(definition.order)
        if order_owner is not None and order_owner != definition:
            raise DuplicateMissionAssessmentError(
                f"mission order {definition.order!r} is already assigned "
                f"to mission {order_owner.slug!r}")
        policy_id = definition.assessment_policy_id
        if policy_id is not None:
            policy_owner = self._definitions_by_policy.get(policy_id)
            if policy_owner is not None and policy_owner != definition:
                raise DuplicateMissionAssessmentError(
                    f"assessment policy {policy_id!r} is already assigned "
                    f"to mission {policy_owner.slug!r}")
        self._definitions[definition.slug] = definition
        self._definitions_by_order[definition.order] = definition
        if policy_id is not None:
            self._definitions_by_policy[policy_id] = definition

    def definitions(self) -> tuple[MissionDefinition, ...]:
        return tuple(sorted(
            self._definitions.values(),
            key=lambda definition: (definition.order, definition.slug),
        ))

    def definition_for_slug(self, slug: str) -> MissionDefinition | None:
        return self._definitions.get(slug)

    def definition_for_policy(self, policy_id: str) -> MissionDefinition | None:
        return self._definitions_by_policy.get(policy_id)

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
        try:
            result = provider.assess(request)
            self._validate_provider_result(request, result)
            return result
        except Exception:
            return MissionAssessment.unavailable(
                request, "assessment provider failed safely")

    def _validate_provider_result(
        self,
        request: MissionAssessmentRequest,
        result: MissionAssessment,
    ) -> None:
        if not isinstance(result, MissionAssessment):
            raise TypeError("provider returned an unsupported result")
        if (
            result.mission_id != request.mission_id
            or result.policy_id != request.policy_id
            or result.scope != request.scope
            or result.as_of != request.as_of
        ):
            raise ValueError("provider result does not match its request envelope")
        _require_text(result.status, "assessment status")
        _require_text(
            result.calculation_version,
            "assessment calculation version",
            allow_empty=result.status == "unavailable",
        )
        if not isinstance(result.mission_complete, bool):
            raise ValueError("mission_complete must be boolean")
        _require_finite(result.eta, "assessment ETA", allow_none=True)
        if result.trajectory_state is not None:
            _require_text(result.trajectory_state, "mission trajectory")
            if result.trajectory_state not in MISSION_TRAJECTORY:
                raise ValueError("unsupported mission trajectory")
        _require_text(
            result.trajectory_tone,
            "trajectory presentation tone",
            allow_empty=True,
        )
        if result.trajectory_tone not in (
            "", "green", "amber", "red", "none"
        ):
            raise ValueError("unsupported trajectory presentation tone")
        if result.confidence is not None \
                and not isinstance(result.confidence, MissionConfidence):
            raise TypeError("provider returned unsupported confidence")
        if result.mission_margin is not None \
                and not isinstance(result.mission_margin, MissionMargin):
            raise TypeError("provider returned unsupported mission margin")
        if not isinstance(result.applicability, InstrumentApplicability):
            raise TypeError("provider returned unsupported instrument applicability")

        for field, values in (
            ("milestones", result.milestones),
            ("trajectory", result.trajectory),
            ("forecast", result.forecast),
            ("telemetry", result.telemetry),
            ("recommendations", result.recommendations),
        ):
            if not isinstance(values, tuple):
                raise TypeError(f"provider {field} must be a tuple")
        if any(
            not isinstance(milestone, MissionMilestone)
            for milestone in result.milestones
        ):
            raise TypeError("provider returned unsupported milestones")
        definition = self.definition_for_policy(request.policy_id)
        if definition is not None and any(
            milestone.destination_direction
            != definition.destination_direction
            for milestone in result.milestones
        ):
            raise ValueError(
                "milestone direction disagrees with mission definition")
        if result.current_milestone is not None:
            if not isinstance(result.current_milestone, MissionMilestone):
                raise TypeError("provider returned unsupported current milestone")
            if result.current_milestone not in result.milestones:
                raise ValueError(
                    "current milestone is absent from milestone plan")
            if not result.current_milestone.is_current:
                raise ValueError("current milestone is not marked current")
        if sum(milestone.is_current for milestone in result.milestones) > 1:
            raise ValueError("provider returned multiple current milestones")
        milestone_ids = tuple(
            milestone.id for milestone in result.milestones)
        milestone_orders = tuple(
            milestone.order for milestone in result.milestones)
        if len(set(milestone_ids)) != len(milestone_ids) \
                or len(set(milestone_orders)) != len(milestone_orders):
            raise ValueError("milestone ids and orders must be unique")

        self._validate_series(result)
        self._validate_applicability(result)
        if any(not isinstance(item, TelemetryItem) for item in result.telemetry):
            raise TypeError("provider returned unsupported telemetry")
        essential = tuple(
            item for item in result.telemetry
            if item.display_region == "essential"
        )
        if len(essential) > 6:
            raise ValueError(
                "provider returned more than six essential telemetry items")
        if any(
            item.result.status not in ("available", "stale")
            for item in essential
        ):
            raise ValueError(
                "essential telemetry must carry current evidence")
        metric_results = tuple(item.result for item in result.telemetry)
        if result.current_value is not None:
            metric_results += (result.current_value,)
        for metric in metric_results:
            self._validate_metric_result(request, metric)

        if result.delta_v is not None:
            self._validate_delta_v(result.delta_v)
        for recommendation in result.recommendations:
            self._validate_recommendation(recommendation)
        for field, values in (
            ("input references", result.input_references),
            ("evidence references", result.evidence_references),
            ("assumption references", result.assumption_references),
            ("limitations", result.limitations),
        ):
            self._validate_text_tuple(values, field)
        _require_text(
            result.confidence_basis,
            "confidence basis",
            allow_empty=True,
        )
        _require_text(result.forecast_resolution, "forecast resolution")

    @staticmethod
    def _validate_applicability(result: MissionAssessment) -> None:
        instruments = (
            ("eta", result.applicability.eta, result.eta is not None),
            (
                "delta-v",
                result.applicability.delta_v,
                result.delta_v is not None,
            ),
            (
                "trajectory",
                result.applicability.trajectory,
                len(result.trajectory) > 0,
            ),
            (
                "forecast",
                result.applicability.forecast,
                len(result.forecast) > 0,
            ),
            (
                "margin",
                result.applicability.margin,
                result.mission_margin is not None,
            ),
        )
        for name, applicability, present in instruments:
            if applicability == "applicable" and not present:
                raise ValueError(
                    f"applicable {name} instrument must be present")
            if applicability in ("not_applicable", "unavailable") and present:
                raise ValueError(
                    f"{applicability} {name} instrument must be absent")

    @staticmethod
    def _validate_series(result: MissionAssessment) -> None:
        prior_at: float | None = None
        for point in result.trajectory:
            if not isinstance(point, TrajectoryPoint):
                raise TypeError("provider returned unsupported trajectory")
            _require_finite(point.at, "trajectory timestamp")
            _require_finite(point.value, "trajectory value")
            if point.at > result.as_of:
                raise ValueError("observed trajectory cannot be in the future")
            if prior_at is not None and point.at < prior_at:
                raise ValueError("trajectory must be time ordered")
            prior_at = point.at

        prior_at = None
        for point in result.forecast:
            if not isinstance(point, ForecastPoint):
                raise TypeError("provider returned unsupported forecast")
            for field, value in (
                ("forecast timestamp", point.at),
                ("forecast low", point.low),
                ("forecast base", point.base),
                ("forecast high", point.high),
            ):
                _require_finite(value, field)
            if not point.low <= point.base <= point.high:
                raise ValueError("forecast paths must be ordered low/base/high")
            if point.at < result.as_of:
                raise ValueError("forecast cannot precede assessment time")
            if prior_at is not None and point.at < prior_at:
                raise ValueError("forecast must be time ordered")
            prior_at = point.at

    @staticmethod
    def _validate_metric_result(
        request: MissionAssessmentRequest,
        metric: MetricResult,
    ) -> None:
        if not isinstance(metric, MetricResult):
            raise TypeError("provider returned unsupported metric evidence")
        if metric.scope != request.scope:
            raise ValueError("provider returned cross-scope evidence")
        if metric.as_of != request.as_of:
            raise ValueError("provider returned evidence for another timestamp")
        _require_text(metric.metric_id, "metric id")
        _require_finite(metric.value, "metric value", allow_none=True)
        if metric.status in ("available", "stale") and metric.value is None:
            raise ValueError(
                "available or stale metric evidence must carry a value")
        if metric.unit_or_currency is not None:
            _require_text(metric.unit_or_currency, "metric unit")
        _require_text(metric.calculation_version, "metric calculation version",
                      allow_empty=metric.status in ("unsupported", "unavailable"))
        for field, values in (
            ("metric input references", metric.input_references),
            ("metric evidence references", metric.evidence_references),
            ("metric assumption references", metric.assumption_references),
            ("metric limitations", metric.limitations),
        ):
            MissionAssessmentRegistry._validate_text_tuple(values, field)

    @staticmethod
    def _validate_delta_v(delta_v: DeltaV) -> None:
        if not isinstance(delta_v, DeltaV):
            raise TypeError("provider returned unsupported delta-v")
        _require_finite(delta_v.days, "delta-v days", allow_none=True)
        if isinstance(delta_v.lookback_days, bool) \
                or not isinstance(delta_v.lookback_days, int) \
                or delta_v.lookback_days < 0:
            raise ValueError("delta-v lookback must be a non-negative integer")
        _require_text(delta_v.description, "delta-v description")
        if delta_v.months is not None and (
            isinstance(delta_v.months, bool)
            or not isinstance(delta_v.months, int)
        ):
            raise ValueError("delta-v months must be an integer")
        if delta_v.direction not in (None, "accelerated", "delayed"):
            raise ValueError("unsupported delta-v direction")
        _require_text(delta_v.resolution, "delta-v resolution")
        _require_text(
            delta_v.period_label, "delta-v period label", allow_empty=True)
        for field, value in (
            ("reference start", delta_v.reference_start_at),
            ("reference destination", delta_v.reference_destination_at),
        ):
            _require_utc_timestamp(
                value, f"delta-v {field}", allow_none=True)
        for field, value in (
            ("reference start", delta_v.reference_start_label),
            ("reference destination", delta_v.reference_destination_label),
        ):
            _require_text(
                value, f"delta-v {field} label", allow_empty=True)
        for at, label, field in (
            (
                delta_v.reference_start_at,
                delta_v.reference_start_label,
                "reference start",
            ),
            (
                delta_v.reference_destination_at,
                delta_v.reference_destination_label,
                "reference destination",
            ),
        ):
            if (at is None) != (not label):
                raise ValueError(
                    f"delta-v {field} time and label must be supplied together")

    @staticmethod
    def _validate_recommendation(
        recommendation: RecommendationAssessment,
    ) -> None:
        if not isinstance(recommendation, RecommendationAssessment):
            raise TypeError("provider returned unsupported recommendation")
        _require_text(recommendation.action, "recommendation action")
        _require_text(recommendation.scenario_id, "recommendation scenario")
        _require_text(recommendation.status, "recommendation status")
        for field, value in (
            ("recommendation delta-v", recommendation.estimated_delta_v_days),
            ("recommendation amount", recommendation.amount),
        ):
            _require_finite(value, field, allow_none=True)
        for field, value in (
            ("recommendation action type", recommendation.action_type),
            ("recommendation action label", recommendation.action_label),
            ("recommendation adjustment key", recommendation.adjustment_key),
        ):
            _require_text(value, field, allow_empty=True)
        for field, value in (
            ("recommendation unit", recommendation.unit_or_currency),
            ("recommendation cadence", recommendation.cadence),
            ("recommendation delta-v direction",
             recommendation.delta_v_direction),
        ):
            if value is not None:
                _require_text(value, field)
        if recommendation.estimated_delta_v_months is not None and (
            isinstance(recommendation.estimated_delta_v_months, bool)
            or not isinstance(recommendation.estimated_delta_v_months, int)
        ):
            raise ValueError("recommendation delta-v months must be an integer")
        for field, values in (
            ("recommendation limitations", recommendation.limitations),
            ("recommendation assumption references",
             recommendation.assumption_references),
            ("recommendation evidence references",
             recommendation.evidence_references),
        ):
            MissionAssessmentRegistry._validate_text_tuple(values, field)

    @staticmethod
    def _validate_text_tuple(values, field: str) -> None:
        if not isinstance(values, tuple):
            raise ValueError(f"{field} must be a tuple")
        for value in values:
            _require_text(value, field)

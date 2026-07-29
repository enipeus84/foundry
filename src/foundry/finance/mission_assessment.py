"""Financial Independence Mission Assessment (RFC-005).

Finance owns every calculation in this module. Core supplies only the
assessment contract and dispatch registry; Mission Control renders the
returned object and performs no mission arithmetic.

Forecasts are deterministic low/base/high sensitivity paths under one
explicit Assumption Set. They are not calibrated probabilities and are
never presented as a confidence percentage.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

from foundry.core.entities import EntityProjection
from foundry.core.metrics import MetricRegistry, MetricRequest, MetricResult
from foundry.core.mission_assessment import (
    DeltaV, ForecastPoint, MissionAssessment, MissionAssessmentRequest,
    MissionConfidence, MissionMargin, MissionMilestone,
    RecommendationAssessment, TelemetryItem, TrajectoryPoint,
)

from .entities import FinanceEntityProjection, AssumptionSet, Scenario


POLICY_ID = "finance.financial_independence.v1"
CALCULATION_VERSION = "fi-v1"
DAY = 86_400.0
YEAR = 365.2425 * DAY
MONTH = YEAR / 12.0
MONTH_DAYS = MONTH / DAY


@dataclass(frozen=True)
class PhaseDefinition:
    id: str
    label: str
    lower_bound: float
    upper_bound: float | None
    order: int
    completes_mission: bool = False


@dataclass(frozen=True)
class FinancialIndependencePolicy:
    id: str = POLICY_ID
    target_metric: str = "finance.accessible_assets"
    unit_or_currency: str = "GBP"
    building_capital_threshold: float = 450_000.0
    independent_threshold: float = 750_000.0
    abundance_threshold: float = 1_500_000.0
    building_capital_label: str = "Building Capital"
    escape_velocity_label: str = "Escape Velocity"
    independent_label: str = "Independent"
    abundance_label: str = "Abundance"

    def __post_init__(self) -> None:
        thresholds = (
            self.building_capital_threshold,
            self.independent_threshold,
            self.abundance_threshold,
        )
        if any(not math.isfinite(v) or v <= 0 for v in thresholds):
            raise ValueError("phase thresholds must be finite and positive")
        if thresholds != tuple(sorted(thresholds)) or len(set(thresholds)) != 3:
            raise ValueError("phase thresholds must be strictly increasing")
        labels = (
            self.building_capital_label,
            self.escape_velocity_label,
            self.independent_label,
            self.abundance_label,
        )
        if any(not label.strip() for label in labels) or len(set(labels)) != 4:
            raise ValueError("phase labels must be non-empty and unique")
        if not self.unit_or_currency.strip():
            raise ValueError("policy unit_or_currency must be declared")

    @property
    def phases(self) -> tuple[PhaseDefinition, ...]:
        return (
            PhaseDefinition("building_capital", self.building_capital_label, 0.0,
                            self.building_capital_threshold, 0),
            PhaseDefinition("escape_velocity", self.escape_velocity_label,
                            self.building_capital_threshold,
                            self.independent_threshold, 1),
            PhaseDefinition("independent", self.independent_label,
                            self.independent_threshold,
                            self.abundance_threshold, 2, completes_mission=True),
            PhaseDefinition("abundance", self.abundance_label,
                            self.abundance_threshold, None, 3),
        )

    def phase_for(self, value: float) -> MissionMilestone:
        if value < self.building_capital_threshold:
            phase = self.phases[0]
        elif value < self.independent_threshold:
            phase = self.phases[1]
        elif value <= self.abundance_threshold:
            phase = self.phases[2]
        else:
            phase = self.phases[3]

        if phase.upper_bound is None:
            completion = 1.0
        else:
            span = phase.upper_bound - phase.lower_bound
            completion = max(0.0, min(1.0, (value - phase.lower_bound) / span))
        return MissionMilestone(
            id=phase.id, label=phase.label, lower_bound=phase.lower_bound,
            upper_bound=phase.upper_bound, completion=completion,
            order=phase.order, unit_or_currency=self.unit_or_currency,
            is_current=True,
            is_complete=(
                phase.upper_bound is not None and value >= phase.upper_bound),
            completes_mission=phase.completes_mission,
            destination_direction="higher_is_better",
            destination_value=phase.lower_bound)


@dataclass(frozen=True)
class ProjectionInputs:
    monthly_contribution: float
    low_real_return: float
    base_real_return: float
    high_real_return: float
    horizon_years: int
    history_months: int
    delta_v_lookback_days: int
    desired_annual_spending: float
    withdrawal_rate: float

    @classmethod
    def from_assumption_set(cls, assumption_set: AssumptionSet) -> "ProjectionInputs":
        values = assumption_set.assumptions
        required = {
            "monthly_contribution", "low_real_return", "base_real_return",
            "high_real_return", "horizon_years", "history_months",
            "delta_v_lookback_days", "desired_annual_spending",
            "withdrawal_rate",
        }
        missing = sorted(required - values.keys())
        if missing:
            raise ValueError(f"Assumption Set missing: {', '.join(missing)}")
        result = cls(
            monthly_contribution=float(values["monthly_contribution"]),
            low_real_return=float(values["low_real_return"]),
            base_real_return=float(values["base_real_return"]),
            high_real_return=float(values["high_real_return"]),
            horizon_years=int(values["horizon_years"]),
            history_months=int(values["history_months"]),
            delta_v_lookback_days=int(values["delta_v_lookback_days"]),
            desired_annual_spending=float(values["desired_annual_spending"]),
            withdrawal_rate=float(values["withdrawal_rate"]),
        )
        if result.monthly_contribution < 0:
            raise ValueError("monthly_contribution must be non-negative")
        if not (-1.0 < result.low_real_return <= result.base_real_return
                <= result.high_real_return):
            raise ValueError("real returns must be ordered low <= base <= high and greater than -1")
        if not 1 <= result.horizon_years <= 80:
            raise ValueError("horizon_years must be between 1 and 80")
        if not 1 <= result.history_months <= 120:
            raise ValueError("history_months must be between 1 and 120")
        if not 1 <= result.delta_v_lookback_days <= 3650:
            raise ValueError("delta_v_lookback_days must be between 1 and 3650")
        if result.desired_annual_spending <= 0:
            raise ValueError("desired_annual_spending must be positive")
        if not 0 < result.withdrawal_rate <= 1:
            raise ValueError("withdrawal_rate must be in (0, 1]")
        return result


class FinanceProjectionEngine:
    """Pure monthly projection; no state, event writes, or model calls."""

    @staticmethod
    def project(start_value: float, start_at: float, inputs: ProjectionInputs,
                monthly_contribution_delta: float = 0.0) -> tuple[ForecastPoint, ...]:
        contribution = inputs.monthly_contribution + monthly_contribution_delta
        if contribution < 0:
            raise ValueError("scenario makes monthly contribution negative")

        monthly_rates = tuple(
            (1.0 + annual) ** (1.0 / 12.0) - 1.0
            for annual in (
                inputs.low_real_return,
                inputs.base_real_return,
                inputs.high_real_return,
            )
        )
        low = base = high = max(0.0, start_value)
        points = [ForecastPoint(at=start_at, low=low, base=base, high=high)]
        for month in range(1, inputs.horizon_years * 12 + 1):
            low = max(0.0, low * (1.0 + monthly_rates[0]) + contribution)
            base = max(0.0, base * (1.0 + monthly_rates[1]) + contribution)
            high = max(0.0, high * (1.0 + monthly_rates[2]) + contribution)
            points.append(ForecastPoint(
                at=start_at + month * MONTH, low=low, base=base, high=high))
        return tuple(points)

    @staticmethod
    def eta(points: tuple[ForecastPoint, ...], target: float,
            path: str = "base") -> float | None:
        for point in points:
            if getattr(point, path) >= target:
                return point.at
        return None


class FinancialIndependenceAssessor:
    """Finance implementation of Core's MissionAssessmentProvider."""

    def __init__(self, finance: FinanceEntityProjection,
                 core: EntityProjection, metrics: MetricRegistry,
                 policy: FinancialIndependencePolicy | None = None):
        self.finance = finance
        self.core = core
        self.metrics = metrics
        self.policy = policy or FinancialIndependencePolicy()
        self.projection = FinanceProjectionEngine()

    def owned_policy_ids(self) -> frozenset[str]:
        return frozenset({self.policy.id})

    def assess(self, request: MissionAssessmentRequest) -> MissionAssessment:
        mission = self.core.missions.get(request.mission_id)
        if mission is None:
            return MissionAssessment.unavailable(
                request, "mission does not exist", CALCULATION_VERSION)
        if mission.assessment_policy_id != self.policy.id:
            return MissionAssessment.unavailable(
                request, "mission is not declared against this policy",
                CALCULATION_VERSION)
        if mission.target_metric != self.policy.target_metric:
            return MissionAssessment.unavailable(
                request, f"policy requires target metric {self.policy.target_metric}",
                CALCULATION_VERSION)
        if mission.target_value != self.policy.independent_threshold:
            return MissionAssessment.unavailable(
                request, "Mission target does not match the policy's Independent threshold",
                CALCULATION_VERSION)
        assumption_set = self.finance.assumption_sets.get(
            mission.assumption_set_id or "")
        if assumption_set is None or assumption_set.status != "active":
            return MissionAssessment.unavailable(
                request, "active Assumption Set not found", CALCULATION_VERSION)
        try:
            inputs = ProjectionInputs.from_assumption_set(assumption_set)
        except ValueError as exc:
            return MissionAssessment.unavailable(
                request, str(exc), CALCULATION_VERSION)

        current = self._metric(
            self.policy.target_metric, request, request.as_of)
        if current.status not in ("available", "stale") or current.value is None:
            return MissionAssessment(
                mission_id=request.mission_id, policy_id=request.policy_id,
                scope=request.scope, as_of=request.as_of, status="unavailable",
                calculation_version=CALCULATION_VERSION, current_value=current,
                confidence=MissionConfidence(
                    "Insufficient", "accessible assets are unavailable"),
                limitations=("accessible assets are unavailable", *current.limitations),
                assumption_references=tuple(assumption_set.provenance))
        if current.unit_or_currency != self.policy.unit_or_currency:
            return MissionAssessment(
                mission_id=request.mission_id, policy_id=request.policy_id,
                scope=request.scope, as_of=request.as_of, status="unavailable",
                calculation_version=CALCULATION_VERSION, current_value=current,
                confidence=MissionConfidence(
                    "Insufficient", "assessment currency is incompatible"),
                limitations=(
                    "accessible-assets currency does not match the configured policy",
                ),
                assumption_references=tuple(assumption_set.provenance))

        forecasts = self.projection.project(current.value, request.as_of, inputs)
        base_eta = self.projection.eta(
            forecasts, self.policy.independent_threshold, "base")
        low_eta = self.projection.eta(
            forecasts, self.policy.independent_threshold, "low")
        complete = current.value >= self.policy.independent_threshold
        status, trajectory_state, trajectory_tone = self._schedule_assessment(
            complete, low_eta, base_eta, mission.target_date)

        trajectory = self._trajectory(request, inputs.history_months)
        prior_at = request.as_of - inputs.delta_v_lookback_days * DAY
        prior = self._metric(self.policy.target_metric, request, prior_at)
        prior_eta = None
        if prior.status in ("available", "stale") and prior.value is not None:
            prior_forecast = self.projection.project(prior.value, prior_at, inputs)
            prior_eta = self.projection.eta(
                prior_forecast, self.policy.independent_threshold, "base")

        delta_v = self._delta_v(
            prior_eta, base_eta, inputs.delta_v_lookback_days, complete)
        margin = self._mission_margin(
            current.value, prior.value, prior.status, prior_at,
            request.as_of, mission.target_date, base_eta)
        recommendations = self._recommendations(
            current.value, request.as_of, inputs, assumption_set, base_eta,
            current.unit_or_currency)
        phases = self._phase_assessments(
            current.value, forecasts, request.as_of)
        current_phase = next(
            (phase for phase in phases if phase.is_current), None)

        telemetry = (
            TelemetryItem(
                self._metric(
                    "finance.accessible_assets", request, request.as_of),
                "ACCESSIBLE ASSETS", "currency"),
            TelemetryItem(
                self._metric("finance.cash_flow", request, request.as_of),
                "NET CASH FLOW", "currency", "SINCE FIRST OBSERVATION"),
            TelemetryItem(
                self._metric(
                    "finance.liquidity_runway", request, request.as_of),
                "RUNWAY", "months"),
        )
        limitations = list(current.limitations)
        limitations.append(
            "Historical trajectory uses as_of-filtered V1 entity state; "
            "undated entity revisions are not reconstructed")
        implied_target = inputs.desired_annual_spending / inputs.withdrawal_rate
        if not math.isclose(
                implied_target, self.policy.independent_threshold,
                rel_tol=0.0, abs_tol=0.01):
            limitations.append(
                "Assumption-implied lifestyle capital differs from the configured "
                "Independent threshold; policy bands remain unchanged")
        if base_eta is None:
            limitations.append("base path does not enter Independent within the forecast horizon")

        # Quarterly points retain monthly ETA precision without sending an
        # unnecessarily dense series to presentation.
        sampled_forecast = tuple(
            point for index, point in enumerate(forecasts)
            if index % 3 == 0 or index == len(forecasts) - 1)
        if mission.target_date is None:
            confidence = MissionConfidence(
                "Insufficient", "mission target date is absent")
        elif current.status == "stale":
            confidence = MissionConfidence(
                "Provisional", "current evidence is stale")
        else:
            confidence = MissionConfidence(
                "Supported",
                "declared inputs and active assumptions support "
                "the deterministic assessment",
            )

        return MissionAssessment(
            mission_id=mission.id, policy_id=request.policy_id,
            scope=request.scope, as_of=request.as_of, status=status,
            calculation_version=CALCULATION_VERSION, current_value=current,
            mission_complete=complete, eta=base_eta,
            trajectory_state=trajectory_state,
            trajectory_tone=trajectory_tone,
            confidence=confidence,
            current_milestone=current_phase, milestones=phases,
            # Deprecated RFC-005 presentation fields, retained while
            # external consumers migrate to Core's trajectory vocabulary.
            flight_status_id=(
                trajectory_state.lower() if trajectory_state else "unavailable"),
            flight_status_label=trajectory_state or "Not Evaluable",
            phase=current_phase, phases=phases,
            mission_margin=margin, delta_v=delta_v,
            trajectory=trajectory, forecast=sampled_forecast,
            telemetry=telemetry, recommendations=recommendations,
            input_references=current.input_references,
            evidence_references=current.evidence_references,
            assumption_references=tuple(assumption_set.provenance),
            limitations=tuple(limitations),
            confidence_basis=(
                "LOW / BASE / HIGH SENSITIVITY ENVELOPE · NOT A PROBABILITY"),
            forecast_resolution="month",
            phase_thresholds=tuple(
                (phase.label, phase.lower_bound) for phase in self.policy.phases),
        )

    def _metric(self, metric_id: str, request: MissionAssessmentRequest,
                as_of: float) -> MetricResult:
        return self.metrics.dispatch(MetricRequest(
            metric_id=metric_id, scope=request.scope, as_of=as_of))

    def _trajectory(self, request: MissionAssessmentRequest,
                    history_months: int) -> tuple[TrajectoryPoint, ...]:
        points = []
        for offset in range(history_months, -1, -1):
            at = request.as_of - offset * MONTH
            result = self._metric(self.policy.target_metric, request, at)
            if result.status in ("available", "stale") and result.value is not None:
                points.append(TrajectoryPoint(at=at, value=result.value))
        return tuple(points)

    def _phase_assessments(
            self, current: float, forecast: tuple[ForecastPoint, ...],
            as_of: float) -> tuple[MissionMilestone, ...]:
        current_phase = self.policy.phase_for(current)
        phases = []
        for definition in self.policy.phases:
            if definition.upper_bound is None:
                completion = 1.0 if current >= definition.lower_bound else 0.0
                is_complete = current >= definition.lower_bound
            elif current >= definition.upper_bound:
                completion = 1.0
                is_complete = True
            elif current <= definition.lower_bound:
                completion = 0.0
                is_complete = False
            else:
                completion = (
                    (current - definition.lower_bound)
                    / (definition.upper_bound - definition.lower_bound)
                )
                is_complete = False
            estimated_at = None
            if definition.lower_bound > current:
                estimated_at = self.projection.eta(
                    forecast, definition.lower_bound, "base")
            phases.append(MissionMilestone(
                id=definition.id,
                label=definition.label,
                lower_bound=definition.lower_bound,
                upper_bound=definition.upper_bound,
                completion=max(0.0, min(1.0, completion)),
                order=definition.order,
                unit_or_currency=self.policy.unit_or_currency,
                is_current=definition.id == current_phase.id,
                is_complete=is_complete,
                completes_mission=definition.completes_mission,
                estimated_at=estimated_at,
                destination_direction="higher_is_better",
                destination_value=definition.lower_bound,
            ))
        return tuple(phases)

    @staticmethod
    def _status(complete: bool, low_eta: float | None,
                base_eta: float | None, target_date: float | None) -> str:
        """Deprecated RFC-005 scalar adapter; no new consumer should use it."""
        return FinancialIndependenceAssessor._schedule_assessment(
            complete, low_eta, base_eta, target_date)[0]

    @staticmethod
    def _schedule_assessment(
        complete: bool,
        low_eta: float | None,
        base_eta: float | None,
        target_date: float | None,
    ) -> tuple[str, str | None, str]:
        """Evaluate FI schedule policy into explicit independent outputs."""
        if complete:
            return "green", "Complete", "green"
        if target_date is None:
            return "unavailable", None, "none"
        if low_eta is not None and low_eta <= target_date:
            return "green", "Accelerated", "green"
        if base_eta is not None and base_eta <= target_date:
            return "amber", "Nominal", "amber"
        return "red", "Divergent", "red"

    @staticmethod
    def _months_from_days(days: float) -> int:
        magnitude = abs(days)
        if magnitude < MONTH_DAYS:
            return 0
        months = max(1, int(round(magnitude / MONTH_DAYS)))
        return months if days >= 0 else -months

    @staticmethod
    def _delta_v(prior_eta: float | None, current_eta: float | None,
                 lookback_days: int, complete: bool = False) -> DeltaV:
        if complete:
            return DeltaV(
                days=None, lookback_days=lookback_days,
                description="Mission complete; ETA movement no longer applies",
                months=None, direction=None)
        if prior_eta is None or current_eta is None:
            return DeltaV(
                days=None, lookback_days=lookback_days,
                description="Insufficient history for ETA movement",
                months=None, direction=None)
        days = (prior_eta - current_eta) / DAY
        direction = "accelerated" if days >= 0 else "delayed"
        months = FinancialIndependenceAssessor._months_from_days(days)
        return DeltaV(
            days=days, lookback_days=lookback_days,
            description=f"ETA {direction} over the last {lookback_days} days",
            months=months, direction=direction)

    def _mission_margin(self, current: float, prior_value: float | None,
                        prior_status: str, prior_at: float, as_of: float,
                        target_date: float | None,
                        eta: float | None) -> MissionMargin:
        buffer_days = (
            (target_date - eta) / DAY
            if target_date is not None and eta is not None else None)
        if target_date is None or target_date <= as_of \
                or prior_status not in ("available", "stale") \
                or prior_value is None:
            return MissionMargin(
                pace_percent=None, schedule_buffer_days=buffer_days,
                description="Insufficient schedule history for pace margin",
                state=self._margin_state(None, buffer_days))

        elapsed_months = max((as_of - prior_at) / MONTH, 1e-9)
        remaining_months = max((target_date - as_of) / MONTH, 1e-9)
        actual_pace = (current - prior_value) / elapsed_months
        required_pace = max(
            0.0, self.policy.independent_threshold - current) / remaining_months
        pace_percent = (
            None if required_pace <= 0 else
            (actual_pace - required_pace) / required_pace * 100.0)
        if pace_percent is None:
            description = "Independent threshold already reached"
        elif pace_percent >= 0:
            description = f"{abs(pace_percent):.1f}% above required pace"
        else:
            description = f"{abs(pace_percent):.1f}% below required pace"
        return MissionMargin(
            pace_percent=pace_percent, schedule_buffer_days=buffer_days,
            description=description,
            state=self._margin_state(pace_percent, buffer_days))

    @staticmethod
    def _margin_state(
        pace_percent: float | None,
        schedule_buffer_days: float | None,
    ) -> str | None:
        """Classify FI operating buffer from margin evidence alone."""
        available = tuple(
            value for value in (pace_percent, schedule_buffer_days)
            if value is not None
        )
        if not available:
            return None
        if len(available) == 2 and all(value > 0 for value in available):
            return "High Margin"
        if len(available) == 2 and all(value < 0 for value in available):
            return "Negative Margin"
        if all(value >= 0 for value in available):
            return "Adequate Margin"
        return "Low Margin"

    def _recommendations(self, current: float, as_of: float,
                         inputs: ProjectionInputs,
                         assumption_set: AssumptionSet,
                         base_eta: float | None,
                         unit_or_currency: str | None,
                         ) -> tuple[RecommendationAssessment, ...]:
        if base_eta is None:
            return ()
        candidates = []
        for scenario in self.finance.scenarios.values():
            if scenario.status != "active" \
                    or scenario.assumption_set_id != assumption_set.id:
                continue
            delta = scenario.adjustments.get("monthly_contribution_delta")
            if delta is None:
                continue
            if isinstance(delta, bool) or not isinstance(delta, (int, float)) \
                    or not math.isfinite(float(delta)) or delta <= 0:
                candidates.append(RecommendationAssessment(
                    action=scenario.name,
                    scenario_id=scenario.id,
                    estimated_delta_v_days=None,
                    status="unavailable",
                    action_type=(
                        scenario.action_type
                        if isinstance(scenario.action_type, str) else ""),
                    action_label=(
                        scenario.action_label
                        if isinstance(scenario.action_label, str) else ""),
                    adjustment_key="monthly_contribution_delta",
                    limitations=(
                        "structured Scenario adjustment is invalid",
                    ),
                    assumption_references=tuple(
                        [*assumption_set.provenance, *scenario.provenance]),
                ))
                continue
            delta = float(delta)
            structured = (
                scenario.action_type,
                scenario.action_label,
                scenario.unit_or_currency,
                scenario.cadence,
            )
            if not all(isinstance(value, str) and value.strip()
                       for value in structured):
                candidates.append(RecommendationAssessment(
                    action=scenario.name,
                    scenario_id=scenario.id,
                    estimated_delta_v_days=None,
                    status="unavailable",
                    action_type=scenario.action_type or "",
                    action_label=scenario.action_label or "",
                    amount=delta,
                    unit_or_currency=scenario.unit_or_currency,
                    cadence=scenario.cadence,
                    adjustment_key="monthly_contribution_delta",
                    limitations=(
                        "structured Scenario presentation metadata is incomplete",
                    ),
                    assumption_references=tuple(
                        [*assumption_set.provenance, *scenario.provenance]),
                ))
                continue
            if scenario.unit_or_currency != unit_or_currency:
                candidates.append(RecommendationAssessment(
                    action=scenario.name,
                    scenario_id=scenario.id,
                    estimated_delta_v_days=None,
                    status="unavailable",
                    action_type=scenario.action_type or "",
                    action_label=scenario.action_label or "",
                    amount=delta,
                    unit_or_currency=scenario.unit_or_currency,
                    cadence=scenario.cadence,
                    adjustment_key="monthly_contribution_delta",
                    limitations=(
                        "Scenario currency does not match the assessed metric currency",
                    ),
                    assumption_references=tuple(
                        [*assumption_set.provenance, *scenario.provenance]),
                ))
                continue
            try:
                projected = self.projection.project(
                    current, as_of, inputs, monthly_contribution_delta=delta)
            except ValueError:
                continue
            scenario_eta = self.projection.eta(
                projected, self.policy.independent_threshold, "base")
            if scenario_eta is None or scenario_eta >= base_eta:
                continue
            impact_days = (base_eta - scenario_eta) / DAY
            candidates.append(RecommendationAssessment(
                action=scenario.name, scenario_id=scenario.id,
                estimated_delta_v_days=impact_days,
                status="available",
                action_type=scenario.action_type or "",
                action_label=scenario.action_label or "",
                amount=delta,
                unit_or_currency=scenario.unit_or_currency,
                cadence=scenario.cadence,
                adjustment_key="monthly_contribution_delta",
                estimated_delta_v_months=self._months_from_days(impact_days),
                delta_v_direction="accelerated",
                assumption_references=tuple(
                    [*assumption_set.provenance, *scenario.provenance]),
            ))
        candidates.sort(
            key=lambda recommendation: (
                recommendation.status != "available",
                -(recommendation.estimated_delta_v_days or 0.0),
                recommendation.scenario_id,
            ))
        return tuple(candidates[:1])

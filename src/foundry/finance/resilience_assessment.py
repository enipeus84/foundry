"""Financial Resilience mission assessment (RFC-008).

This is a steady-state Finance mission. It composes published metrics,
attributed manual evidence, and a declared policy without calling another
assessor, a model, or an event writer. Completion is derived and reversible.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import math
from numbers import Real

from foundry.core.entities import EntityProjection
from foundry.core.metrics import MetricRegistry, MetricRequest, MetricResult
from foundry.core.mission_assessment import (
    InstrumentApplicability,
    MissionAssessment,
    MissionAssessmentRequest,
    MissionConfidence,
    MissionMargin,
    MissionMilestone,
    RecommendationAssessment,
    TelemetryItem,
)

from .entities import AssumptionSet, FinanceEntityProjection
from .resilience_evidence import (
    ResilienceEvidence,
    ResilienceEvidenceProjection,
)


POLICY_ID = "finance.financial_resilience.v1"
CALCULATION_VERSION = "resilience-v1"
TARGET_METRIC = "finance.liquidity_runway"
TARGET_MONTHS = 18.0
DAY = 86_400.0
MONTH = 365.2425 * DAY / 12.0

APPLICABILITY = InstrumentApplicability(
    eta="not_applicable",
    delta_v="not_applicable",
    trajectory="unavailable",
    forecast="not_applicable",
)


@dataclass(frozen=True)
class FinancialResilienceInputs:
    reserve_target_months: float
    secure_floor_months: float
    critical_floor_months: float
    income_concentration_limit: float
    commitment_horizon_months: int
    outflow_crosscheck_tolerance: float
    evidence_stale_after_days: int
    movement_lookback_days: int
    income_reduction_fraction: float
    income_reduction_months: int
    unexpected_expenditure: float
    rate_shock_monthly_cost: float
    temporary_unemployment_months: int

    @classmethod
    def from_assumption_set(
        cls,
        assumption_set: AssumptionSet,
    ) -> "FinancialResilienceInputs":
        required = {
            "reserve_target_months",
            "secure_floor_months",
            "critical_floor_months",
            "income_concentration_limit",
            "commitment_horizon_months",
            "outflow_crosscheck_tolerance",
            "evidence_stale_after_days",
            "movement_lookback_days",
            "income_reduction_fraction",
            "income_reduction_months",
            "unexpected_expenditure",
            "rate_shock_monthly_cost",
            "temporary_unemployment_months",
        }
        missing = sorted(required - assumption_set.assumptions.keys())
        if missing:
            raise ValueError(f"Assumption Set missing: {', '.join(missing)}")
        values = {}
        for key in sorted(required):
            value = assumption_set.assumptions[key]
            if isinstance(value, bool) or not isinstance(value, Real) \
                    or not math.isfinite(float(value)):
                raise ValueError(
                    f"Assumption Set {key} must be a finite number")
            values[key] = float(value)
        for key in (
            "commitment_horizon_months",
            "evidence_stale_after_days",
            "movement_lookback_days",
            "income_reduction_months",
            "temporary_unemployment_months",
        ):
            if not values[key].is_integer():
                raise ValueError(f"Assumption Set {key} must be an integer")
        result = cls(
            reserve_target_months=values["reserve_target_months"],
            secure_floor_months=values["secure_floor_months"],
            critical_floor_months=values["critical_floor_months"],
            income_concentration_limit=values[
                "income_concentration_limit"],
            commitment_horizon_months=int(
                values["commitment_horizon_months"]),
            outflow_crosscheck_tolerance=values[
                "outflow_crosscheck_tolerance"],
            evidence_stale_after_days=int(
                values["evidence_stale_after_days"]),
            movement_lookback_days=int(values["movement_lookback_days"]),
            income_reduction_fraction=values[
                "income_reduction_fraction"],
            income_reduction_months=int(
                values["income_reduction_months"]),
            unexpected_expenditure=values["unexpected_expenditure"],
            rate_shock_monthly_cost=values["rate_shock_monthly_cost"],
            temporary_unemployment_months=int(
                values["temporary_unemployment_months"]),
        )
        if result.reserve_target_months != TARGET_MONTHS:
            raise ValueError(
                "reserve_target_months must equal the approved "
                "18-month destination")
        if result.secure_floor_months != 6.0:
            raise ValueError(
                "secure_floor_months must equal the approved "
                "6-month operational floor")
        if not 0 <= result.critical_floor_months \
                < result.secure_floor_months:
            raise ValueError(
                "critical_floor_months must be non-negative and below "
                "the secure floor")
        if not 0 <= result.income_concentration_limit <= 1:
            raise ValueError(
                "income_concentration_limit must be between zero and one")
        if result.commitment_horizon_months != 12:
            raise ValueError(
                "commitment_horizon_months must equal the approved "
                "12-month horizon")
        if not 0 <= result.outflow_crosscheck_tolerance <= 1:
            raise ValueError(
                "outflow_crosscheck_tolerance must be between zero and one")
        if result.evidence_stale_after_days <= 0:
            raise ValueError(
                "evidence_stale_after_days must be positive")
        if result.movement_lookback_days <= 0:
            raise ValueError("movement_lookback_days must be positive")
        if not 0 <= result.income_reduction_fraction <= 1:
            raise ValueError(
                "income_reduction_fraction must be between zero and one")
        if result.unexpected_expenditure < 0 \
                or result.rate_shock_monthly_cost < 0 \
                or result.income_reduction_months < 0 \
                or result.temporary_unemployment_months < 0:
            raise ValueError("stress magnitudes must be non-negative")
        return result


@dataclass(frozen=True)
class FinancialResiliencePolicy:
    id: str = POLICY_ID
    target_metric: str = TARGET_METRIC
    destination_months: float = TARGET_MONTHS
    unit_or_currency: str = "months"


class FinancialResilienceAssessor:
    """Independent Finance provider for one household resilience mission."""

    def __init__(
        self,
        metrics: MetricRegistry,
        finance: FinanceEntityProjection,
        core: EntityProjection,
        evidence: ResilienceEvidenceProjection,
        policy: FinancialResiliencePolicy | None = None,
    ):
        self.metrics = metrics
        self.finance = finance
        self.core = core
        self.evidence = evidence
        self.policy = policy or FinancialResiliencePolicy()

    def owned_policy_ids(self) -> frozenset[str]:
        return frozenset({self.policy.id})

    def assess(self, request: MissionAssessmentRequest) -> MissionAssessment:
        mission = self.core.missions.get(request.mission_id)
        if mission is None:
            return self._unavailable(request, "mission does not exist")
        if mission.assessment_policy_id != self.policy.id:
            return self._unavailable(
                request, "mission is not declared against this policy")
        if mission.target_metric != self.policy.target_metric \
                or isinstance(mission.target_value, bool) \
                or not isinstance(mission.target_value, Real) \
                or not math.isfinite(float(mission.target_value)) \
                or float(mission.target_value) != self.policy.destination_months:
            return self._unavailable(
                request,
                "Mission destination must be 18 months of liquidity runway",
            )
        if mission.target_date is not None:
            return self._unavailable(
                request,
                "Financial Resilience is a steady-state mission and cannot "
                "declare a target date",
            )
        if request.scope.kind != "party":
            return self._unavailable(
                request, "Financial Resilience requires a party scope")
        household = self.core.parties.get(request.scope.id)
        if household is None or household.party_type != "household" \
                or household.status != "active":
            return self._unavailable(
                request, "active household scope not found")
        reporting_currency = household.attributes.get("reporting_currency")
        if not isinstance(reporting_currency, str) \
                or not reporting_currency.strip():
            return self._unavailable(
                request, "household reporting currency not found")

        assumption_set = self.finance.assumption_sets.get(
            mission.assumption_set_id or "")
        if assumption_set is None or assumption_set.status != "active":
            return self._unavailable(
                request, "active resilience Assumption Set not found")
        try:
            inputs = FinancialResilienceInputs.from_assumption_set(
                assumption_set)
        except (TypeError, ValueError) as exc:
            return self._unavailable(request, str(exc))

        runway = self.metrics.dispatch(MetricRequest(
            TARGET_METRIC,
            request.scope,
            request.as_of,
        ))
        runway_value = self._metric_value(
            runway, TARGET_METRIC, request, "months")
        if runway_value is None:
            return self._unavailable(
                request, "liquidity runway is unavailable")
        current = replace(runway, generated_at=request.as_of)

        metric_results = {}
        for metric_id, label in (
            (
                "finance.essential_outflow_monthly",
                "essential-outflow basis",
            ),
            (
                "finance.emergency_reserve_target",
                "emergency reserve target",
            ),
            ("finance.emergency_reserve_gap", "emergency reserve gap"),
            ("finance.deployable_surplus", "deployable surplus"),
        ):
            result = self.metrics.dispatch(MetricRequest(
                metric_id,
                request.scope,
                request.as_of,
                assumption_set_id=assumption_set.id,
            ))
            if self._metric_value(
                    result, metric_id, request, "GBP") is None:
                if metric_id == "finance.deployable_surplus":
                    return self._partial_assessment(
                        request=request,
                        assumption_set=assumption_set,
                        current=current,
                        outflow=metric_results["finance.essential_outflow_monthly"],
                        target=metric_results["finance.emergency_reserve_target"],
                        gap=metric_results["finance.emergency_reserve_gap"],
                        reason=f"{label} is unavailable",
                    )
                return self._unavailable(
                    request, f"{label} is unavailable")
            metric_results[metric_id] = replace(
                result, generated_at=request.as_of)

        outflow = metric_results["finance.essential_outflow_monthly"]
        target = metric_results["finance.emergency_reserve_target"]
        gap = metric_results["finance.emergency_reserve_gap"]
        deployable = metric_results["finance.deployable_surplus"]
        outflow_value = float(outflow.value)
        target_value = float(target.value)
        gap_value = float(gap.value)
        deployable_value = float(deployable.value)
        liquid_holdings = target_value - gap_value

        records = self.evidence.for_party(request.scope.id, request.as_of)
        future_records = self.evidence.future_for(
            request.scope.id, request.as_of)
        income_records = self.evidence.latest_by_source(
            request.scope.id,
            "income_source_monthly",
            request.as_of,
        )
        commitment_records = self._commitments(
            records, request.as_of, inputs.commitment_horizon_months)

        bands = []
        factor_telemetry = []
        limitations = [
            "Protection and insurance are not assessed in Financial "
            "Resilience V1; Mission Confidence is capped at Supported.",
            "Affordability is not assessed because verified future income "
            "and spending capacity are outside this assessment.",
            "Essential outflow is the transaction-derived average monthly "
            "essential and committed outflow used by liquidity runway.",
            "Adverse stresses are deterministic arithmetic sensitivities, "
            "not probabilities.",
            "Historical trajectory is unavailable because the current "
            "averaging-window denominator cannot support an honest "
            "like-for-like history.",
        ]
        for result in metric_results.values():
            limitations.extend(result.limitations)

        reserve_band = self._reserve_band(runway_value)
        bands.append(("reserve coverage", reserve_band))
        factor_telemetry.append(TelemetryItem(
            current, "RESERVE COVERAGE", "months",
            f"BAND {reserve_band} · {runway_value:.1f} MONTHS",
            display_group="MISSION MARGIN EVIDENCE",
        ))

        concentration = self.metrics.dispatch(MetricRequest(
            "finance.employer_concentration",
            request.scope,
            request.as_of,
        ))
        concentration_value = self._metric_value(
            concentration,
            "finance.employer_concentration",
            request,
            None,
        )
        if income_records and concentration_value is not None:
            income_band = self._income_band(
                concentration_value,
                len(income_records),
                runway_value,
                inputs.income_concentration_limit,
            )
            bands.append(("income concentration", income_band))
            income_refs = tuple(sorted({
                *concentration.input_references,
                *(record.event_id for record in income_records),
            }))
            factor_telemetry.append(TelemetryItem(
                self._derived_metric(
                    "finance.resilience_income_concentration",
                    concentration_value,
                    None,
                    request,
                    income_refs,
                    tuple(record.event_id for record in income_records),
                    tuple(assumption_set.provenance),
                ),
                "INCOME CONCENTRATION",
                "percent",
                f"BAND {income_band} · {len(income_records)} DECLARED "
                "SOURCE(S)",
                display_group="MISSION MARGIN EVIDENCE",
            ))
        else:
            if not income_records:
                limitations.extend((
                    "Income-source concentration is excluded from Mission "
                    "Margin because attributable income-source evidence is "
                    "not available.",
                    "Income-reduction stress is excluded because "
                    "attributable income-source evidence is not available.",
                ))
            else:
                limitations.append(
                    "Income-source concentration is excluded from Mission "
                    "Margin because employer-concentration evidence is "
                    "not available.")

        commitment_total = sum(
            float(record.value) for record in commitment_records
            if self._numeric_evidence(record) is not None)
        if commitment_records and commitment_total > 0:
            # Commitment factors answer whether declared obligations are
            # funded by liquid holdings. Reserve coverage separately answers
            # whether the full 18-month destination is met; M4 remains the
            # conservative stock available only above that destination.
            coverage = liquid_holdings / commitment_total
            commitment_band = (
                3 if coverage >= 2 else
                2 if coverage >= 1 else
                1 if coverage >= .5 else 0
            )
            headroom_after_commitments = (
                liquid_holdings - commitment_total)
            headroom_band = self._headroom_band(
                headroom_after_commitments, target_value)
            evidence_refs = tuple(
                record.event_id for record in commitment_records)
            input_refs = tuple(sorted({
                *target.input_references,
                *gap.input_references,
            }))
            bands.extend((
                ("commitment coverage", commitment_band),
                ("obligation headroom", headroom_band),
            ))
            factor_telemetry.extend((
                TelemetryItem(
                    self._derived_metric(
                        "finance.resilience_commitment_coverage",
                        coverage,
                        None,
                        request,
                        input_refs,
                        evidence_refs,
                        tuple(assumption_set.provenance),
                    ),
                    "COMMITMENT COVERAGE",
                    "number",
                    f"BAND {commitment_band} · {coverage:.2f}×",
                    display_group="MISSION MARGIN EVIDENCE",
                ),
                TelemetryItem(
                    self._derived_metric(
                        "finance.resilience_obligation_headroom",
                        headroom_after_commitments,
                        reporting_currency,
                        request,
                        input_refs,
                        evidence_refs,
                        tuple(assumption_set.provenance),
                    ),
                    "OBLIGATION HEADROOM",
                    "currency",
                    f"BAND {headroom_band}",
                    display_group="MISSION MARGIN EVIDENCE",
                ),
            ))
        else:
            headroom_after_commitments = liquid_holdings
            limitations.append(
                "Commitment coverage and obligation headroom are excluded "
                "from Mission Margin because no positive dated near-term "
                "commitment is recorded.")

        margin = self._mission_margin(bands, runway_value)
        complete = runway_value >= self.policy.destination_months
        trajectory_state = self._trajectory_state(
            runway_value,
            gap_value,
            deployable_value,
            headroom_after_commitments,
            bool(commitment_records),
            bands,
            inputs,
        )
        status, tone = self._status(trajectory_state)
        milestones = self._milestones(runway_value)
        current_milestone = next(
            milestone for milestone in milestones
            if milestone.is_current)

        confidence, confidence_reasons = self._confidence(
            request,
            inputs,
            (
                current, outflow, target, gap, deployable, concentration,
            ),
            tuple(
                record for record in records
                if record.field != "protection_declaration"),
            bool(income_records),
            bool(commitment_records),
            future_records,
            self.evidence.has_invalid_for(
                request.scope.id, request.as_of),
        )
        limitations.extend(confidence_reasons)

        telemetry = (
            *factor_telemetry,
            TelemetryItem(outflow, "ESSENTIAL OUTFLOW", "currency",
                          "AVERAGE MONTHLY BASIS",
                          display_group="RESERVE REQUIREMENTS"),
            TelemetryItem(target, "EMERGENCY RESERVE TARGET", "currency",
                          "FULL 18-MONTH DESTINATION",
                          display_group="RESERVE REQUIREMENTS"),
            TelemetryItem(gap, "EMERGENCY RESERVE GAP", "currency",
                          "SIGNED SHORTFALL",
                          display_region="essential"),
            TelemetryItem(deployable, "DEPLOYABLE SURPLUS", "currency",
                          "STOCK ABOVE FULL RESERVE",
                          display_region="essential"),
            *(replace(item, display_group="STRESS ANALYSIS")
              for item in self._stress_telemetry(
                  request,
                  inputs,
                  liquid_holdings,
                  outflow_value,
                  income_records,
                  tuple(sorted({
                      *outflow.input_references,
                      *gap.input_references,
                  })),
                  tuple(record.event_id for record in income_records),
                  tuple(assumption_set.provenance),
              )),
        )
        recommendations = self._recommendations(
            request,
            assumption_set,
            runway_value,
            tuple(sorted({
                *current.input_references,
                *outflow.input_references,
            })),
            tuple(sorted({
                *current.evidence_references,
                *outflow.evidence_references,
            })),
        )

        input_refs = tuple(sorted({
            *mission.provenance,
            *mission.history,
            *household.provenance,
            *household.history,
            *(ref for result in (
                current, outflow, target, gap, deployable)
              for ref in result.input_references),
        }))
        evidence_refs = tuple(sorted({
            *(record.event_id for record in records),
            *(ref for result in (
                outflow, target, gap, deployable)
              for ref in result.evidence_references),
        }))
        return MissionAssessment(
            mission_id=mission.id,
            policy_id=request.policy_id,
            scope=request.scope,
            as_of=request.as_of,
            status=status,
            calculation_version=CALCULATION_VERSION,
            current_value=current,
            mission_complete=complete,
            eta=None,
            trajectory_state=trajectory_state,
            trajectory_tone=tone,
            confidence=confidence,
            current_milestone=current_milestone,
            milestones=milestones,
            mission_margin=margin,
            delta_v=None,
            trajectory=(),
            forecast=(),
            telemetry=tuple(telemetry),
            recommendations=recommendations,
            input_references=input_refs,
            evidence_references=evidence_refs,
            assumption_references=tuple(assumption_set.provenance),
            limitations=tuple(dict.fromkeys(limitations)),
            confidence_basis=(
                f"{confidence.state.upper()} · ATTRIBUTABLE EVIDENCE · "
                "PROTECTION NOT ASSESSED · V1 CAP SUPPORTED"),
            forecast_resolution="month",
            applicability=APPLICABILITY,
        )

    def _unavailable(
        self,
        request: MissionAssessmentRequest,
        reason: str,
    ) -> MissionAssessment:
        return replace(
            MissionAssessment.unavailable(
                request, reason, CALCULATION_VERSION),
            applicability=APPLICABILITY,
        )

    def _partial_assessment(
        self,
        *,
        request: MissionAssessmentRequest,
        assumption_set,
        current: MetricResult,
        outflow: MetricResult,
        target: MetricResult,
        gap: MetricResult,
        reason: str,
    ) -> MissionAssessment:
        runway_value = float(current.value)
        milestones = self._milestones(runway_value)
        current_milestone = next(
            milestone for milestone in milestones
            if milestone.is_current)
        confidence = MissionConfidence("Provisional", reason)
        return MissionAssessment(
            mission_id=request.mission_id,
            policy_id=request.policy_id,
            scope=request.scope,
            as_of=request.as_of,
            status="none",
            completeness="partial",
            calculation_version=CALCULATION_VERSION,
            current_value=current,
            mission_complete=runway_value >= self.policy.destination_months,
            eta=None,
            trajectory_state=None,
            trajectory_tone="none",
            confidence=confidence,
            current_milestone=current_milestone,
            milestones=milestones,
            mission_margin=None,
            delta_v=None,
            trajectory=(),
            forecast=(),
            telemetry=(
                TelemetryItem(
                    current, "RESERVE COVERAGE", "months",
                    f"VISIBLE RUNWAY · {runway_value:.1f} MONTHS",
                    display_region="essential",
                ),
                TelemetryItem(
                    outflow, "ESSENTIAL OUTFLOW", "currency",
                    "AVERAGE MONTHLY BASIS",
                    display_group="RESERVE REQUIREMENTS",
                ),
                TelemetryItem(
                    target, "EMERGENCY RESERVE TARGET", "currency",
                    "FULL 18-MONTH DESTINATION",
                    display_group="RESERVE REQUIREMENTS",
                ),
                TelemetryItem(
                    gap, "EMERGENCY RESERVE GAP", "currency",
                    "SIGNED SHORTFALL",
                    display_region="essential",
                ),
            ),
            recommendations=(),
            input_references=tuple(sorted({
                *current.input_references,
                *outflow.input_references,
                *target.input_references,
                *gap.input_references,
            })),
            evidence_references=tuple(sorted({
                *current.evidence_references,
                *outflow.evidence_references,
                *target.evidence_references,
                *gap.evidence_references,
            })),
            assumption_references=tuple(assumption_set.provenance),
            limitations=(reason,),
            confidence_basis=reason,
            forecast_resolution="month",
            applicability=APPLICABILITY,
        )

    @staticmethod
    def _metric_value(
        result: MetricResult,
        metric_id: str,
        request: MissionAssessmentRequest,
        unit: str | None,
    ) -> float | None:
        value = result.value
        if result.metric_id != metric_id \
                or result.scope != request.scope \
                or result.as_of != request.as_of \
                or result.status not in ("available", "stale") \
                or (unit is not None and result.unit_or_currency != unit) \
                or isinstance(value, bool) \
                or not isinstance(value, Real) \
                or not math.isfinite(float(value)):
            return None
        return float(value)

    @staticmethod
    def _commitments(
        records: tuple[ResilienceEvidence, ...],
        as_of: float,
        horizon_months: int,
    ) -> tuple[ResilienceEvidence, ...]:
        horizon = as_of + horizon_months * MONTH
        return tuple(
            record for record in records
            if record.field == "near_term_commitment"
            and record.due_at is not None
            and as_of <= record.due_at <= horizon
        )

    @staticmethod
    def _numeric_evidence(
        record: ResilienceEvidence,
    ) -> float | None:
        value = record.value
        if isinstance(value, bool) or not isinstance(value, Real) \
                or not math.isfinite(float(value)):
            return None
        return float(value)

    @staticmethod
    def _reserve_band(runway: float) -> int:
        return 3 if runway >= 18 else 2 if runway >= 6 \
            else 1 if runway >= 3 else 0

    @staticmethod
    def _income_band(
        concentration: float,
        source_count: int,
        runway: float,
        limit: float,
    ) -> int:
        if source_count <= 1 and runway < 3:
            return 0
        if concentration > limit:
            return 1
        if source_count >= 2:
            return 3
        return 2

    @staticmethod
    def _headroom_band(headroom: float, target: float) -> int:
        if headroom >= 0:
            return 3
        shortfall = abs(headroom)
        return (
            2 if shortfall <= target * .1 else
            1 if shortfall <= target * .5 else 0
        )

    @staticmethod
    def _mission_margin(
        bands: list[tuple[str, int]],
        runway: float,
    ) -> MissionMargin:
        values = tuple(value for _, value in bands)
        minimum = min(values)
        if minimum == 0:
            state = "Negative Margin"
        elif minimum == 1:
            state = "Low Margin"
        elif all(value == 3 for value in values):
            state = "High Margin"
        else:
            state = "Adequate Margin"
        description = ", ".join(
            f"{label} band {value}" for label, value in bands)
        return MissionMargin(
            pace_percent=None,
            schedule_buffer_days=None,
            description=description,
            state=state,
            label="RUNWAY",
            value=runway,
            unit_or_currency="months",
            format_kind="months",
        )

    @staticmethod
    def _trajectory_state(
        runway: float,
        gap: float,
        deployable: float,
        headroom: float,
        has_commitments: bool,
        bands: list[tuple[str, int]],
        inputs: FinancialResilienceInputs,
    ) -> str:
        if runway < inputs.critical_floor_months \
                or (has_commitments and headroom < 0):
            return "Critical"
        if runway >= inputs.reserve_target_months \
                and all(value > 0 for _, value in bands):
            return "Complete"
        if gap <= 0:
            return "Nominal"
        if deployable >= 0:
            return "Constrained"
        return "Divergent"

    @staticmethod
    def _status(trajectory_state: str) -> tuple[str, str]:
        if trajectory_state in ("Complete", "Nominal"):
            return "green", "green"
        if trajectory_state == "Constrained":
            return "amber", "amber"
        return "red", "red"

    @staticmethod
    def _milestones(runway: float) -> tuple[MissionMilestone, ...]:
        definitions = (
            ("exposed", "Exposed", 0.0, 1.0, False),
            ("fragile", "Fragile", 1.0, 3.0, False),
            ("buffered", "Buffered", 3.0, 6.0, False),
            ("secure", "Secure", 6.0, 18.0, False),
            ("fortified", "Fortified", 18.0, None, True),
        )
        current_index = (
            0
            if runway < definitions[0][3]
            else next(
                index for index, (_, _, lower, upper, _) in
                enumerate(definitions)
                if runway >= lower and (upper is None or runway < upper)
            )
        )
        milestones = []
        for order, (
            identifier, label, lower, upper, completes
        ) in enumerate(definitions):
            is_current = order == current_index
            if upper is None:
                completion = 1.0 if runway >= lower else 0.0
            else:
                completion = max(
                    0.0, min(1.0, (runway - lower) / (upper - lower)))
            milestones.append(MissionMilestone(
                identifier,
                label,
                lower,
                upper,
                completion,
                order=order,
                unit_or_currency="months",
                is_current=is_current,
                is_complete=runway >= (upper if upper is not None else lower),
                completes_mission=completes,
                destination_direction="higher_is_better",
                destination_value=18.0 if completes else lower,
            ))
        return tuple(milestones)

    def _confidence(
        self,
        request: MissionAssessmentRequest,
        inputs: FinancialResilienceInputs,
        metrics: tuple[MetricResult, ...],
        records: tuple[ResilienceEvidence, ...],
        has_income: bool,
        has_commitments: bool,
        future_records: tuple[ResilienceEvidence, ...],
        invalid: bool,
    ) -> tuple[MissionConfidence, tuple[str, ...]]:
        reasons = []
        if any(result.status == "stale" for result in metrics):
            reasons.append("Contributing metric evidence is stale.")
        if any(
            result.status not in ("available", "stale")
            for result in metrics
        ):
            reasons.append(
                "A contributing Mission Margin metric is unavailable.")
        if records and min(record.confidence for record in records) < .9:
            reasons.append(
                "Contributing manual evidence carries provisional "
                "confidence.")
        if any(
            request.as_of - record.effective_at
            > inputs.evidence_stale_after_days * DAY
            for record in records
        ):
            reasons.append("Contributing manual evidence is stale.")
        if not has_income:
            reasons.append("Income-source evidence is excluded.")
        if not has_commitments:
            reasons.append("Near-term commitment evidence is excluded.")
        if future_records:
            reasons.append(
                "Future-dated resilience evidence exists and is excluded "
                "from this assessment.")
        if invalid:
            reasons.append(
                "Malformed resilience evidence is quarantined and visible.")
        if any(
            "differs from the transaction-derived basis" in limitation
            for result in metrics
            for limitation in result.limitations
        ):
            reasons.append(
                "The declared essential-outflow cross-check diverges from "
                "the transaction-derived basis.")
        if reasons:
            return (
                MissionConfidence(
                    "Provisional",
                    "attributable evidence is incomplete, stale, or "
                    "provisional; protection remains not assessed",
                ),
                tuple(reasons),
            )
        return (
            MissionConfidence(
                "Supported",
                "fresh attributable evidence supports the assessment; "
                "Established is unavailable while protection is not assessed",
            ),
            (),
        )

    @staticmethod
    def _derived_metric(
        metric_id: str,
        value: float,
        unit: str | None,
        request: MissionAssessmentRequest,
        input_refs: tuple[str, ...],
        evidence_refs: tuple[str, ...],
        assumption_refs: tuple[str, ...],
    ) -> MetricResult:
        return MetricResult(
            metric_id,
            value,
            unit,
            request.scope,
            request.as_of,
            "available",
            CALCULATION_VERSION,
            input_references=input_refs,
            evidence_references=evidence_refs,
            assumption_references=assumption_refs,
            generated_at=request.as_of,
            confidence_or_quality="deterministic",
        )

    def _stress_telemetry(
        self,
        request: MissionAssessmentRequest,
        inputs: FinancialResilienceInputs,
        liquid: float,
        outflow: float,
        income_records: tuple[ResilienceEvidence, ...],
        input_refs: tuple[str, ...],
        evidence_refs: tuple[str, ...],
        assumption_refs: tuple[str, ...],
    ) -> tuple[TelemetryItem, ...]:
        monthly_income = sum(
            float(record.value) for record in income_records
            if self._numeric_evidence(record) is not None)
        reduced_income = (
            monthly_income * (1.0 - inputs.income_reduction_fraction))
        reduced_income_shortfall = max(0.0, outflow - reduced_income)
        unemployment_shortfall = outflow
        stresses = [
            (
                "finance.resilience_stress_income_reduction",
                max(
                    0.0,
                    liquid
                    - reduced_income_shortfall
                    * inputs.income_reduction_months,
                ) / outflow,
                f"RUNWAY · {inputs.income_reduction_months}-MONTH "
                "DECLARED INCOME REDUCTION",
            )
        ] if income_records else []
        stresses.extend((
            (
                "finance.resilience_stress_unexpected_expenditure",
                max(0.0, liquid - inputs.unexpected_expenditure) / outflow,
                "RUNWAY · UNEXPECTED EXPENDITURE",
            ),
            (
                "finance.resilience_stress_rate_shock",
                liquid / (outflow + inputs.rate_shock_monthly_cost),
                "RUNWAY · RATE SHOCK",
            ),
            (
                "finance.resilience_stress_temporary_unemployment",
                max(
                    0.0,
                    liquid
                    - unemployment_shortfall
                    * inputs.temporary_unemployment_months,
                ) / outflow,
                f"RUNWAY · {inputs.temporary_unemployment_months}-MONTH "
                "INCOME LOSS",
            ),
        ))
        return tuple(
            TelemetryItem(
                self._derived_metric(
                    metric_id,
                    value,
                    "months",
                    request,
                    input_refs,
                    evidence_refs,
                    assumption_refs,
                ),
                label,
                "months",
                "DETERMINISTIC STRESS · NOT A PROBABILITY",
            )
            for metric_id, value, label in stresses
        )

    def _recommendations(
        self,
        request: MissionAssessmentRequest,
        assumption_set: AssumptionSet,
        runway: float,
        input_refs: tuple[str, ...],
        evidence_refs: tuple[str, ...],
    ) -> tuple[RecommendationAssessment, ...]:
        candidates = []
        for scenario in self.finance.scenarios.values():
            if scenario.status != "active" \
                    or scenario.assumption_set_id != assumption_set.id:
                continue
            amount = scenario.adjustments.get(
                "monthly_reserve_contribution")
            structured = (
                scenario.action_type,
                scenario.action_label,
                scenario.unit_or_currency,
                scenario.cadence,
            )
            if isinstance(amount, bool) \
                    or not isinstance(amount, Real) \
                    or not math.isfinite(float(amount)) \
                    or amount <= 0 \
                    or not all(
                        isinstance(value, str) and value.strip()
                        for value in structured) \
                    or scenario.unit_or_currency != "GBP" \
                    or scenario.cadence != "month":
                continue
            action = (
                f"Maintain £{float(amount):,.0f} per month in the emergency "
                f"reserve; current liquidity runway is {runway:.1f} months "
                "against Financial Resilience's declared 18-month reserve "
                f"destination. Each declared contribution improves the "
                f"reserve position by £{float(amount):,.0f}. Preserve the "
                "full reserve before deploying capital elsewhere.")
            candidates.append(RecommendationAssessment(
                action=action,
                scenario_id=scenario.id,
                estimated_delta_v_days=None,
                action_type=scenario.action_type or "",
                action_label=scenario.action_label or "",
                amount=float(amount),
                unit_or_currency=scenario.unit_or_currency,
                cadence=scenario.cadence,
                adjustment_key="monthly_reserve_contribution",
                estimated_delta_v_months=None,
                delta_v_direction=None,
                assumption_references=tuple(sorted({
                    *assumption_set.provenance,
                    *scenario.provenance,
                })),
                evidence_references=tuple(sorted({
                    *input_refs,
                    *evidence_refs,
                })),
            ))
        return tuple(candidates[:1])

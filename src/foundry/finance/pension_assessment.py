"""Pension Independence mission assessment (RFC-009).

The provider composes observed pension metrics, attributed declarations and a
versioned Finance policy. It is deterministic, read-only, independently
executable, and keeps observations separate from deterministic sensitivities.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import math
from numbers import Real

from foundry.core.entities import EntityProjection
from foundry.core.identity import age_years
from foundry.core.metrics import MetricRegistry, MetricRequest, MetricResult
from foundry.core.mission_assessment import (
    DeltaV,
    ForecastPoint,
    InstrumentApplicability,
    MissionAssessment,
    MissionAssessmentRequest,
    MissionConfidence,
    MissionMargin,
    MissionMilestone,
    RecommendationAssessment,
    TelemetryItem,
)

from . import vocab
from .aggregation import FinanceAggregationService
from .entities import AssumptionSet, FinanceEntityProjection
from .pension_evidence import PensionEvidenceProjection, RATE_FIELDS
from .pension_projection import PensionProviderProjectionProjection


POLICY_ID = "finance.pension_independence.v1"
CALCULATION_VERSION = "pension-v1"
TARGET_METRIC = "finance.pension_wealth"
DAY = 86_400.0
MONTH = 365.2425 * DAY / 12.0
MILESTONE_LABELS = (
    ("dependent", "Dependent"),
    ("foundation", "Foundation"),
    ("building", "Building"),
    ("approaching", "Approaching"),
    ("pension-independent", "Pension Independent"),
)


@dataclass(frozen=True)
class PensionIndependenceInputs:
    required_retirement_income_annual: float
    low_real_return: float
    base_real_return: float
    high_real_return: float
    sustainable_withdrawal_rate: float
    assumed_annual_fee_percent: float
    contribution_stale_after_days: int
    valuation_stale_after_days: int
    evidence_crosscheck_tolerance: float
    accelerated_threshold_months: int
    divergent_floor_fraction: float
    milestone_fractions: tuple[float, float, float, float]
    surplus_high_fraction: float
    shortfall_low_fraction: float
    sp_reliance_limits: tuple[float, float, float]
    delta_v_lookback_days: int
    recommendation_liquidity_floor_months: float
    planning_age: float | None = None

    @classmethod
    def from_assumption_set(
        cls,
        assumption_set: AssumptionSet,
    ) -> "PensionIndependenceInputs":
        required = {
            "required_retirement_income_annual",
            "low_real_return",
            "base_real_return",
            "high_real_return",
            "sustainable_withdrawal_rate",
            "assumed_annual_fee_percent",
            "contribution_stale_after_days",
            "valuation_stale_after_days",
            "evidence_crosscheck_tolerance",
            "accelerated_threshold_months",
            "divergent_floor_fraction",
            "milestone_fraction_1",
            "milestone_fraction_2",
            "milestone_fraction_3",
            "milestone_fraction_4",
            "surplus_high_fraction",
            "shortfall_low_fraction",
            "sp_reliance_low_fraction",
            "sp_reliance_mid_fraction",
            "sp_reliance_high_fraction",
            "delta_v_lookback_days",
            "recommendation_liquidity_floor_months",
        }
        missing = sorted(required - assumption_set.assumptions.keys())
        if missing:
            raise ValueError(f"Assumption Set missing: {', '.join(missing)}")
        values = {}
        for key in sorted(required | {"planning_age"}):
            if key not in assumption_set.assumptions:
                continue
            value = assumption_set.assumptions[key]
            if isinstance(value, bool) or not isinstance(value, Real) \
                    or not math.isfinite(float(value)):
                raise ValueError(
                    f"Assumption Set {key} must be a finite number")
            values[key] = float(value)
        for key in (
            "contribution_stale_after_days",
            "valuation_stale_after_days",
            "accelerated_threshold_months",
            "delta_v_lookback_days",
        ):
            if not values[key].is_integer():
                raise ValueError(f"Assumption Set {key} must be an integer")
        result = cls(
            required_retirement_income_annual=values[
                "required_retirement_income_annual"],
            low_real_return=values["low_real_return"],
            base_real_return=values["base_real_return"],
            high_real_return=values["high_real_return"],
            sustainable_withdrawal_rate=values[
                "sustainable_withdrawal_rate"],
            assumed_annual_fee_percent=values[
                "assumed_annual_fee_percent"],
            contribution_stale_after_days=int(
                values["contribution_stale_after_days"]),
            valuation_stale_after_days=int(
                values["valuation_stale_after_days"]),
            evidence_crosscheck_tolerance=values[
                "evidence_crosscheck_tolerance"],
            accelerated_threshold_months=int(
                values["accelerated_threshold_months"]),
            divergent_floor_fraction=values["divergent_floor_fraction"],
            milestone_fractions=tuple(
                values[f"milestone_fraction_{index}"]
                for index in range(1, 5)
            ),
            surplus_high_fraction=values["surplus_high_fraction"],
            shortfall_low_fraction=values["shortfall_low_fraction"],
            sp_reliance_limits=(
                values["sp_reliance_low_fraction"],
                values["sp_reliance_mid_fraction"],
                values["sp_reliance_high_fraction"],
            ),
            delta_v_lookback_days=int(values["delta_v_lookback_days"]),
            recommendation_liquidity_floor_months=values[
                "recommendation_liquidity_floor_months"],
            planning_age=values.get("planning_age"),
        )
        if not 0 <= result.low_real_return \
                <= result.base_real_return <= result.high_real_return:
            raise ValueError(
                "real returns must be ordered Conservative <= Expected "
                "<= Optimistic and non-negative")
        if not 0 < result.sustainable_withdrawal_rate <= 1:
            raise ValueError(
                "sustainable_withdrawal_rate must be between zero and one")
        if not 0 <= result.assumed_annual_fee_percent < 1:
            raise ValueError(
                "assumed_annual_fee_percent must be below one")
        if result.contribution_stale_after_days <= 0 \
                or result.valuation_stale_after_days <= 0:
            raise ValueError("evidence freshness bounds must be positive")
        if not 0 <= result.evidence_crosscheck_tolerance <= 1:
            raise ValueError(
                "evidence_crosscheck_tolerance must be between zero and one")
        if result.accelerated_threshold_months < 0 \
                or result.delta_v_lookback_days <= 0:
            raise ValueError("schedule thresholds must be non-negative")
        if not 0 <= result.divergent_floor_fraction <= 1:
            raise ValueError(
                "divergent_floor_fraction must be between zero and one")
        if result.milestone_fractions != (.25, .5, .75, 1.0):
            raise ValueError(
                "milestone fractions must equal the approved "
                "25/50/75/100 percent bands")
        if not 0 <= result.shortfall_low_fraction \
                <= result.surplus_high_fraction:
            raise ValueError("margin surplus/shortfall bands are invalid")
        if not 0 < result.sp_reliance_limits[0] \
                < result.sp_reliance_limits[1] \
                < result.sp_reliance_limits[2] <= 1:
            raise ValueError("State Pension reliance limits are invalid")
        if result.recommendation_liquidity_floor_months < 0:
            raise ValueError(
                "recommendation liquidity floor must be non-negative")
        if result.planning_age is not None \
                and not 0 < result.planning_age <= 120:
            raise ValueError("planning_age must be an age in years")
        return result


@dataclass(frozen=True)
class PensionIndependencePolicy:
    id: str = POLICY_ID
    target_metric: str = TARGET_METRIC
    unit_or_currency: str = "GBP"


class PensionIndependenceAssessor:
    """Independent Finance provider for Pension Independence."""

    def __init__(
        self,
        metrics: MetricRegistry,
        finance: FinanceEntityProjection,
        core: EntityProjection,
        evidence: PensionEvidenceProjection,
        policy: PensionIndependencePolicy | None = None,
        provider_projections: PensionProviderProjectionProjection | None = None,
    ):
        self.metrics = metrics
        self.finance = finance
        self.core = core
        self.evidence = evidence
        self.provider_projections = provider_projections
        self.basis = FinanceAggregationService(finance, core)
        self.policy = policy or PensionIndependencePolicy()

    def owned_policy_ids(self) -> frozenset[str]:
        return frozenset({self.policy.id})

    def assess(self, request: MissionAssessmentRequest) -> MissionAssessment:
        mission = self.core.missions.get(request.mission_id)
        if mission is None:
            return self._unavailable(request, "mission does not exist")
        if mission.assessment_policy_id != self.policy.id:
            return self._unavailable(
                request, "mission is not declared against this policy")
        if mission.target_metric != self.policy.target_metric:
            return self._unavailable(
                request, "Mission target metric must be pension wealth")
        if mission.target_value is not None or mission.target_date is not None:
            return self._unavailable(
                request,
                "Pension Independence derives its destination and planning "
                "point from declared evidence, not Mission scalar targets.",
            )
        members, scope_error = self._participants(request)
        if scope_error is not None:
            return self._unavailable(request, scope_error)
        assumption_set = self.finance.assumption_sets.get(
            mission.assumption_set_id or "")
        if assumption_set is None or assumption_set.status != "active":
            return self._unavailable(
                request, "active pension Assumption Set not found")
        try:
            inputs = PensionIndependenceInputs.from_assumption_set(
                assumption_set)
        except (TypeError, ValueError) as exc:
            return self._unavailable(request, str(exc))
        planning, planning_error = self._planning_point(
            members, request.as_of, inputs)
        if planning_error is not None:
            return self._unavailable(request, planning_error)
        assert planning is not None
        planning_at, planning_label = planning

        results = {
            metric_id: self.metrics.dispatch(MetricRequest(
                metric_id,
                request.scope,
                request.as_of,
                assumption_set_id=assumption_set.id,
                parameters={
                    "pension_participant_ids": tuple(
                        member.id for member in members),
                },
            ))
            for metric_id in (
                "finance.pension_wealth",
                "finance.pension_contributions_annual",
                "finance.state_pension_income_annual",
                "finance.defined_benefit_income_annual",
                "finance.retirement_income_required",
                "finance.retirement_wealth_required",
                "finance.pension_contributions_tax_year",
            )
        }
        for metric_id in (
            "finance.pension_wealth",
            "finance.retirement_income_required",
            "finance.retirement_wealth_required",
        ):
            if results[metric_id].status not in ("available", "stale") \
                    or results[metric_id].value is None:
                return self._unavailable(
                    request,
                    f"{metric_id} is unavailable",
                    extra=results[metric_id].limitations,
                )
        current = replace(
            results["finance.pension_wealth"], generated_at=request.as_of)
        required_income = float(
            results["finance.retirement_income_required"].value)
        required_wealth = float(
            results["finance.retirement_wealth_required"].value)
        state_income = (
            float(results["finance.state_pension_income_annual"].value)
            if results["finance.state_pension_income_annual"].value is not None
            else 0.0
        )
        db_income = (
            float(results["finance.defined_benefit_income_annual"].value)
            if results[
                "finance.defined_benefit_income_annual"].value is not None
            else 0.0
        )

        limitations = [
            "All retirement-income figures are gross and expressed in "
            "today's-money real terms; taxation is not assessed.",
            "Longevity beyond the declared sustainable withdrawal basis "
            "is not modelled.",
            "Pension policy and legislative change are not modelled.",
            "Income between earlier pension access ages and the planning "
            "point is not modelled.",
            "Decumulation, sequencing risk and annuitisation are outside "
            "Pension Independence V1.",
            "Declared annual pension contributions continue at constant "
            "real value until the planning point; escalation and career "
            "progression are not modelled.",
            "Foundry provides deterministic factual scenario modelling, "
            "not regulated financial advice.",
            "Observed pension trajectory history is unavailable because "
            "dated pension valuation history cannot yet be reconstructed "
            "honestly.",
        ]
        for result in results.values():
            limitations.extend(result.limitations)
        future = tuple(
            record for subject_id in (
                *(member.id for member in members),
                *self._pension_account_ids({m.id for m in members}),
            )
            for record in self.evidence.future_for(
                subject_id, request.as_of)
        )
        if future:
            limitations.append(
                f"{len(future)} future-dated pension declaration(s) are "
                "excluded from this assessment.")

        accounts, fee_defaulted = self._projection_accounts(
            {member.id for member in members},
            request.as_of,
            inputs,
        )
        if not accounts:
            return self._unavailable(
                request, "no projectable DC pension account is available")
        if fee_defaulted:
            limitations.append(
                "One or more schemes have no fee declaration; the declared "
                "assumed annual fee is used.")
        forecast = self._project(
            accounts,
            request.as_of,
            planning_at,
            inputs,
        )
        terminal = forecast[-1]
        eta = self._first_crossing(forecast, required_wealth, "base")
        low_eta = self._first_crossing(forecast, required_wealth, "low")
        high_eta = self._first_crossing(forecast, required_wealth, "high")
        mission_complete = float(current.value) >= required_wealth
        trajectory_state, trajectory_tone = self._trajectory_state(
            mission_complete,
            eta,
            high_eta,
            terminal,
            required_wealth,
            planning_at,
            inputs,
        )
        eta_applicability = "applicable" if eta is not None else "unavailable"

        milestones = self._milestones(
            float(current.value),
            required_wealth,
            forecast,
        )
        current_milestone = next(
            item for item in milestones if item.is_current)

        sustainable_income = (
            terminal.base * inputs.sustainable_withdrawal_rate)
        combined_income = sustainable_income + state_income + db_income
        surplus = combined_income - required_income
        state_available = (
            results["finance.state_pension_income_annual"].value is not None)
        reliance = (
            state_income / combined_income
            if state_available and combined_income > 0 else None
        )
        margin, factor_items = self._margin(
            surplus,
            required_income,
            low_eta,
            eta,
            high_eta,
            reliance,
            inputs,
            current,
            terminal.base,
            assumption_set,
            request,
        )
        confidence = self._confidence(
            results,
            fee_defaulted,
            members,
            request,
            limitations,
        )
        delta_v, delta_applicability = self._delta_v(
            mission,
            {member.id for member in members},
            request,
            planning_at,
            required_wealth,
            inputs,
        )

        telemetry = self._telemetry(
            results,
            current,
            terminal,
            sustainable_income,
            state_income,
            db_income,
            combined_income,
            required_wealth,
            required_income,
            surplus,
            reliance,
            assumption_set,
            request,
            factor_items,
            members,
        )
        recommendations = self._recommendations(
            request,
            assumption_set,
            accounts,
            planning_at,
            required_wealth,
            required_income,
            state_income,
            db_income,
            combined_income,
            eta,
            confidence,
            inputs,
        )

        input_refs = tuple(sorted({
            reference
            for result in results.values()
            for reference in result.input_references
        }))
        evidence_refs = tuple(sorted({
            reference
            for result in results.values()
            for reference in result.evidence_references
        }))
        limitation_values = tuple(dict.fromkeys(limitations))
        return MissionAssessment(
            mission_id=request.mission_id,
            policy_id=request.policy_id,
            scope=request.scope,
            as_of=request.as_of,
            status=trajectory_tone,
            calculation_version=CALCULATION_VERSION,
            current_value=current,
            mission_complete=mission_complete,
            eta=eta,
            trajectory_state=trajectory_state,
            trajectory_tone=trajectory_tone,
            confidence=confidence,
            current_milestone=current_milestone,
            milestones=milestones,
            mission_margin=margin,
            delta_v=delta_v,
            trajectory=(),
            forecast=forecast,
            telemetry=telemetry,
            recommendations=recommendations,
            input_references=input_refs,
            evidence_references=evidence_refs,
            assumption_references=tuple(assumption_set.provenance),
            limitations=limitation_values,
            confidence_basis=confidence.basis,
            applicability=InstrumentApplicability(
                eta=eta_applicability,
                delta_v=delta_applicability,
                trajectory="unavailable",
                forecast="applicable",
            ),
        )

    def _participants(self, request):
        if request.scope.kind != "party":
            return (), "Pension Independence requires a Party subject"
        subject = self.core.parties.get(request.scope.id)
        if subject is None or subject.status != "active":
            return (), "Pension Independence subject is not active canonical state"
        if subject.party_type == "person":
            if subject.date_of_birth is None:
                return (), f"active pension participant {subject.id} lacks canonical date_of_birth"
            return (subject,), None
        if subject.party_type != "household":
            return (), "Pension Independence subject must be a Person or household"
        active = tuple(member for member in self.core.members_of(subject.id)
                       if member.status == "active")
        missing = tuple(member.id for member in active if member.date_of_birth is None)
        if missing:
            return (), "active household member(s) lack canonical date_of_birth: " + ", ".join(sorted(missing))
        members = tuple(member for member in active
                        if age_years(member.date_of_birth, request.as_of) >= 18)
        if not members:
            return (), "household has no active adult pension participants"
        return members, None

    def _planning_point(self, members, as_of, inputs):
        horizons = []
        missing = []
        for member in members:
            assert member.date_of_birth is not None
            current_age = age_years(member.date_of_birth, as_of)
            target_age = inputs.planning_age
            if target_age is None:
                record = self.evidence.latest(
                    member.id, "state_pension_age", as_of)
                if record is None:
                    missing.append(member.id)
                    continue
                target_age = float(record.value)
            horizons.append(max(0.0, target_age - float(current_age)))
        if missing:
            return None, "State Pension age evidence is missing for adult participant(s): " + ", ".join(sorted(missing))
        if not horizons:
            return None, "planning point has no adult pension participants"
        months = max(1, math.ceil(max(horizons) * 12))
        return (
            self._add_months(as_of, months),
            "PLANNED RETIREMENT" if inputs.planning_age is not None
            else "STATE PENSION AGE",
        ), None

    def _pension_account_ids(self, person_ids):
        owned = self.basis.owned_entities(
            set(person_ids),
            self.finance.accounts,
            vocab.VALUE_OWNERSHIP_RELATIONS,
        )
        return tuple(
            account_id for account_id in owned
            if self.finance.accounts[account_id].account_type == "pension"
        )

    def _projection_accounts(self, person_ids, as_at, inputs):
        account_ids = self._pension_account_ids(person_ids)
        accounts = []
        defaulted = False
        for account_id in account_ids:
            has_db = self.evidence.latest(
                account_id, "db_annual_income_accrued", as_at) is not None
            valuations = tuple(
                item for item in self.finance.valuations_of(account_id)
                if item.as_of <= as_at
            )
            if has_db and valuations:
                continue
            if not valuations:
                continue
            latest = max(
                enumerate(valuations),
                key=lambda item: (item[1].as_of, item[0]),
            )[1]
            converted, _ = self.basis.convert(
                latest.amount, latest.currency, "GBP", as_at)
            if converted is None:
                continue
            contribution = sum(
                float(record.value)
                for field in RATE_FIELDS
                if (record := self.evidence.latest(
                    account_id, field, as_at)) is not None
            )
            fee = self.evidence.latest(
                account_id, "annual_fee_percent", as_at)
            if fee is None:
                annual_fee = inputs.assumed_annual_fee_percent
                defaulted = True
            else:
                annual_fee = float(fee.value)
            accounts.append((converted, contribution, annual_fee))
        return tuple(accounts), defaulted

    def _project(
        self,
        accounts,
        as_at,
        planning_at,
        inputs,
        *,
        monthly_delta=0.0,
    ):
        months = max(0, self._months_between(as_at, planning_at))
        balances = [
            [float(balance), float(balance), float(balance)]
            for balance, _, _ in accounts
        ]
        annual_returns = (
            inputs.low_real_return,
            inputs.base_real_return,
            inputs.high_real_return,
        )
        points = [
            ForecastPoint(
                as_at,
                sum(item[0] for item in balances),
                sum(item[1] for item in balances),
                sum(item[2] for item in balances),
            )
        ]
        for month in range(1, months + 1):
            for account_index, (_, annual_contribution, fee) in enumerate(
                    accounts):
                contribution = annual_contribution / 12
                if account_index == 0:
                    contribution += monthly_delta
                for path, annual_return in enumerate(annual_returns):
                    net = annual_return - fee
                    monthly_rate = (1 + net) ** (1 / 12) - 1
                    balances[account_index][path] = (
                        balances[account_index][path] * (1 + monthly_rate)
                        + contribution
                    )
            at = min(self._add_months(as_at, month), planning_at)
            points.append(ForecastPoint(
                at,
                sum(item[0] for item in balances),
                sum(item[1] for item in balances),
                sum(item[2] for item in balances),
            ))
        return tuple(points)

    @staticmethod
    def _first_crossing(forecast, required, path):
        if required <= 0:
            return forecast[0].at
        for point in forecast:
            if getattr(point, path) >= required:
                return point.at
        return None

    @staticmethod
    def _trajectory_state(
        complete,
        eta,
        high_eta,
        terminal,
        required,
        planning_at,
        inputs,
    ):
        if complete:
            return "Complete", "green"
        if eta is not None:
            months_early = max(0, round(
                (planning_at - eta) / MONTH))
            if months_early >= inputs.accelerated_threshold_months:
                return "Accelerated", "green"
            return "Nominal", "green"
        if high_eta is not None:
            return "Constrained", "amber"
        if required <= 0 \
                or terminal.base >= inputs.divergent_floor_fraction * required:
            return "Divergent", "amber"
        return "Critical", "red"

    def _milestones(self, current, required, forecast):
        if required == 0:
            # A zero destination has no honest intermediate wealth bands.
            # Represent the already-secured destination directly rather than
            # fabricating negative or epsilon-width boundaries.
            return (MissionMilestone(
                "pension-independent",
                "Pension Independent",
                0.0,
                None,
                1.0,
                order=0,
                unit_or_currency="GBP",
                is_current=True,
                is_complete=True,
                completes_mission=True,
                estimated_at=forecast[0].at,
                destination_direction="higher_is_better",
                destination_value=0.0,
            ),)
        boundaries = (
            0.0,
            .25 * required,
            .5 * required,
            .75 * required,
            required,
        )
        current_index = 4 if current >= required else next(
            index for index in range(4)
            if current < boundaries[index + 1]
        )
        values = []
        for index, (identifier, label) in enumerate(MILESTONE_LABELS):
            lower = boundaries[index]
            upper = boundaries[index + 1] if index < 4 else None
            if upper is None:
                completion = 1.0 if current >= lower else 0.0
            elif current <= lower:
                completion = 0.0
            elif current >= upper:
                completion = 1.0
            else:
                completion = (current - lower) / (upper - lower)
            estimate = self._first_crossing(forecast, lower, "base")
            values.append(MissionMilestone(
                identifier,
                label,
                lower,
                upper,
                completion,
                order=index,
                unit_or_currency="GBP",
                is_current=index == current_index,
                is_complete=(
                    current >= (upper if upper is not None else lower)),
                completes_mission=index == 4,
                estimated_at=estimate,
                destination_direction="higher_is_better",
                destination_value=required if index == 4 else lower,
            ))
        return tuple(values)

    def _margin(
        self,
        surplus,
        required_income,
        low_eta,
        eta,
        high_eta,
        reliance,
        inputs,
        current,
        terminal_expected,
        assumption_set,
        request,
    ):
        if surplus >= inputs.surplus_high_fraction * required_income:
            f1 = 3
        elif surplus >= 0:
            f1 = 2
        elif surplus >= -inputs.shortfall_low_fraction * required_income:
            f1 = 1
        else:
            f1 = 0
        if low_eta is not None:
            f2 = 3
            coverage = "Conservative, Expected and Optimistic paths reach"
        elif eta is not None:
            f2 = 2
            coverage = "Expected and Optimistic paths reach"
        elif high_eta is not None:
            f2 = 1
            coverage = "Only the Optimistic path reaches"
        else:
            f2 = 0
            coverage = "No declared sensitivity path reaches"
        f3 = None
        if reliance is not None:
            low, mid, high = inputs.sp_reliance_limits
            f3 = 3 if reliance <= low else 2 if reliance <= mid \
                else 1 if reliance <= high else 0
        scores = (f1, f2) if f3 is None else (f1, f2, f3)
        worst = min(scores)
        state = (
            "Negative Margin" if worst == 0
            else "Low Margin" if worst == 1
            else "High Margin" if all(score == 3 for score in scores)
            else "Adequate Margin"
        )
        signed = (
            f"£{abs(surplus):,.0f} per year projected "
            + ("surplus" if surplus >= 0 else "shortfall")
        )
        description = (
            f"{signed} at the planning point on the Expected path; "
            f"{coverage} the required retirement wealth. Current pension "
            f"is £{float(current.value):,.0f}; Expected projected pension "
            f"is £{terminal_expected:,.0f}. Margin factors: projected "
            f"income band {f1}, sensitivity band {f2}, "
            + (
                f"State Pension reliance {reliance * 100:.1f}% "
                f"(band {f3})."
                if reliance is not None
                else "State Pension reliance excluded because no State "
                "Pension income declaration is available."
            )
        )
        factor_items = [
            self._derived_item(
                "finance.pension_margin_income_band",
                float(f1),
                None,
                request,
                "PROJECTED INCOME MARGIN BAND",
                "number",
                f"F1 · EXPECTED PATH · {signed.upper()}",
                assumption_set,
            ),
            self._derived_item(
                "finance.pension_margin_sensitivity_band",
                float(f2),
                None,
                request,
                "SENSITIVITY ROBUSTNESS BAND",
                "number",
                f"F2 · {coverage.upper()} DESTINATION",
                assumption_set,
            ),
        ]
        if f3 is not None:
            factor_items.append(self._derived_item(
                "finance.pension_margin_reliance_band",
                float(f3),
                None,
                request,
                "STATE PENSION RELIANCE BAND",
                "number",
                f"F3 · {reliance * 100:.1f}% RELIANCE",
                assumption_set,
            ))
        return MissionMargin(
            None,
            None,
            description,
            state,
            label="INCOME GAP",
            value=surplus,
            unit_or_currency="GBP",
            format_kind="currency",
        ), tuple(factor_items)

    def _confidence(
        self,
        results,
        fee_defaulted,
        members,
        request,
        limitations,
    ):
        triggers = []
        if any(result.status == "stale" for result in results.values()):
            triggers.append("one or more pension inputs are stale")
        if fee_defaulted:
            triggers.append("one or more scheme fees are assumed")
        if any(
            "differs from observed" in limitation
            or "both" in limitation and "DB" in limitation
            for limitation in limitations
        ):
            triggers.append("declared evidence has a visible conflict")
        missing_sp = [
            member.id for member in members
            if self.evidence.latest(
                member.id, "state_pension_annual", request.as_of) is None
        ]
        if missing_sp:
            triggers.append("State Pension is missing for active members")
        if self.evidence.has_invalid_for(
            {
                *(member.id for member in members),
                *self._pension_account_ids({m.id for m in members}),
            },
            request.as_of,
        ):
            triggers.append("invalid pension envelopes are quarantined")
        if any(
            self.evidence.latest(
                member.id, "state_pension_basis", request.as_of
            ) is not None
            and self.evidence.latest(
                member.id, "state_pension_basis", request.as_of
            ).value == "forecast_with_continuing_contributions"
            for member in members
        ):
            triggers.append(
                "a State Pension forecast assumes continuing contributions")
        if triggers:
            return MissionConfidence(
                "Provisional",
                "; ".join(dict.fromkeys(triggers))
                + ". Established is unreachable in V1 because tax, "
                "longevity and pension-policy risks are unmodelled.",
            )
        return MissionConfidence(
            "Supported",
            "Required evidence is present, fresh and uncontradicted. "
            "Established is unreachable in V1 because tax, longevity and "
            "pension-policy risks are unmodelled.",
        )

    def _delta_v(
        self,
        mission,
        person_ids,
        request,
        planning_at,
        required,
        inputs,
    ):
        lookback_at = request.as_of - inputs.delta_v_lookback_days * DAY
        historical_accounts, _ = self._projection_accounts(
            person_ids, lookback_at, inputs)
        if not historical_accounts:
            return None, "unavailable"
        historical_forecast = self._project(
            historical_accounts,
            lookback_at,
            planning_at,
            inputs,
        )
        historical_eta = self._first_crossing(
            historical_forecast, required, "base")
        current_accounts, _ = self._projection_accounts(
            person_ids, request.as_of, inputs)
        current_eta = self._first_crossing(
            self._project(
                current_accounts, request.as_of, planning_at, inputs),
            required,
            "base",
        )
        if historical_eta is None or current_eta is None:
            return None, "unavailable"
        days = (historical_eta - current_eta) / DAY
        months = round(days * 12 / 365.2425)
        direction = "accelerated" if days >= 0 else "delayed"
        reference_start_at = self._mission_declared_at(mission)
        kwargs = {}
        if reference_start_at is not None:
            kwargs = {
                "reference_start_at": reference_start_at,
                "reference_start_label": "PLAN DECLARED",
                "reference_destination_at": planning_at,
                "reference_destination_label": "STATE PENSION AGE",
            }
        return DeltaV(
            days,
            inputs.delta_v_lookback_days,
            (
                "Expected fully-funded date moved against the deterministic "
                f"{inputs.delta_v_lookback_days}-day reassessment."
            ),
            months=months,
            direction=direction,
            period_label=f"LAST {inputs.delta_v_lookback_days} DAYS",
            **kwargs,
        ), "applicable"

    def _mission_declared_at(self, mission):
        if not mission.provenance:
            return None
        wanted = mission.provenance[0]
        for event in self.evidence.log.events():
            if event.get("id") == wanted:
                value = event.get("ts")
                if isinstance(value, Real) and math.isfinite(float(value)):
                    return float(value)
        return None

    def _telemetry(
        self,
        results,
        current,
        terminal,
        sustainable_income,
        state_income,
        db_income,
        combined_income,
        required_wealth,
        required_income,
        surplus,
        reliance,
        assumption_set,
        request,
        factor_items,
        members,
    ):
        derived = lambda metric_id, value, unit, label, format_kind, qualifier, \
            region="drilldown", group="": self._derived_item(
                metric_id,
                value,
                unit,
                request,
                label,
                format_kind,
                qualifier,
                assumption_set,
                region,
                group,
            )
        annual = "PER YEAR"
        p7 = replace(
            results["finance.pension_contributions_tax_year"],
            generated_at=request.as_of,
        )
        items = [
            TelemetryItem(
                current,
                "CURRENT PENSION",
                "currency",
                "OBSERVED POT TODAY",
                display_region="essential",
            ),
            *self._provider_projection_items(members, request, assumption_set),
            derived(
                "finance.projected_pension_expected",
                terminal.base,
                "GBP",
                "EXPECTED OUTCOME",
                "currency",
                "AT PLANNING POINT · PROJECTED · EXPECTED PATH · NOT A GUARANTEE",
                "outcome",
            ),
            derived(
                "finance.estimated_retirement_income",
                combined_income,
                "GBP",
                "ESTIMATED RETIREMENT INCOME",
                "currency",
                f"{annual} · PROJECTED · EXPECTED PATH · NOT A GUARANTEE",
                "drilldown",
                "RETIREMENT INCOME COMPOSITION",
            ),
            TelemetryItem(
                p7,
                "THIS TAX YEAR'S CONTRIBUTIONS",
                "currency",
                "DECLARED DATED PAYMENTS",
                display_region="drilldown",
                display_group="CONTRIBUTIONS",
            ),
            TelemetryItem(
                replace(
                    results["finance.retirement_wealth_required"],
                    generated_at=request.as_of),
                "REQUIRED RETIREMENT WEALTH",
                "currency",
                "W* · DECLARED INCOME NEED AND WITHDRAWAL BASIS",
                display_region="essential",
            ),
            derived(
                "finance.pension_funding_ratio",
                float(current.value) / required_wealth
                if required_wealth > 0 else 1.0,
                None,
                "FUNDING RATIO",
                "percent",
                "CURRENT PENSION ÷ REQUIRED RETIREMENT WEALTH",
                "essential",
            ),
            derived(
                "finance.projected_pension_conservative",
                terminal.low,
                "GBP",
                "CONSERVATIVE CASE",
                "currency",
                "PROJECTED · CONSERVATIVE PATH · NOT A GUARANTEE",
                "drilldown",
                "PROJECTION SCENARIOS",
            ),
            derived(
                "finance.projected_pension_optimistic",
                terminal.high,
                "GBP",
                "OPTIMISTIC CASE",
                "currency",
                "PROJECTED · OPTIMISTIC PATH · NOT A GUARANTEE",
                "drilldown",
                "PROJECTION SCENARIOS",
            ),
            derived(
                "finance.sustainable_pension_income",
                sustainable_income,
                "GBP",
                "SUSTAINABLE PENSION INCOME · PER YEAR",
                "currency",
                "PROJECTED · EXPECTED PATH · WITHDRAWAL BASIS",
                "drilldown",
                "RETIREMENT INCOME COMPOSITION",
            ),
            TelemetryItem(
                replace(
                    results["finance.state_pension_income_annual"],
                    generated_at=request.as_of,
                ),
                "STATE PENSION · PER YEAR",
                "currency",
                "DECLARED COMPONENT",
                display_region="drilldown",
                display_group="RETIREMENT INCOME COMPOSITION",
            ),
        ]
        if results["finance.defined_benefit_income_annual"].value is not None:
            items.append(TelemetryItem(
                replace(
                    results["finance.defined_benefit_income_annual"],
                    generated_at=request.as_of,
                ),
                "DEFINED BENEFIT INCOME · PER YEAR",
                "currency",
                "DECLARED COMPONENT",
                display_region="drilldown",
                display_group="RETIREMENT INCOME COMPOSITION",
            ))
        items.extend([
            derived(
                "finance.combined_retirement_income",
                combined_income,
                "GBP",
                "COMBINED RETIREMENT INCOME · PER YEAR",
                "currency",
                "PROJECTED · EXPECTED PATH",
                "drilldown",
                "RETIREMENT INCOME COMPOSITION",
            ),
            *self._contribution_items(
                members, request, assumption_set, p7),
            TelemetryItem(
                replace(
                    results["finance.retirement_income_required"],
                    generated_at=request.as_of),
                "REQUIRED RETIREMENT INCOME · PER YEAR",
                "currency",
                "DECLARED NEED",
                display_group="RETIREMENT REQUIREMENTS",
            ),
            derived(
                "finance.projected_retirement_income_margin",
                surplus,
                "GBP",
                "PROJECTED SURPLUS / SHORTFALL · PER YEAR",
                "currency",
                "SIGNED · EXPECTED PATH",
                "drilldown",
                "MISSION MARGIN EVIDENCE",
            ),
            *factor_items,
        ])
        if reliance is not None:
            items.append(derived(
                "finance.state_pension_reliance",
                reliance,
                None,
                "STATE PENSION RELIANCE",
                "percent",
                "STATE PENSION ÷ COMBINED RETIREMENT INCOME",
                "drilldown",
                "MISSION MARGIN EVIDENCE",
            ))
        margin_metrics = {
            "finance.pension_margin_income_band",
            "finance.pension_margin_sensitivity_band",
            "finance.pension_margin_reliance_band",
        }
        return tuple(
            replace(item, display_group="MISSION MARGIN EVIDENCE")
            if item.result.metric_id in margin_metrics and not item.display_group
            else item
            for item in items
        )

    def _provider_projection_items(self, members, request, assumption_set):
        """Render provider illustrations without making them assessment inputs."""
        if self.provider_projections is None:
            return ()
        items = []
        for account_id in sorted(self._pension_account_ids({member.id for member in members})):
            projection = self.provider_projections.latest(account_id, request.as_of)
            if projection is None:
                continue
            target = (f"RETIREMENT AGE {projection.retirement_age:g}"
                      if projection.retirement_age is not None else "STATED RETIREMENT DATE")
            observed = datetime.fromtimestamp(projection.observed_at, timezone.utc).date().isoformat()
            context = f"{projection.provider.upper()} · OBSERVED {observed} · {target}"
            items.extend((
                self._derived_item(
                    "finance.provider_projected_fund_value_medium", projection.fund_medium,
                    "GBP", request, "PROJECTED FUND VALUE", "currency",
                    f"{context} · MEDIUM {projection.growth_medium_percent:g}% · LOW £{projection.fund_low:,.0f} / HIGH £{projection.fund_high:,.0f}",
                    assumption_set, "essential"),
                self._derived_item(
                    "finance.provider_estimated_yearly_income_medium", projection.income_medium,
                    "GBP", request, "ESTIMATED YEARLY INCOME", "currency",
                    f"{context} · MEDIUM · LOW £{projection.income_low:,.0f} / HIGH £{projection.income_high:,.0f} · {projection.income_basis}",
                    assumption_set, "essential"),
            ))
        return tuple(items)

    def _contribution_items(self, members, request, assumption_set, p7):
        person_ids = {member.id for member in members}
        employee = employer = sacrifice = 0.0
        refs = []
        for account_id in self._pension_account_ids(person_ids):
            for field in RATE_FIELDS:
                record = self.evidence.latest(
                    account_id, field, request.as_of)
                if record is None:
                    continue
                refs.append(record.event_id)
                if field == "employee_contribution_annual":
                    employee += float(record.value)
                elif field == "employer_contribution_annual":
                    employer += float(record.value)
                else:
                    sacrifice += float(record.value)
        def item(metric_id, value, label):
            result = MetricResult(
                metric_id,
                value,
                "GBP",
                request.scope,
                request.as_of,
                "available",
                CALCULATION_VERSION,
                evidence_references=tuple(refs),
                assumption_references=(),
                generated_at=request.as_of,
                confidence_or_quality="derived",
            )
            return TelemetryItem(
                result,
                label,
                "currency",
                "DECLARED ANNUAL RATE · PER YEAR",
                display_region="drilldown",
                display_group="CONTRIBUTIONS",
            )
        return (
            item(
                "finance.pension_employee_contributions",
                employee + sacrifice,
                "EMPLOYEE CONTRIBUTIONS · PER YEAR",
            ),
            item(
                "finance.pension_employer_contributions",
                employer,
                "EMPLOYER CONTRIBUTIONS · PER YEAR",
            ),
            item(
                "finance.pension_total_contributions",
                employee + employer + sacrifice,
                "TOTAL CONTRIBUTIONS · PER YEAR",
            ),
            TelemetryItem(
                p7,
                "TAX YEAR TOTAL",
                "currency",
                "DECLARED DATED PAYMENTS",
                display_region="drilldown",
                display_group="CONTRIBUTIONS",
            ),
        )

    def _derived_item(
        self,
        metric_id,
        value,
        unit,
        request,
        label,
        format_kind,
        qualifier,
        assumption_set,
        region="drilldown",
        group="",
    ):
        result = MetricResult(
            metric_id,
            value,
            unit,
            request.scope,
            request.as_of,
            "available",
            CALCULATION_VERSION,
            assumption_references=tuple(assumption_set.provenance),
            generated_at=request.as_of,
            confidence_or_quality="derived",
        )
        return TelemetryItem(
            result,
            label,
            format_kind,
            qualifier,
            display_region=region,
            display_group=group,
        )

    def _recommendations(
        self,
        request,
        assumption_set,
        accounts,
        planning_at,
        required_wealth,
        required_income,
        state_income,
        db_income,
        current_income,
        current_eta,
        confidence,
        inputs,
    ):
        scenarios = sorted(
            (
                scenario for scenario in self.finance.scenarios.values()
                if scenario.status == "active"
                and scenario.assumption_set_id == assumption_set.id
                and scenario.action_type == "increase_pension_contribution"
                and scenario.unit_or_currency == "GBP"
                and scenario.cadence == "month"
                and set(scenario.adjustments)
                == {"monthly_pension_contribution_delta"}
            ),
            key=lambda scenario: scenario.id,
        )
        if not scenarios:
            return ()
        scenario = scenarios[0]
        liquidity = self.metrics.dispatch(MetricRequest(
            "finance.liquidity_runway",
            request.scope,
            request.as_of,
        ))
        if liquidity.status not in ("available", "stale") \
                or liquidity.value is None \
                or float(liquidity.value) \
                < inputs.recommendation_liquidity_floor_months:
            observed = (
                f"{float(liquidity.value):.1f} months"
                if liquidity.value is not None else "not evaluable")
            return (RecommendationAssessment(
                action=(
                    f"Pension contribution increase is not recommended "
                    f"because current liquidity runway is {observed}, below "
                    f"Pension Independence's declared "
                    f"{inputs.recommendation_liquidity_floor_months:.0f}-month "
                    "recommendation floor. Financial Resilience takes "
                    "precedence."
                ),
                scenario_id=scenario.id,
                estimated_delta_v_days=None,
                status="suppressed",
                limitations=(
                    "Preserve emergency liquidity before deploying "
                    "additional capital.",
                ),
                assumption_references=tuple(assumption_set.provenance),
                evidence_references=liquidity.input_references,
            ),)
        delta = float(
            scenario.adjustments["monthly_pension_contribution_delta"])
        projected = self._project(
            accounts,
            request.as_of,
            planning_at,
            inputs,
            monthly_delta=delta,
        )
        new_terminal = projected[-1].base
        new_income = (
            new_terminal * inputs.sustainable_withdrawal_rate
            + state_income + db_income
        )
        margin_impact = new_income - current_income
        new_eta = self._first_crossing(
            projected, required_wealth, "base")
        eta_days = (
            (current_eta - new_eta) / DAY
            if current_eta is not None and new_eta is not None else None
        )
        eta_months = (
            round(eta_days * 12 / 365.2425)
            if eta_days is not None else None
        )
        return (RecommendationAssessment(
            action=(
                f"Declared scenario increases pension contributions by "
                f"£{delta:,.0f} per month. Expected retirement income "
                f"improves by £{margin_impact:,.0f} per year under the "
                "same declared assumptions."
            ),
            scenario_id=scenario.id,
            estimated_delta_v_days=eta_days,
            action_type=scenario.action_type or "",
            action_label=scenario.action_label or "",
            amount=delta,
            unit_or_currency=scenario.unit_or_currency,
            cadence=scenario.cadence,
            adjustment_key="monthly_pension_contribution_delta",
            estimated_delta_v_months=eta_months,
            delta_v_direction=(
                "accelerated" if eta_days is not None and eta_days >= 0
                else "delayed" if eta_days is not None else None
            ),
            limitations=(
                "Deterministic factual scenario modelling; not regulated "
                "financial advice.",
                f"Mission Confidence remains {confidence.state}.",
            ),
            assumption_references=tuple(assumption_set.provenance),
            evidence_references=tuple(scenario.provenance),
        ),)

    @staticmethod
    def _add_months(timestamp, months):
        value = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        month_index = value.month - 1 + months
        year = value.year + month_index // 12
        month = month_index % 12 + 1
        day = min(value.day, calendar.monthrange(year, month)[1])
        return value.replace(year=year, month=month, day=day).timestamp()

    @staticmethod
    def _months_between(start, end):
        first = datetime.fromtimestamp(start, tz=timezone.utc)
        last = datetime.fromtimestamp(end, tz=timezone.utc)
        return max(
            0,
            (last.year - first.year) * 12 + last.month - first.month,
        )

    @staticmethod
    def _unavailable(request, reason, *, extra=()):
        return MissionAssessment.unavailable(
            request,
            reason,
            calculation_version=CALCULATION_VERSION,
        ) if not extra else MissionAssessment(
            mission_id=request.mission_id,
            policy_id=request.policy_id,
            scope=request.scope,
            as_of=request.as_of,
            status="unavailable",
            calculation_version=CALCULATION_VERSION,
            confidence=MissionConfidence("Insufficient", reason),
            limitations=(reason, *extra),
            applicability=InstrumentApplicability(
                eta="unavailable",
                delta_v="unavailable",
                trajectory="unavailable",
                forecast="unavailable",
                margin="unavailable",
            ),
        )

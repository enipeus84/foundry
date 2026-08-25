"""Mortgage Freedom Mission Assessment (RFC-007).

All mortgage policy and arithmetic live in Finance.  Core routes the
domain-neutral contract and Mission Control renders it without knowing the
mission name.  Forecasts are deterministic sensitivity paths, not
probabilities, and assessment never appends an event.
"""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import math
import time

from foundry.core.entities import EntityProjection
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
    TrajectoryPoint,
)

from .entities import AssumptionSet, FinanceEntityProjection, VALUATION_BASES
from .mortgage_evidence import MortgageEvidence, MortgageEvidenceProjection


POLICY_ID = "finance.mortgage_freedom.v1"
CALCULATION_VERSION = "mortgage-v2"
TARGET_METRIC = "finance.mortgage_balance"
DAY = 86_400.0
YEAR = 365.2425 * DAY
MONTH = YEAR / 12.0
MONTH_DAYS = MONTH / DAY
MONTH_NAMES = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)
EVIDENCE_LABELS = {
    "property_role": "property role",
    "purchase_price": "purchase price",
    "purchase_date": "purchase date",
    "initial_deposit": "initial deposit",
    "acquisition_costs": "acquisition costs",
    "property_valuation": "dated valuation reference",
    "valuation_basis": "valuation basis",
    "lender": "mortgage lender",
    "original_advance": "original mortgage advance",
    "mortgage_start": "first mortgage payment date",
    "balance": "mortgage balance",
    "repayment_type": "repayment type",
    "interest_type": "interest type",
    "interest_rate": "mortgage interest rate",
    "monthly_payment": "monthly mortgage payment",
    "original_term_months": "original mortgage term",
    "remaining_term_months": "remaining mortgage term",
    "fixed_rate_expiry": "fixed-rate expiry",
}
ACQUISITION_FIELDS = (
    "purchase_price",
    "purchase_date",
    "initial_deposit",
    "original_advance",
    "acquisition_costs",
)


def _month_year(timestamp: float) -> str:
    utc = time.gmtime(timestamp)
    return f"{MONTH_NAMES[utc.tm_mon - 1]} {utc.tm_year}"


def _add_calendar_months(timestamp: float, months: int) -> float:
    """Advance a UTC timestamp by whole calendar months deterministically."""
    value = datetime.fromtimestamp(timestamp, timezone.utc)
    month_index = value.year * 12 + value.month - 1 + months
    year, zero_based_month = divmod(month_index, 12)
    month = zero_based_month + 1
    day = min(value.day, monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day).timestamp()


@dataclass(frozen=True)
class MortgageProjectionInputs:
    low_post_fix_rate: float
    base_post_fix_rate: float
    high_post_fix_rate: float
    forecast_horizon_months: int
    balance_stale_after_days: int
    valuation_stale_after_days: int
    liquidity_floor_months: float

    @classmethod
    def from_assumption_set(
        cls, assumption_set: AssumptionSet
    ) -> "MortgageProjectionInputs":
        values = assumption_set.assumptions
        required = {
            "low_post_fix_rate",
            "base_post_fix_rate",
            "high_post_fix_rate",
            "forecast_horizon_months",
            "balance_stale_after_days",
            "valuation_stale_after_days",
            "liquidity_floor_months",
        }
        missing = sorted(required - values.keys())
        if missing:
            raise ValueError(f"Assumption Set missing: {', '.join(missing)}")
        for key in sorted(required):
            value = values[key]
            if isinstance(value, bool) \
                    or not isinstance(value, (int, float)) \
                    or not math.isfinite(float(value)):
                raise ValueError(
                    f"Assumption Set {key} must be a finite number")
        for key in (
            "forecast_horizon_months",
            "balance_stale_after_days",
            "valuation_stale_after_days",
        ):
            if not float(values[key]).is_integer():
                raise ValueError(
                    f"Assumption Set {key} must be an integer")
        result = cls(
            low_post_fix_rate=float(values["low_post_fix_rate"]),
            base_post_fix_rate=float(values["base_post_fix_rate"]),
            high_post_fix_rate=float(values["high_post_fix_rate"]),
            forecast_horizon_months=int(values["forecast_horizon_months"]),
            balance_stale_after_days=int(values["balance_stale_after_days"]),
            valuation_stale_after_days=int(
                values["valuation_stale_after_days"]),
            liquidity_floor_months=float(values["liquidity_floor_months"]),
        )
        if not (
            0.0 <= result.low_post_fix_rate
            <= result.base_post_fix_rate
            <= result.high_post_fix_rate
            <= 1.0
        ):
            raise ValueError(
                "post-fix rates must be ordered low <= base <= high "
                "and between zero and one")
        if not 1 <= result.forecast_horizon_months <= 960:
            raise ValueError(
                "forecast_horizon_months must be between 1 and 960")
        if not 1 <= result.balance_stale_after_days <= 3650:
            raise ValueError(
                "balance_stale_after_days must be between 1 and 3650")
        if not 1 <= result.valuation_stale_after_days <= 3650:
            raise ValueError(
                "valuation_stale_after_days must be between 1 and 3650")
        if not math.isfinite(result.liquidity_floor_months) \
                or result.liquidity_floor_months < 0:
            raise ValueError(
                "liquidity_floor_months must be finite and non-negative")
        return result


@dataclass(frozen=True)
class MortgageProjection:
    points: tuple[ForecastPoint, ...]
    payoff_low: float | None
    payoff_base: float | None
    payoff_high: float | None
    interest_low: float
    interest_base: float
    interest_high: float


class MortgageProjectionEngine:
    """Pure monthly capital-repayment model."""

    @staticmethod
    def _path(
        balance: float,
        start_at: float,
        current_rate: float,
        monthly_payment: float,
        fixed_rate_expiry: float,
        post_fix_rate: float,
        horizon_months: int,
        monthly_overpayment: float,
    ) -> tuple[tuple[float, ...], float, int | None]:
        outstanding = max(0.0, balance)
        values = [outstanding]
        interest_total = 0.0
        payoff_month = 0 if outstanding == 0 else None
        payment = monthly_payment + monthly_overpayment
        if payment <= 0:
            raise ValueError("monthly payment must be positive")
        for month in range(1, horizon_months + 1):
            if outstanding == 0:
                values.append(0.0)
                continue
            period_at = start_at + (month - 1) * MONTH
            annual_rate = (
                current_rate if period_at <= fixed_rate_expiry
                else post_fix_rate)
            interest = outstanding * annual_rate / 12.0
            interest_total += interest
            outstanding = max(
                0.0, outstanding + interest - min(
                    payment, outstanding + interest))
            if outstanding < .005:
                outstanding = 0.0
            values.append(outstanding)
            if outstanding == 0 and payoff_month is None:
                payoff_month = month
        return tuple(values), interest_total, payoff_month

    @classmethod
    def project(
        cls,
        balance: float,
        start_at: float,
        inputs: MortgageProjectionInputs,
        *,
        current_rate: float,
        monthly_payment: float,
        fixed_rate_expiry: float,
        monthly_overpayment: float = 0.0,
    ) -> MortgageProjection:
        if not all(math.isfinite(value) for value in (
            balance, start_at, current_rate, monthly_payment,
            fixed_rate_expiry, monthly_overpayment,
        )):
            raise ValueError("mortgage projection inputs must be finite")
        if balance < 0 or not 0 <= current_rate <= 1 \
                or monthly_overpayment < 0:
            raise ValueError("mortgage projection inputs are outside policy")
        paths = tuple(
            cls._path(
                balance, start_at, current_rate, monthly_payment,
                fixed_rate_expiry, rate, inputs.forecast_horizon_months,
                monthly_overpayment)
            for rate in (
                inputs.low_post_fix_rate,
                inputs.base_post_fix_rate,
                inputs.high_post_fix_rate,
            )
        )
        low_values, base_values, high_values = (
            paths[0][0], paths[1][0], paths[2][0])
        points = tuple(ForecastPoint(
            at=start_at + month * MONTH,
            low=low_values[month],
            base=base_values[month],
            high=high_values[month],
        ) for month in range(inputs.forecast_horizon_months + 1))
        payoff = tuple(
            None if path[2] is None else start_at + path[2] * MONTH
            for path in paths)
        return MortgageProjection(
            points, payoff[0], payoff[1], payoff[2],
            paths[0][1], paths[1][1], paths[2][1])


@dataclass(frozen=True)
class MortgageFreedomPolicy:
    id: str = POLICY_ID
    target_metric: str = TARGET_METRIC
    unit_or_currency: str = "GBP"


@dataclass(frozen=True)
class PropertyValuationCandidate:
    amount: float
    effective_at: float
    source: str
    basis: str | None
    event_id: str
    legacy_record: MortgageEvidence | None = None


class MortgageFreedomAssessor:
    """Finance provider for one household-scoped mortgage mission."""

    _REQUIRED_FIELDS = frozenset({
        "property_role",
        "lender",
        "original_advance",
        "mortgage_start",
        "balance",
        "repayment_type",
        "interest_type",
        "interest_rate",
        "monthly_payment",
        "original_term_months",
        "remaining_term_months",
        "fixed_rate_expiry",
    })

    def __init__(
        self,
        finance: FinanceEntityProjection,
        core: EntityProjection,
        metrics: MetricRegistry,
        evidence: MortgageEvidenceProjection,
        policy: MortgageFreedomPolicy | None = None,
    ):
        self.finance = finance
        self.core = core
        self.metrics = metrics
        self.evidence = evidence
        self.policy = policy or MortgageFreedomPolicy()
        self.projection = MortgageProjectionEngine()

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
                or not isinstance(mission.target_value, (int, float)) \
                or not math.isfinite(float(mission.target_value)) \
                or mission.target_value != 0.0:
            return self._unavailable(
                request, "Mission destination must be a zero mortgage balance")
        if mission.target_date is None \
                or isinstance(mission.target_date, bool) \
                or not isinstance(mission.target_date, (int, float)) \
                or not math.isfinite(float(mission.target_date)):
            return self._unavailable(
                request, "mission target date is absent or invalid")
        if request.scope.kind != "party":
            return self._unavailable(
                request, "Mortgage Freedom requires a party scope")
        household = self.core.parties.get(request.scope.id)
        if household is None or household.party_type != "household" \
                or household.status != "active":
            return self._unavailable(
                request, "active household scope not found")

        assumption_set = self.finance.assumption_sets.get(
            mission.assumption_set_id or "")
        if assumption_set is None or assumption_set.status != "active":
            return self._unavailable(
                request, "active Assumption Set not found")
        try:
            inputs = MortgageProjectionInputs.from_assumption_set(
                assumption_set)
        except (TypeError, ValueError) as exc:
            return self._unavailable(request, str(exc))

        obligation, secured_property, scope_input_refs, reason = self._scoped_mortgage(
            request.scope.id)
        if obligation is None:
            return self._unavailable(request, reason)
        if self.evidence.has_invalid_for(obligation.id, request.as_of):
            return self._unavailable(
                request, "mortgage evidence envelope is malformed")

        records = {
            field: self.evidence.latest(obligation.id, field, request.as_of)
            for field in self._REQUIRED_FIELDS
        }
        missing = sorted(field for field, record in records.items()
                         if record is None)
        if missing:
            missing_labels = sorted(
                EVIDENCE_LABELS.get(field, "required mortgage evidence")
                for field in missing)
            return self._unavailable(
                request,
                f"Mortgage evidence missing: {', '.join(missing_labels)}")
        evidence_records = tuple(
            record for record in records.values() if record is not None)
        if any(record.confidence < .5 for record in evidence_records):
            return self._unavailable(
                request, "required mortgage evidence has insufficient confidence")

        valuation_candidate = self._property_valuation_candidate(
            obligation.id, secured_property.id, request.as_of)
        if valuation_candidate is None:
            return self._unavailable(
                request, "no eligible secured-property valuation was found")
        if valuation_candidate.legacy_record is not None \
                and valuation_candidate.legacy_record.confidence < .5:
            return self._unavailable(
                request, "required mortgage evidence has insufficient confidence")

        try:
            numeric = {
                field: self._numeric(records[field], field)
                for field in (
                    "original_advance",
                    "mortgage_start",
                    "balance",
                    "interest_rate",
                    "monthly_payment",
                    "original_term_months",
                    "remaining_term_months",
                    "fixed_rate_expiry",
                )
            }
            text = {
                field: self._string(records[field], field)
                for field in (
                    "property_role", "lender", "repayment_type",
                    "interest_type")
            }
            self._validate_contract(numeric, text)
            self._validate_units(records)
        except ValueError as exc:
            return self._unavailable(request, str(exc))
        if numeric["mortgage_start"] > request.as_of:
            return self._unavailable(
                request, "Mortgage start cannot be after assessment time")
        if records["balance"].effective_at < numeric["mortgage_start"]:
            return self._unavailable(
                request, "Mortgage balance evidence predates mortgage start")
        try:
            original_contractual_eta = _add_calendar_months(
                numeric["mortgage_start"],
                int(numeric["original_term_months"]))
        except (OSError, OverflowError, ValueError):
            return self._unavailable(
                request,
                "Original contractual term cannot be represented safely")
        if mission.target_date != original_contractual_eta:
            return self._unavailable(
                request,
                "Mission destination does not match the original "
                "contractual term evidence")

        balance = numeric["balance"]
        original = numeric["original_advance"]
        valuation = valuation_candidate.amount
        current_equity = valuation - balance
        principal_repaid = original - balance
        current_rate = numeric["interest_rate"]
        payment = numeric["monthly_payment"]
        fixed_expiry = numeric["fixed_rate_expiry"]
        mortgage_evidence_refs = tuple(sorted(
            record.event_id for record in evidence_records))
        valuation_evidence_refs = (valuation_candidate.event_id,)
        mortgage_input_refs = tuple(sorted({
            *scope_input_refs, *mission.provenance, *mission.history,
        }))
        assumption_refs = tuple(assumption_set.provenance)
        balance_status = (
            "stale" if self._is_stale(
                request.as_of, records["balance"],
                inputs.balance_stale_after_days)
            else "available")
        current = self._metric(
            self.policy.target_metric, balance, self.policy.unit_or_currency,
            request, balance_status, mortgage_input_refs,
            mortgage_evidence_refs,
            assumption_refs)
        ltv = balance / valuation
        runway = self.metrics.dispatch(MetricRequest(
            "finance.liquidity_runway", request.scope, request.as_of))
        runway_value = self._finite_metric_value(runway, request)
        fixed_months = max(
            0.0, (fixed_expiry - request.as_of) / MONTH)
        all_overpayments = tuple(
            record for record in self.evidence.for_obligation(
                obligation.id, request.as_of)
            if record.field == "recorded_overpayment"
        )
        overpayments = all_overpayments
        all_mortgage_records = self.evidence.for_obligation(
            obligation.id, request.as_of)
        acquisition_history = {
            field: tuple(
                record for record in all_mortgage_records
                if record.field == field)
            for field in ACQUISITION_FIELDS
        }
        acquisition_records = tuple(
            record for field in ACQUISITION_FIELDS
            for record in acquisition_history[field])
        purchase_price_record = self.evidence.latest(
            obligation.id, "purchase_price", request.as_of)
        purchase_date_record = self.evidence.latest(
            obligation.id, "purchase_date", request.as_of)
        initial_deposit_record = self.evidence.latest(
            obligation.id, "initial_deposit", request.as_of)
        acquisition_costs_record = self.evidence.latest(
            obligation.id, "acquisition_costs", request.as_of)
        valuation_basis_records = tuple(
            record for record in all_mortgage_records
            if record.field == "valuation_basis")
        valuation_basis_record = self.evidence.latest(
            obligation.id, "valuation_basis", request.as_of)

        try:
            projected = self.projection.project(
                balance, request.as_of, inputs,
                current_rate=current_rate, monthly_payment=payment,
                fixed_rate_expiry=fixed_expiry)
        except ValueError as exc:
            return self._partial_projection_failure(
                request=request,
                mission=mission,
                assumption_refs=assumption_refs,
                mortgage_input_refs=mortgage_input_refs,
                mortgage_evidence_refs=mortgage_evidence_refs,
                valuation_evidence_refs=valuation_evidence_refs,
                acquisition_history=acquisition_history,
                valuation_basis_records=valuation_basis_records,
                current=current,
                balance=balance,
                original=original,
                valuation=valuation,
                current_equity=current_equity,
                principal_repaid=principal_repaid,
                fixed_months=fixed_months,
                purchase_price_record=purchase_price_record,
                purchase_date_record=purchase_date_record,
                initial_deposit_record=initial_deposit_record,
                acquisition_costs_record=acquisition_costs_record,
                valuation_basis_record=valuation_basis_record,
                valuation_status=(
                    "stale" if request.as_of - valuation_candidate.effective_at > (
                        inputs.valuation_stale_after_days * DAY)
                    else "available"
                ),
                balance_status=balance_status,
                ltv=ltv,
                text=text,
                current_rate=current_rate,
                payment=payment,
                original_contractual_eta=original_contractual_eta,
                confidence=self._confidence(
                    request.as_of, records, inputs, overpayments,
                    valuation_effective_at=valuation_candidate.effective_at,
                    valuation_record=valuation_candidate.legacy_record),
                valuation_effective_at=valuation_candidate.effective_at,
                valuation_source=valuation_candidate.source,
                reason=str(exc),
            )

        complete = balance == 0.0
        status, trajectory_state, tone = self._schedule_assessment(
            complete, projected.payoff_low, projected.payoff_base,
            projected.payoff_high, original_contractual_eta)

        purchase_price = (
            self._numeric(purchase_price_record, "purchase_price")
            if purchase_price_record is not None else None)
        purchase_date = self._purchase_date_label(purchase_date_record)
        initial_deposit = (
            self._numeric(initial_deposit_record, "initial_deposit")
            if initial_deposit_record is not None else None)
        acquisition_costs = (
            self._numeric(acquisition_costs_record, "acquisition_costs")
            if acquisition_costs_record is not None else None)
        valuation_movement = (
            valuation - purchase_price
            if purchase_price is not None else None)
        purchase_detail = (
            f"Purchase evidence: £{purchase_price:,.0f} purchase price"
            + (f" · {purchase_date}." if purchase_date else ".")
            if purchase_price is not None else None)
        confidence = self._confidence(
            request.as_of, records, inputs, overpayments,
            valuation_effective_at=valuation_candidate.effective_at,
            valuation_record=valuation_candidate.legacy_record)
        assessment_input_refs = tuple(sorted({
            *mortgage_input_refs,
            *(runway.input_references if runway_value is not None else ()),
        }))
        recommendation_evidence_refs = tuple(sorted({
            *mortgage_evidence_refs,
            *(record.event_id for record in all_overpayments),
            *(runway.evidence_references if runway_value is not None else ()),
        }))
        assessment_evidence_refs = tuple(sorted({
            *recommendation_evidence_refs,
            *valuation_evidence_refs,
            *(record.event_id for record in acquisition_records),
            *(record.event_id for record in valuation_basis_records),
        }))
        margin = self._mission_margin(
            ltv, runway_value, fixed_months, overpayments)
        milestones = self._milestones(
            balance, original, projected)
        current_milestone = next(
            item for item in milestones if item.is_current)

        delta_v = self._delta_v(
            original_contractual_eta, projected.payoff_base,
            numeric["mortgage_start"], request.as_of, complete)
        recommendations = self._recommendation(
            balance, request, inputs, assumption_set, current_rate,
            payment, fixed_expiry, projected, runway_value,
            recommendation_evidence_refs)

        valuation_status = (
            "stale" if request.as_of - valuation_candidate.effective_at > (
                inputs.valuation_stale_after_days * DAY)
            else "available")
        valuation_source = valuation_candidate.source
        valuation_month = _month_year(valuation_candidate.effective_at)
        if valuation_candidate.basis is not None:
            valuation_basis = valuation_candidate.basis.replace("_", " ").capitalize()
            valuation_reference = (
                f"Estimated · {valuation_basis} · "
                f"{valuation_source} · {valuation_month}"
            )
        else:
            valuation_reference = (
                "Estimated · Valuation basis: Not recorded; not inferred · "
                f"{valuation_source} · {valuation_month}"
            )
        current_position_status = (
            "stale"
            if balance_status == "stale" or valuation_status == "stale"
            else "available")

        def evidence_refs(*record_groups) -> tuple[str, ...]:
            return tuple(sorted({
                record.event_id
                for group in record_groups
                for record in group
            }))

        purchase_refs = evidence_refs(
            acquisition_history["purchase_price"],
            acquisition_history["purchase_date"])
        deposit_refs = evidence_refs(
            acquisition_history["initial_deposit"])
        original_refs = evidence_refs(
            acquisition_history["original_advance"])
        acquisition_cost_refs = evidence_refs(
            acquisition_history["acquisition_costs"])
        valuation_refs = valuation_evidence_refs
        equity_refs = tuple(sorted({
            *valuation_evidence_refs, records["balance"].event_id,
        }))
        purchase_qualifier = (
            f"PURCHASED {purchase_date.upper()}"
            + (
                " · MONTH PRECISION"
                if purchase_date_record is not None
                and isinstance(purchase_date_record.value, str)
                else ""
            )
            if purchase_date is not None
            else "PURCHASE DATE NOT RECORDED"
        )

        purchase_metric = (
            self._metric(
                "finance.property_purchase_price", purchase_price,
                self.policy.unit_or_currency, request, "available",
                mortgage_input_refs, purchase_refs, assumption_refs)
            if purchase_price is not None
            else self._unavailable_metric(
                "finance.property_purchase_price", request,
                "purchase price evidence is not recorded",
                mortgage_input_refs, purchase_refs, assumption_refs)
        )
        deposit_metric = (
            self._metric(
                "finance.mortgage_initial_deposit", initial_deposit,
                self.policy.unit_or_currency, request, "available",
                mortgage_input_refs, deposit_refs, assumption_refs)
            if initial_deposit is not None
            else self._unavailable_metric(
                "finance.mortgage_initial_deposit", request,
                "initial deposit evidence is not recorded",
                mortgage_input_refs, deposit_refs, assumption_refs)
        )
        acquisition_cost_metric = (
            self._metric(
                "finance.property_acquisition_costs", acquisition_costs,
                self.policy.unit_or_currency, request, "available",
                mortgage_input_refs, acquisition_cost_refs, assumption_refs)
            if acquisition_costs is not None
            else self._unavailable_metric(
                "finance.property_acquisition_costs", request,
                "optional acquisition costs are not recorded",
                mortgage_input_refs, acquisition_cost_refs, assumption_refs)
        )
        valuation_movement_metric = (
            self._metric(
                "finance.property_valuation_movement", valuation_movement,
                self.policy.unit_or_currency, request,
                current_position_status, mortgage_input_refs,
                tuple(sorted({*valuation_evidence_refs, *evidence_refs(
                    acquisition_history["purchase_price"])})),
                assumption_refs)
            if valuation_movement is not None
            else self._unavailable_metric(
                "finance.property_valuation_movement", request,
                "purchase price evidence is required for valuation movement",
                mortgage_input_refs, valuation_refs, assumption_refs)
        )
        telemetry = (
            # Property acquisition. Purchase date is carried at its supplied
            # precision in the purchase-price qualifier; no day is inferred.
            TelemetryItem(
                purchase_metric, "PROPERTY ACQUISITION · PURCHASE PRICE",
                "currency",
                purchase_qualifier),
            TelemetryItem(
                deposit_metric, "PROPERTY ACQUISITION · INITIAL DEPOSIT",
                "currency"),
            TelemetryItem(self._metric(
                "finance.mortgage_initial_advance", original,
                self.policy.unit_or_currency, request, "available",
                mortgage_input_refs, original_refs, assumption_refs),
                "PROPERTY ACQUISITION · INITIAL MORTGAGE", "currency"),
            TelemetryItem(
                acquisition_cost_metric,
                "PROPERTY ACQUISITION · ACQUISITION COSTS", "currency",
                "OPTIONAL · SHOWN SEPARATELY FROM EQUITY"),

            # Current position.
            TelemetryItem(self._metric(
                "finance.property_valuation", valuation,
                self.policy.unit_or_currency, request, valuation_status,
                mortgage_input_refs, valuation_refs, assumption_refs),
                "CURRENT POSITION · PROPERTY VALUATION", "currency",
                valuation_reference),
            TelemetryItem(
                current, "MORTGAGE BALANCE", "currency",
                f"OBSERVED · "
                f"{_month_year(records['balance'].effective_at).upper()}"),
            TelemetryItem(self._metric(
                "finance.property_current_equity", current_equity,
                self.policy.unit_or_currency, request,
                current_position_status, mortgage_input_refs, equity_refs,
                assumption_refs), "CURRENT POSITION · CURRENT EQUITY",
                "currency",
                "PROPERTY VALUE − MORTGAGE BALANCE"),
            TelemetryItem(self._metric(
                "finance.mortgage_ltv", ltv, None, request,
                valuation_status, mortgage_input_refs,
                valuation_evidence_refs, assumption_refs),
                "CURRENT POSITION · CURRENT LTV", "percent",
                valuation_reference),
            TelemetryItem(self._metric(
                "finance.mortgage_payment", payment,
                self.policy.unit_or_currency, request, "available",
                mortgage_input_refs, mortgage_evidence_refs, assumption_refs),
                "CURRENT POSITION · MONTHLY PAYMENT", "currency"),
            TelemetryItem(self._metric(
                "finance.mortgage_fixed_protection", fixed_months,
                "months", request, "available", mortgage_input_refs,
                mortgage_evidence_refs,
                assumption_refs),
                "CURRENT POSITION · FIXED-RATE PROTECTION", "months"),
            TelemetryItem(self._metric(
                "finance.mortgage_projected_interest",
                projected.interest_base, self.policy.unit_or_currency,
                request, "available", mortgage_input_refs,
                mortgage_evidence_refs,
                assumption_refs), "CURRENT POSITION · REMAINING INTEREST",
                "currency",
                "PROJECTED · EXPECTED PATH"),

            # Equity composition. These observations explain current equity;
            # they do not determine mission policy or correct one another.
            TelemetryItem(self._metric(
                "finance.mortgage_principal_repaid", principal_repaid,
                self.policy.unit_or_currency, request, balance_status,
                mortgage_input_refs,
                evidence_refs(
                    acquisition_history["original_advance"],
                    (records["balance"],)),
                assumption_refs), "EQUITY COMPOSITION · PRINCIPAL REPAID",
                "currency",
                "INITIAL MORTGAGE − CURRENT BALANCE"),
            TelemetryItem(
                valuation_movement_metric,
                "EQUITY COMPOSITION · VALUATION MOVEMENT", "currency",
                "CURRENT VALUE − PURCHASE PRICE"),
        )
        essential_metric_ids = {
            "finance.mortgage_payment",
            "finance.mortgage_fixed_protection",
        }
        acquisition_metric_ids = {
            "finance.property_purchase_price",
            "finance.mortgage_initial_deposit",
            "finance.mortgage_initial_advance",
            "finance.property_acquisition_costs",
        }
        equity_metric_ids = {
            "finance.property_valuation",
            "finance.property_current_equity",
            "finance.mortgage_ltv",
            "finance.mortgage_principal_repaid",
            "finance.property_valuation_movement",
        }
        telemetry = tuple(
            replace(
                item,
                display_region=(
                    "essential"
                    if item.result.metric_id in essential_metric_ids
                    else "drilldown"
                ),
                display_group=(
                    ""
                    if item.result.metric_id in essential_metric_ids
                    else "PROPERTY ACQUISITION"
                    if item.result.metric_id in acquisition_metric_ids
                    else "EQUITY AND VALUATION ANALYSIS"
                    if item.result.metric_id in equity_metric_ids
                    else "MORTGAGE POSITION"
                ),
            )
            for item in telemetry
        )
        limitations = [
            f"Primary residence dated valuation reference: "
            f"£{valuation:,.2f} · {valuation_source} · "
            f"{valuation_month}; "
            f"mortgage held with {text['lender']}.",
            f"Mortgage contract: capital repayment, fixed "
            f"{current_rate * 100:.2f}% with a £{payment:,.2f} monthly "
            "payment.",
            f"Original contractual mortgage-free date: "
            f"{_month_year(original_contractual_eta)}, based on a "
            f"{int(numeric['original_term_months'])}-month term beginning "
            f"{_month_year(numeric['mortgage_start'])}.",
            f"Projected remaining interest sensitivity: low "
            f"£{projected.interest_low:,.0f}, expected "
            f"£{projected.interest_base:,.0f}, high "
            f"£{projected.interest_high:,.0f}.",
            "Affordability is not assessed because verified household "
            "income and expenditure evidence is outside this Burn.",
            "Low, expected and high paths are deterministic rate "
            "sensitivities, not probabilities.",
            "Equity composition is explanatory attribution only. Current "
            "equity is property value minus mortgage balance; principal "
            "repaid is initial mortgage minus current balance; valuation "
            "movement is current value minus purchase price. Interest is "
            "excluded, and monthly payment is never used to infer principal "
            "repayment.",
            "Mortgage Freedom selects eligible dated valuations of the "
            "secured property. Net Worth retains its existing latest-applicable "
            "Finance valuation policy.",
        ]
        if purchase_detail is not None:
            limitations.insert(1, purchase_detail)
        missing_composition = []
        if initial_deposit is None:
            missing_composition.append("initial deposit")
        if purchase_price is None:
            missing_composition.append("purchase price")
        if missing_composition:
            limitations.append(
                "Equity composition is partially unavailable because "
                + " and ".join(missing_composition)
                + " evidence is not recorded.")
        if acquisition_costs is not None:
            limitations.append(
                "Acquisition costs are disclosed separately and do not form "
                "part of current property equity.")
        if initial_deposit is not None and valuation_movement is not None:
            attributed_equity = (
                initial_deposit + principal_repaid + valuation_movement)
            difference = current_equity - attributed_equity
            if not math.isclose(difference, 0.0, abs_tol=.01):
                limitations.append(
                    "The explanatory components differ from current equity "
                    f"by £{abs(difference):,.2f}; every observation remains "
                    "visible and no automatic correction is applied.")
        for field in ACQUISITION_FIELDS:
            history = acquisition_history[field]
            if self._has_conflicting_values(history):
                limitations.append(
                    f"Conflicting {EVIDENCE_LABELS[field]} evidence remains "
                    f"visible ({len(history)} observations); the latest "
                    "effective observation is displayed and no evidence is "
                    "automatically corrected.")
        if overpayments:
            limitations.append(
                f"The observed balance follows {len(overpayments)} recorded "
                "historical one-off overpayments; no recurrence is assumed.")
        if balance_status == "stale":
            limitations.append("Mortgage balance evidence is stale.")
        if valuation_status == "stale":
            limitations.append(
                "The dated valuation reference is stale; loan-to-value "
                "and margin should be treated cautiously.")
        if any(record.confidence < .5 for record in overpayments):
            limitations.append(
                "Low-confidence overpayment evidence reduces Mission "
                "Confidence but does not determine Mission Margin.")
        if runway_value is None:
            limitations.append(
                "Liquidity evidence is absent; no acceleration "
                "recommendation is made.")
        elif runway_value < inputs.liquidity_floor_months:
            limitations.append(
                f"Overpayment is not recommended because current liquidity "
                f"runway is {runway_value:.1f} months, below Mortgage "
                f"Freedom's declared "
                f"{inputs.liquidity_floor_months:g}-month recommendation "
                "floor. Preserve emergency liquidity before deploying "
                "additional capital.")
        elif runway.limitations:
            limitations.extend(
                f"Liquidity runway: {note}" for note in runway.limitations)

        sampled = tuple(
            point for index, point in enumerate(projected.points)
            if index % 3 == 0 or index == len(projected.points) - 1)
        trajectory = tuple(sorted((
            TrajectoryPoint(numeric["mortgage_start"], original),
            TrajectoryPoint(records["balance"].effective_at, balance),
        ), key=lambda point: point.at))
        return MissionAssessment(
            mission_id=mission.id,
            policy_id=request.policy_id,
            scope=request.scope,
            as_of=request.as_of,
            status=status,
            calculation_version=CALCULATION_VERSION,
            current_value=current,
            mission_complete=complete,
            eta=projected.payoff_base,
            applicability=InstrumentApplicability(
                eta=(
                    "applicable"
                    if projected.payoff_base is not None
                    else "unavailable"
                ),
            ),
            trajectory_state=trajectory_state,
            trajectory_tone=tone,
            trajectory_movement=self._trajectory_movement(trajectory),
            confidence=confidence,
            current_milestone=current_milestone,
            milestones=milestones,
            mission_margin=margin,
            delta_v=delta_v,
            trajectory=trajectory,
            forecast=sampled,
            telemetry=telemetry,
            recommendations=recommendations,
            input_references=assessment_input_refs,
            evidence_references=assessment_evidence_refs,
            assumption_references=assumption_refs,
            limitations=tuple(limitations),
            confidence_basis=(
                "LOW / EXPECTED / HIGH RATE SENSITIVITY · "
                "OBSERVATIONS AND PROJECTIONS REMAIN DISTINCT · "
                "NOT A PROBABILITY"),
            forecast_resolution="month",
        )

    @staticmethod
    def _trajectory_movement(
        points: tuple[TrajectoryPoint, ...],
    ) -> str:
        if len(points) < 2 or points[0].at >= points[-1].at:
            return "unknown"
        if points[-1].value < points[0].value:
            return "advancing"
        if points[-1].value > points[0].value:
            return "receding"
        return "holding"

    def _unavailable(
        self, request: MissionAssessmentRequest, reason: str
    ) -> MissionAssessment:
        return MissionAssessment.unavailable(
            request, reason, CALCULATION_VERSION)

    def _scoped_mortgage(self, household_id: str):
        household = self.core.parties[household_id]
        members = tuple(
            member for member in self.core.members_of(household_id)
            if member.status == "active")
        member_ids = {member.id for member in members}
        candidates = []
        for obligation in self.finance.obligations.values():
            if obligation.status != "active" \
                    or obligation.liability_category != "mortgage":
                continue
            borrowers = {
                link.target for link in obligation.ownership
                if link.relation == "owes"
            }
            secured_ids = {
                link.target for link in obligation.ownership
                if link.relation == "secures"
            }
            secured_assets = tuple(
                self.finance.assets.get(asset_id)
                for asset_id in secured_ids)
            asset = secured_assets[0] if len(secured_assets) == 1 else None
            asset_owners = {
                link.target for link in asset.ownership
                if link.relation in ("owner", "co_owner")
            } if asset is not None else set()
            if (
                borrowers
                and borrowers <= member_ids
                and asset is not None
                and asset.status == "active"
                and asset.asset_category == "property"
                and obligation.currency == self.policy.unit_or_currency
                and asset.currency == self.policy.unit_or_currency
                and asset_owners
                and asset_owners <= member_ids
            ):
                candidates.append((
                    obligation, asset, borrowers | asset_owners))
        if len(candidates) == 1:
            obligation, asset, relevant_party_ids = candidates[0]
            scope_refs = {
                *household.provenance,
                *household.history,
                *obligation.provenance,
                *obligation.history,
                *asset.provenance,
                *asset.history,
            }
            for member in members:
                if member.id in relevant_party_ids:
                    scope_refs.update(member.provenance)
                    scope_refs.update(member.history)
            return obligation, asset, tuple(sorted(scope_refs)), ""
        if not candidates:
            return None, None, (), "one active household mortgage was not found"
        return None, None, (), "more than one active household mortgage was found"

    def _property_valuation_candidate(
        self, obligation_id: str, property_id: str, as_of: float,
    ) -> PropertyValuationCandidate | None:
        """Select an eligible secured-property observation without rewriting history."""
        event_order = {
            event["id"]: index
            for index, event in enumerate(self.finance.log.events())
        }
        candidates: list[PropertyValuationCandidate] = []
        for valuation in self.finance.valuations_of(property_id):
            event_id = valuation.provenance[0] if valuation.provenance else ""
            event = self.finance.log.get(event_id) if event_id else None
            provenance = event["payload"].get("provenance") if event else None
            if not (
                isinstance(valuation.amount, (int, float))
                and not isinstance(valuation.amount, bool)
                and math.isfinite(float(valuation.amount)) and valuation.amount > 0
                and valuation.currency == self.policy.unit_or_currency
                and isinstance(valuation.as_of, (int, float))
                and not isinstance(valuation.as_of, bool)
                and math.isfinite(float(valuation.as_of)) and valuation.as_of <= as_of
                and valuation.valuation_basis in VALUATION_BASES
                and isinstance(valuation.source, str) and valuation.source.strip()
                and isinstance(provenance, dict)
                and all(isinstance(provenance.get(key), str) and provenance[key]
                        for key in ("evidence_id", "proposal_id", "confirmed_by"))
            ):
                continue
            candidates.append(PropertyValuationCandidate(
                float(valuation.amount), float(valuation.as_of), valuation.source.strip(),
                valuation.valuation_basis, event_id))
        for record in self.evidence.for_obligation(obligation_id, as_of):
            if record.field != "property_valuation":
                continue
            if (not isinstance(record.value, (int, float)) or isinstance(record.value, bool)
                    or not math.isfinite(float(record.value)) or record.value <= 0
                    or record.unit_or_currency != self.policy.unit_or_currency):
                continue
            basis_record = self.evidence.latest(obligation_id, "valuation_basis", as_of)
            basis = (
                basis_record.value
                if basis_record is not None and isinstance(basis_record.value, str)
                else None
            )
            candidates.append(PropertyValuationCandidate(
                float(record.value), record.effective_at, record.source, basis,
                record.event_id, record))
        if not candidates:
            return None
        return max(
            candidates,
            key=lambda item: (item.effective_at, event_order.get(item.event_id, -1)),
        )

    @staticmethod
    def _numeric(record: MortgageEvidence | None, field: str) -> float:
        if record is None or isinstance(record.value, bool) \
                or not isinstance(record.value, (int, float)) \
                or not math.isfinite(float(record.value)):
            label = EVIDENCE_LABELS.get(field, "required mortgage evidence")
            raise ValueError(f"Mortgage evidence {label} must be numeric")
        return float(record.value)

    @staticmethod
    def _string(record: MortgageEvidence | None, field: str) -> str:
        if record is None or not isinstance(record.value, str) \
                or not record.value.strip():
            label = EVIDENCE_LABELS.get(field, "required mortgage evidence")
            raise ValueError(f"Mortgage evidence {label} must be text")
        return record.value

    @staticmethod
    def _purchase_date_label(
        record: MortgageEvidence | None,
    ) -> str | None:
        if record is None:
            return None
        if isinstance(record.value, str):
            year, month = record.value.split("-")
            return f"{MONTH_NAMES[int(month) - 1]} {year}"
        if isinstance(record.value, (int, float)):
            return _month_year(float(record.value))
        return None

    @staticmethod
    def _has_conflicting_values(
        records: tuple[MortgageEvidence, ...],
    ) -> bool:
        return len({
            (record.value, record.unit_or_currency)
            for record in records
        }) > 1

    @staticmethod
    def _validate_contract(numeric: dict[str, float],
                           text: dict[str, str]) -> None:
        if numeric["original_advance"] <= 0:
            raise ValueError("Original advance must be positive")
        if not 0 <= numeric["balance"] <= numeric["original_advance"]:
            raise ValueError(
                "Mortgage balance must be between zero and original advance")
        if not 0 <= numeric["interest_rate"] <= 1:
            raise ValueError("Interest rate must be between zero and one")
        if numeric["monthly_payment"] <= 0:
            raise ValueError("Monthly payment must be positive")
        if numeric["remaining_term_months"] < 0:
            raise ValueError("Remaining term must be non-negative")
        if numeric["original_term_months"] <= 0 \
                or not numeric["original_term_months"].is_integer():
            raise ValueError("Original term must be a positive whole month")
        if text["property_role"] != "primary_residence":
            raise ValueError("Mortgage must secure the primary residence")
        if text["repayment_type"] != "capital_repayment":
            raise ValueError(
                "Only capital-repayment mortgages are supported")
        if text["interest_type"] != "fixed":
            raise ValueError("Only a declared fixed-rate period is supported")
        if numeric["fixed_rate_expiry"] < numeric["mortgage_start"]:
            raise ValueError(
                "Fixed-rate expiry cannot predate mortgage start")

    @staticmethod
    def _validate_units(
        records: dict[str, MortgageEvidence | None]
    ) -> None:
        for field in (
            "original_advance",
            "balance",
            "monthly_payment",
        ):
            record = records[field]
            if record is None or record.unit_or_currency != "GBP":
                raise ValueError(
                    f"Mortgage evidence "
                    f"{EVIDENCE_LABELS.get(field, 'required value')} "
                    "must be denominated in GBP")

    @staticmethod
    def _is_stale(
        as_of: float, record: MortgageEvidence | None, max_days: int
    ) -> bool:
        return record is None or as_of - record.effective_at > max_days * DAY

    @classmethod
    def _confidence(
        cls,
        as_of: float,
        records: dict[str, MortgageEvidence | None],
        inputs: MortgageProjectionInputs,
        contributing_evidence: tuple[MortgageEvidence, ...] = (),
        *,
        valuation_effective_at: float,
        valuation_record: MortgageEvidence | None,
    ) -> MissionConfidence:
        stale = []
        if cls._is_stale(
                as_of, records["balance"], inputs.balance_stale_after_days):
            stale.append("balance")
        if as_of - valuation_effective_at > inputs.valuation_stale_after_days * DAY:
            stale.append("property valuation")
        minimum = min(
            (
                *(record.confidence for record in records.values()
                  if record is not None),
                *(record.confidence for record in contributing_evidence),
                *((valuation_record.confidence,) if valuation_record is not None else ()),
            ))
        if minimum < .5:
            return MissionConfidence(
                "Insufficient",
                "contributing manual evidence has insufficient confidence")
        if stale:
            return MissionConfidence(
                "Provisional",
                f"manual evidence is attributable but stale: {', '.join(stale)}")
        if minimum >= .9:
            return MissionConfidence(
                "Supported",
                "fresh, attributable manual evidence supports the assessment")
        return MissionConfidence(
            "Provisional",
            "manual evidence is attributable but carries provisional confidence")

    @staticmethod
    def _schedule_assessment(
        complete: bool,
        low_eta: float | None,
        base_eta: float | None,
        _high_eta: float | None,
        target_date: float,
    ) -> tuple[str, str, str]:
        """Compare the expected payoff with the original contract schedule.

        Sensitivity paths remain visible evidence, but neither the pessimistic
        rate path nor a resilience-constrained recommendation can erase
        material acceleration already present in the expected path.
        """
        if complete:
            return "green", "Complete", "green"
        if base_eta is not None and base_eta <= target_date - MONTH:
            return "green", "Accelerated", "green"
        if base_eta is not None and base_eta <= target_date + DAY:
            return "amber", "Nominal", "amber"
        if low_eta is not None and low_eta <= target_date + DAY:
            return "amber", "Constrained", "amber"
        if base_eta is None:
            return "red", "Critical", "red"
        return "red", "Divergent", "red"

    @staticmethod
    def _eta_for_balance(
        projection: MortgageProjection, value: float
    ) -> float | None:
        return next(
            (point.at for point in projection.points
             if point.base <= value),
            None)

    @classmethod
    def _milestones(
        cls, balance: float, original: float,
        projection: MortgageProjection,
    ) -> tuple[MissionMilestone, ...]:
        three_quarters = original * .75
        one_quarter = original * .25
        if balance == 0:
            current = "mortgage_free"
        elif balance <= one_quarter:
            current = "final_approach"
        elif balance <= three_quarters:
            current = "building_equity"
        else:
            current = "repayment_underway"
        definitions = (
            ("repayment_underway", "Repayment Underway",
             three_quarters, None, original, 0),
            ("building_equity", "Building Equity",
             one_quarter, three_quarters, three_quarters, 1),
            ("final_approach", "Final Approach",
             0.0, one_quarter, one_quarter, 2),
            ("mortgage_free", "Mortgage Free",
             0.0, 1.0, 0.0, 3),
        )
        current_order = next(
            order for id_, _, _, _, _, order in definitions
            if id_ == current)
        items = []
        for id_, label, lower, upper, destination, order in definitions:
            if id_ == "repayment_underway":
                completion = max(
                    0.0, min(1.0, (original - balance) / (original * .25)))
            elif id_ == "building_equity":
                completion = max(
                    0.0, min(
                        1.0, (three_quarters - balance) / (original * .5)))
            elif id_ == "final_approach":
                completion = max(
                    0.0, min(1.0, (one_quarter - balance) / one_quarter))
            else:
                completion = 1.0 if balance == 0 else 0.0
            items.append(MissionMilestone(
                id=id_,
                label=label,
                lower_bound=lower,
                upper_bound=upper,
                completion=completion,
                order=order,
                unit_or_currency="GBP",
                is_current=id_ == current,
                is_complete=(
                    order < current_order
                    or (id_ == "mortgage_free" and balance == 0)),
                completes_mission=id_ == "mortgage_free",
                estimated_at=cls._eta_for_balance(projection, destination),
                destination_direction="lower_is_better",
                destination_value=destination,
            ))
        return tuple(items)

    @staticmethod
    def _margin_band(value: float, thresholds: tuple[float, float, float]):
        if value >= thresholds[2]:
            return 3
        if value >= thresholds[1]:
            return 2
        if value >= thresholds[0]:
            return 1
        return 0

    @classmethod
    def _mission_margin(
        cls,
        ltv: float,
        runway_value: float | None,
        fixed_months: float,
        overpayments: tuple[MortgageEvidence, ...],
    ) -> MissionMargin:
        ltv_band = 3 if ltv <= .5 else 2 if ltv <= .65 \
            else 1 if ltv <= .8 else 0
        runway_band = (
            cls._margin_band(runway_value, (6.0, 12.0, 18.0))
            if runway_value is not None else 0)
        fixed_band = cls._margin_band(fixed_months, (3.0, 6.0, 12.0))
        flexibility_band = 3 if overpayments else 1
        bands = (ltv_band, runway_band, fixed_band, flexibility_band)
        if min(bands) == 0:
            state = "Negative Margin"
        elif min(bands) == 1:
            state = "Low Margin"
        elif all(band == 3 for band in bands):
            state = "High Margin"
        else:
            state = "Adequate Margin"
        return MissionMargin(
            pace_percent=None,
            schedule_buffer_days=None,
            state=state,
            label="LTV BUFFER",
            value=1.0 - ltv,
            unit_or_currency=None,
            format_kind="percent",
            description=(
                f"LTV {ltv * 100:.1f}%, runway "
                f"{runway_value:.1f} months"
                if runway_value is not None else
                f"LTV {ltv * 100:.1f}%; runway unavailable")
            + f", fixed protection {fixed_months:.1f} months, "
              f"{len(overpayments)} recorded overpayment(s)",
        )

    @staticmethod
    def _delta_v(
        contractual_eta: float | None,
        current_eta: float | None,
        mortgage_start: float,
        as_of: float,
        complete: bool,
    ) -> DeltaV:
        lookback = max(0, int(round((as_of - mortgage_start) / DAY)))
        schedule_metadata = {
            "period_label": "SINCE FIRST PAYMENT",
            "reference_start_at": mortgage_start,
            "reference_start_label": "ORIGINAL START",
        }
        if contractual_eta is not None:
            schedule_metadata.update({
                "reference_destination_at": contractual_eta,
                "reference_destination_label": "ORIGINAL DESTINATION",
            })
        if complete:
            return DeltaV(
                None, lookback,
                "Mission complete; payoff acceleration no longer applies",
                **schedule_metadata)
        if contractual_eta is None or current_eta is None:
            return DeltaV(
                None, lookback,
                "Payoff acceleration is unavailable within the model horizon",
                **schedule_metadata)
        days = (contractual_eta - current_eta) / DAY
        months = (
            0 if abs(days) < MONTH_DAYS
            else int(round(days / MONTH_DAYS)))
        direction = "accelerated" if days >= 0 else "delayed"
        return DeltaV(
            days, lookback,
            f"Estimated time {direction} against the original contractual "
            "mortgage-free date",
            months=months,
            direction=direction,
            **schedule_metadata,
        )

    def _recommendation(
        self,
        balance: float,
        request: MissionAssessmentRequest,
        inputs: MortgageProjectionInputs,
        assumption_set: AssumptionSet,
        current_rate: float,
        payment: float,
        fixed_expiry: float,
        baseline: MortgageProjection,
        runway_value: float | None,
        evidence_refs: tuple[str, ...],
    ) -> tuple[RecommendationAssessment, ...]:
        if runway_value is None or baseline.payoff_base is None:
            return ()
        if runway_value < inputs.liquidity_floor_months:
            action = (
                f"Preserve emergency liquidity: current runway is "
                f"{runway_value:.1f} months, below the declared "
                f"{inputs.liquidity_floor_months:g}-month overpayment floor."
            )
            return (RecommendationAssessment(
                action=action,
                scenario_id="financial-resilience-precedence",
                estimated_delta_v_days=None,
                status="suppressed",
                action_type="preserve_liquidity",
                action_label="Preserve emergency liquidity",
                limitations=(action,),
                evidence_references=evidence_refs,
            ),)
        candidates = []
        for scenario in self.finance.scenarios.values():
            if scenario.status != "active" \
                    or scenario.assumption_set_id != assumption_set.id:
                continue
            amount = scenario.adjustments.get(
                "monthly_mortgage_overpayment")
            structured = (
                scenario.action_type,
                scenario.action_label,
                scenario.unit_or_currency,
                scenario.cadence,
            )
            if isinstance(amount, bool) \
                    or not isinstance(amount, (int, float)) \
                    or not math.isfinite(float(amount)) or amount <= 0 \
                    or not all(
                        isinstance(value, str) and value.strip()
                        for value in structured) \
                    or scenario.unit_or_currency != "GBP" \
                    or scenario.cadence != "month":
                continue
            projected = self.projection.project(
                balance, request.as_of, inputs,
                current_rate=current_rate,
                monthly_payment=payment,
                fixed_rate_expiry=fixed_expiry,
                monthly_overpayment=float(amount),
            )
            if projected.payoff_base is None \
                    or projected.payoff_base >= baseline.payoff_base:
                continue
            days = (baseline.payoff_base - projected.payoff_base) / DAY
            interest_avoided = max(
                0.0, baseline.interest_base - projected.interest_base)
            months = max(1, int(round(days / MONTH_DAYS)))
            action = (
                f"Add £{float(amount):,.0f} per month; the expected path "
                f"pays off {months} month(s) sooner and avoids "
                f"£{interest_avoided:,.0f} projected interest under the "
                "declared rate assumptions.")
            candidates.append((days, RecommendationAssessment(
                action=action,
                scenario_id=scenario.id,
                estimated_delta_v_days=days,
                action_type=scenario.action_type or "",
                action_label=scenario.action_label or "",
                amount=float(amount),
                unit_or_currency=scenario.unit_or_currency,
                cadence=scenario.cadence,
                adjustment_key="monthly_mortgage_overpayment",
                estimated_delta_v_months=months,
                delta_v_direction="accelerated",
                assumption_references=tuple(sorted({
                    *assumption_set.provenance, *scenario.provenance})),
                evidence_references=evidence_refs,
            )))
        if not candidates:
            return ()
        return (max(candidates, key=lambda candidate: candidate[0])[1],)

    @staticmethod
    def _finite_metric_value(
        result: MetricResult, request: MissionAssessmentRequest
    ) -> float | None:
        value = result.value
        if result.metric_id != "finance.liquidity_runway" \
                or result.scope != request.scope \
                or result.as_of != request.as_of \
                or result.unit_or_currency != "months" \
                or result.status not in ("available", "stale") \
                or isinstance(value, bool) \
                or not isinstance(value, (int, float)) \
                or not math.isfinite(float(value)):
            return None
        return float(value)

    @staticmethod
    def _metric(
        metric_id: str,
        value: float,
        unit: str | None,
        request: MissionAssessmentRequest,
        status: str,
        input_refs: tuple[str, ...],
        evidence_refs: tuple[str, ...],
        assumption_refs: tuple[str, ...],
    ) -> MetricResult:
        return MetricResult(
            metric_id=metric_id,
            value=value,
            unit_or_currency=unit,
            scope=request.scope,
            as_of=request.as_of,
            status=status,
            calculation_version=CALCULATION_VERSION,
            input_references=input_refs,
            evidence_references=evidence_refs,
            assumption_references=assumption_refs,
            generated_at=request.as_of,
        )

    @staticmethod
    def _unavailable_metric(
        metric_id: str,
        request: MissionAssessmentRequest,
        reason: str,
        input_refs: tuple[str, ...],
        evidence_refs: tuple[str, ...],
        assumption_refs: tuple[str, ...],
    ) -> MetricResult:
        return MetricResult(
            metric_id=metric_id,
            value=None,
            unit_or_currency="GBP",
            scope=request.scope,
            as_of=request.as_of,
            status="unavailable",
            calculation_version=CALCULATION_VERSION,
            input_references=input_refs,
            evidence_references=evidence_refs,
            assumption_references=assumption_refs,
            generated_at=request.as_of,
            limitations=(reason,),
        )

    def _partial_projection_failure(
        self,
        *,
        request: MissionAssessmentRequest,
        mission,
        assumption_refs: tuple[str, ...],
        mortgage_input_refs: tuple[str, ...],
        mortgage_evidence_refs: tuple[str, ...],
        valuation_evidence_refs: tuple[str, ...],
        acquisition_history,
        valuation_basis_records,
        current: MetricResult,
        balance: float,
        original: float,
        valuation: float,
        current_equity: float,
        principal_repaid: float,
        fixed_months: float,
        purchase_price_record,
        purchase_date_record,
        initial_deposit_record,
        acquisition_costs_record,
        valuation_basis_record,
        valuation_status: str,
        balance_status: str,
        ltv: float,
        text: dict[str, str],
        current_rate: float,
        payment: float,
        original_contractual_eta: float,
        confidence: MissionConfidence,
        valuation_effective_at: float,
        valuation_source: str,
        reason: str,
    ) -> MissionAssessment:
        del valuation_basis_records
        del purchase_price_record, purchase_date_record
        del initial_deposit_record, acquisition_costs_record
        projected = MortgageProjection(
            points=(ForecastPoint(request.as_of, balance, balance, balance),),
            payoff_low=None,
            payoff_base=None,
            payoff_high=None,
            interest_low=0.0,
            interest_base=0.0,
            interest_high=0.0,
        )
        milestones = tuple(
            replace(item, estimated_at=None)
            for item in self._milestones(balance, original, projected)
        )
        current_milestone = next(
            item for item in milestones if item.is_current)
        valuation_month = _month_year(valuation_effective_at)
        if valuation_basis_record is not None and valuation_basis_record.value is not None:
            valuation_basis = str(
                valuation_basis_record.value).replace("_", " ").capitalize()
            valuation_reference = (
                f"Estimated · {valuation_basis} · "
                f"{valuation_source} · {valuation_month}"
            )
        else:
            valuation_reference = (
                "Estimated · Valuation basis: Not recorded; not inferred · "
                f"{valuation_source} · {valuation_month}"
            )
        current_position_status = (
            "stale"
            if balance_status == "stale" or valuation_status == "stale"
            else "available")
        telemetry = (
            TelemetryItem(
                current,
                "MORTGAGE BALANCE",
                "currency",
                f"OBSERVED · {_month_year(request.as_of).upper()}",
                display_region="essential",
            ),
            TelemetryItem(
                self._metric(
                    "finance.property_current_equity",
                    current_equity,
                    self.policy.unit_or_currency,
                    request,
                    current_position_status,
                    mortgage_input_refs,
                    tuple(sorted({
                        *valuation_evidence_refs,
                        *current.evidence_references,
                    })),
                    assumption_refs,
                ),
                "CURRENT POSITION · CURRENT EQUITY",
                "currency",
                "PROPERTY VALUE - MORTGAGE BALANCE",
                display_region="essential",
            ),
            TelemetryItem(
                self._metric(
                    "finance.property_valuation",
                    valuation,
                    self.policy.unit_or_currency,
                    request,
                    valuation_status,
                    mortgage_input_refs,
                    valuation_evidence_refs,
                    assumption_refs,
                ),
                "CURRENT POSITION · PROPERTY VALUATION",
                "currency",
                valuation_reference,
                display_group="CURRENT POSITION",
            ),
            TelemetryItem(
                self._metric(
                    "finance.mortgage_ltv",
                    ltv,
                    None,
                    request,
                    valuation_status,
                    mortgage_input_refs,
                    valuation_evidence_refs,
                    assumption_refs,
                ),
                "CURRENT POSITION · CURRENT LTV",
                "percent",
                valuation_reference,
                display_group="CURRENT POSITION",
            ),
            TelemetryItem(
                self._metric(
                    "finance.mortgage_interest_rate",
                    current_rate,
                    None,
                    request,
                    "available",
                    mortgage_input_refs,
                    mortgage_evidence_refs,
                    assumption_refs,
                ),
                "CURRENT POSITION · INTEREST RATE",
                "percent",
                display_group="CURRENT POSITION",
            ),
            TelemetryItem(
                self._metric(
                    "finance.mortgage_payment",
                    payment,
                    self.policy.unit_or_currency,
                    request,
                    "available",
                    mortgage_input_refs,
                    mortgage_evidence_refs,
                    assumption_refs,
                ),
                "CURRENT POSITION · MONTHLY PAYMENT",
                "currency",
                display_group="CURRENT POSITION",
            ),
            TelemetryItem(
                self._metric(
                    "finance.mortgage_fixed_protection",
                    fixed_months,
                    "months",
                    request,
                    "available",
                    mortgage_input_refs,
                    mortgage_evidence_refs,
                    assumption_refs,
                ),
                "CURRENT POSITION · FIXED-RATE PROTECTION",
                "months",
                display_group="CURRENT POSITION",
            ),
            TelemetryItem(
                self._metric(
                    "finance.mortgage_principal_repaid",
                    principal_repaid,
                    self.policy.unit_or_currency,
                    request,
                    balance_status,
                    mortgage_input_refs,
                    tuple(sorted({
                        *current.evidence_references,
                        *tuple(record.event_id for record in
                               acquisition_history["original_advance"]),
                    })),
                    assumption_refs,
                ),
                "EQUITY COMPOSITION · PRINCIPAL REPAID",
                "currency",
                "INITIAL MORTGAGE - CURRENT BALANCE",
                display_group="EQUITY AND VALUATION ANALYSIS",
            ),
        )
        return MissionAssessment(
            mission_id=mission.id,
            policy_id=request.policy_id,
            scope=request.scope,
            as_of=request.as_of,
            status="none",
            completeness="partial",
            calculation_version=CALCULATION_VERSION,
            current_value=current,
            mission_complete=balance == 0.0,
            eta=None,
            applicability=InstrumentApplicability(
                eta="unavailable",
                delta_v="unavailable",
                trajectory="unavailable",
                forecast="unavailable",
                margin="unavailable",
            ),
            trajectory_state=None,
            trajectory_tone="none",
            confidence=MissionConfidence("Provisional", reason),
            current_milestone=current_milestone,
            milestones=milestones,
            mission_margin=None,
            delta_v=None,
            trajectory=(),
            forecast=(),
            telemetry=telemetry,
            recommendations=(),
            input_references=mortgage_input_refs,
            evidence_references=tuple(sorted({
                *mortgage_evidence_refs,
                *valuation_evidence_refs,
            })),
            assumption_references=assumption_refs,
            limitations=(
                f"Original contractual mortgage-free date: "
                f"{_month_year(original_contractual_eta)}.",
                f"Mortgage contract: capital repayment, fixed "
                f"{current_rate * 100:.2f}% with a £{payment:,.2f} monthly payment.",
                reason,
            ),
            confidence_basis=reason,
            forecast_resolution="month",
        )

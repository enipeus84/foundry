"""RFC-007 Mortgage Freedom assessment and deterministic policy."""

from dataclasses import replace

import pytest

from foundry.core import grammar
from foundry.core.entities import (
    EntityProjection,
    declare_mission,
    declare_party,
    join_household,
)
from foundry.core.metrics import MetricRegistry, MetricRequest, MetricResult
from foundry.core.mission_assessment import (
    MissionAssessmentRegistry,
    MissionAssessmentRequest,
)
from foundry.core.mission_targets import MissionTargetProjection, TargetQuantity
from foundry.core.scope import Subject
from foundry.eventlog import EventLog
from foundry.finance import entities as fin
from foundry.finance.entities import FinanceEntityProjection
from foundry.finance.metrics import FinanceMetricProvider
from foundry.finance.mortgage_assessment import (
    DAY,
    MONTH,
    YEAR,
    POLICY_ID,
    TARGET_METRIC,
    MortgageFreedomAssessor as _MortgageFreedomAssessor,
    MortgageProjectionEngine,
    MortgageProjectionInputs,
    _add_calendar_months,
    _month_year,
)
from foundry.finance.mission_targets import FinanceTargetMetricResolver
from foundry.finance.missions import register_finance_mission_definitions
from foundry.finance.mortgage_evidence import (
    MortgageEvidenceProjection,
    record_mortgage_evidence,
)


# This must remain after the real event clock so fixture Targets can be
# validly declared after their Mission and still be in force at assessment.
NOW = 1_800_000_000.0


def _targets(log):
    definitions = MissionAssessmentRegistry()
    register_finance_mission_definitions(definitions)
    return MissionTargetProjection(
        log, EntityProjection(log), definitions, FinanceTargetMetricResolver())


class MortgageFreedomAssessor(_MortgageFreedomAssessor):
    """Keep legacy fixture call sites focused on the assessment under test."""

    def __init__(self, finance, core, metrics, evidence, targets=None):
        super().__init__(
            finance, core, metrics, evidence, targets or _targets(core.log))


class RunwayProvider:
    def __init__(self, months=18.0):
        self.months = months

    def owned_metric_ids(self):
        return frozenset({"finance.liquidity_runway"})

    def calculate(self, request):
        return MetricResult(
            request.metric_id, self.months, "months", request.scope,
            request.as_of, "available", "test-v1",
            input_references=("runway-input",),
            evidence_references=("runway-evidence",),
            generated_at=request.as_of)


def _record(log, mortgage_id, field, value, *,
            effective_at=NOW - 10 * DAY, confidence=.95,
            unit_or_currency=None):
    return record_mortgage_evidence(
        log, mortgage_id, field, value, effective_at,
        confidence=confidence, source="manual lender statement",
        lineage="NatWest statement supplied by household",
        unit_or_currency=unit_or_currency)


def _fixture(path, *, runway=18.0, include_scenario=True,
             include_overpayments=True, overpayment_confidence=.95,
             valuation_effective_at=NOW - 10 * DAY,
             balance_effective_at=NOW - 10 * DAY,
             balance=242_540.09, valuation=436_638.42,
             acquisition_costs=None, omit=()):
    log = EventLog(path)
    household = declare_party(log, "household")
    member = declare_party(log, "person")
    join_household(log, member.id, household.id)
    home = fin.declare_asset(log, "property", "GBP")
    fin.link_ownership(log, "asset", home.id, "owner", member.id)
    mortgage = fin.declare_obligation(
        log, "mortgage", "GBP", amount=balance)
    fin.link_ownership(log, "obligation", mortgage.id, "owes", member.id)
    fin.link_ownership(log, "obligation", mortgage.id, "secures", home.id)

    assumptions = fin.declare_assumption_set(
        log, "Mortgage Freedom baseline", "v1", {
            "low_post_fix_rate": .0333,
            "base_post_fix_rate": .0433,
            "high_post_fix_rate": .0533,
            "forecast_horizon_months": 480.0,
            "balance_stale_after_days": 120.0,
            "valuation_stale_after_days": 365.0,
            "liquidity_floor_months": 12.0,
        })
    if include_scenario:
        fin.declare_scenario(
            log, "Test a £250 monthly overpayment", assumptions.id,
            {"monthly_mortgage_overpayment": 250.0},
            action_type="increase_mortgage_payment",
            action_label="Add mortgage overpayment",
            unit_or_currency="GBP",
            cadence="month")
    mortgage_start = NOW - 365 * DAY
    original_term_months = 300
    mission = declare_mission(
        log, "Mortgage free by contractual term",
        target_metric=TARGET_METRIC, target_value=0.0,
        target_date=_add_calendar_months(
            mortgage_start, original_term_months),
        assessment_policy_id=POLICY_ID,
        assumption_set_id=assumptions.id)
    _targets(log).declare(
        household_id=household.id, subject_id=household.id,
        mission_id=mission.id, metric_id=TARGET_METRIC,
        destination=TargetQuantity(0.0, "GBP", "currency"),
        destination_direction="lower_is_better", horizon_kind="by_date",
        horizon_at=mission.target_date,
        effective_from=log.get(mission.provenance[0])["ts"] + 1.0)

    fields = {
        "property_role": "primary_residence",
        "purchase_price": 450_000.0,
        "purchase_date": NOW - 500 * DAY,
        "initial_deposit": 140_000.0,
        "property_valuation": valuation,
        "valuation_basis": "agent_appraisal",
        "lender": "NatWest",
        "original_advance": 310_000.0,
        "mortgage_start": mortgage_start,
        "balance": balance,
        "repayment_type": "capital_repayment",
        "interest_type": "fixed",
        "interest_rate": .0433,
        "monthly_payment": 1_701.47,
        "original_term_months": float(original_term_months),
        "remaining_term_months": 201.0,
        "fixed_rate_expiry": NOW + 367 * DAY,
    }
    if acquisition_costs is not None:
        fields["acquisition_costs"] = acquisition_costs
    for field, value in fields.items():
        if field in omit:
            continue
        effective_at = (
            valuation_effective_at if field == "property_valuation"
            else balance_effective_at if field == "balance"
            else NOW - 10 * DAY)
        _record(
            log, mortgage.id, field, value, effective_at=effective_at,
            unit_or_currency=(
                "GBP" if field in {
                    "purchase_price", "initial_deposit",
                    "acquisition_costs", "property_valuation",
                    "original_advance", "balance", "monthly_payment",
                } else None))
    if include_overpayments:
        _record(log, mortgage.id, "recorded_overpayment", 30_000.0,
                effective_at=NOW - 300 * DAY,
                confidence=overpayment_confidence,
                unit_or_currency="GBP")
        _record(log, mortgage.id, "recorded_overpayment", 30_000.0,
                effective_at=NOW - 100 * DAY,
                confidence=overpayment_confidence,
                unit_or_currency="GBP")

    core = EntityProjection(log)
    finance = FinanceEntityProjection(log)
    metrics = MetricRegistry()
    metrics.register(RunwayProvider(runway))
    assessor = MortgageFreedomAssessor(
        finance, core, metrics, MortgageEvidenceProjection(log))
    request = MissionAssessmentRequest(
        mission.id, POLICY_ID, Subject("party", household.id), NOW)
    return log, household, mortgage, assumptions, assessor, request


def _telemetry_by_id(result):
    return {item.result.metric_id: item for item in result.telemetry}


def _successor_target(log, household, mission, *, horizon_at,
                      destination=0.0, horizon_kind="by_date"):
    targets = _targets(log)
    predecessor = targets.in_force(mission.id, NOW)
    assert predecessor is not None
    return targets.declare(
        household_id=household.id, subject_id=household.id,
        mission_id=mission.id, metric_id=TARGET_METRIC,
        destination=TargetQuantity(destination, "GBP", "currency"),
        destination_direction="lower_is_better", horizon_kind=horizon_kind,
        horizon_at=horizon_at if horizon_kind == "by_date" else None,
        effective_from=predecessor.effective_from + 1.0,
        supersedes=predecessor.id)


def test_target_horizon_equal_to_contract_preserves_legacy_assessment(tmp_path):
    log, _, _, _, assessor, request = _fixture(tmp_path / "events.jsonl")

    result = assessor.assess(request)

    target = _targets(log).in_force(request.mission_id, request.as_of)
    assert target is not None
    assert target.horizon_at == assessor.core.missions[request.mission_id].target_date
    assert result.trajectory_state == "Accelerated"
    assert result.delta_v is not None
    assert target.id in result.input_references
    assert set(target.provenance) <= set(result.input_references)
    assert "finance.mortgage_target_horizon" in _telemetry_by_id(result)
    assert "finance.mortgage_target_adherence" in _telemetry_by_id(result)
    assert any("coincides with contractual maturity" in note for note in result.limitations)


def test_earlier_target_horizon_does_not_change_contractual_trajectory(tmp_path):
    log, household, _, _, assessor, request = _fixture(tmp_path / "events.jsonl")
    baseline = assessor.assess(request)
    maturity = assessor.core.missions[request.mission_id].target_date
    _successor_target(log, household, assessor.core.missions[request.mission_id],
                      horizon_at=maturity - 5 * YEAR)

    revised = MortgageFreedomAssessor(
        FinanceEntityProjection(log), EntityProjection(log), _metric_registry(18.0),
        MortgageEvidenceProjection(log)).assess(request)

    assert revised.trajectory_state == baseline.trajectory_state
    assert revised.delta_v == baseline.delta_v
    assert revised.eta == baseline.eta
    assert _telemetry_by_id(revised)["finance.mortgage_target_horizon"].result.value < maturity


def test_later_target_horizon_cannot_improve_contractual_trajectory(tmp_path):
    log, household, _, _, assessor, request = _fixture(tmp_path / "events.jsonl")
    baseline = assessor.assess(request)
    maturity = assessor.core.missions[request.mission_id].target_date
    _successor_target(log, household, assessor.core.missions[request.mission_id],
                      horizon_at=maturity + 5 * YEAR)

    revised = MortgageFreedomAssessor(
        FinanceEntityProjection(log), EntityProjection(log), _metric_registry(18.0),
        MortgageEvidenceProjection(log)).assess(request)

    assert revised.trajectory_state == baseline.trajectory_state
    assert revised.trajectory_tone == baseline.trajectory_tone
    assert revised.delta_v == baseline.delta_v
    assert any("later than contractual maturity" in note for note in revised.limitations)


def test_historical_target_resolution_uses_the_predecessor(tmp_path):
    log, household, _, _, assessor, request = _fixture(tmp_path / "events.jsonl")
    mission = assessor.core.missions[request.mission_id]
    predecessor = _targets(log).in_force(mission.id, request.as_of)
    assert predecessor is not None
    successor = _successor_target(
        log, household, mission, horizon_at=predecessor.horizon_at - YEAR)

    projection = _targets(log)
    assert projection.in_force(mission.id, predecessor.effective_from) == predecessor
    assert projection.in_force(mission.id, request.as_of) == successor


def test_absent_target_uses_the_new_failure_message(tmp_path):
    log, household, _, _, assessor, request = _fixture(tmp_path / "events.jsonl")
    target = _targets(log).in_force(request.mission_id, request.as_of)
    assert target is not None
    _targets(log).withdraw(household_id=household.id, target_id=target.id,
                           reason="test withdrawal")

    result = MortgageFreedomAssessor(
        FinanceEntityProjection(log), EntityProjection(log), _metric_registry(18.0),
        MortgageEvidenceProjection(log)).assess(request)

    assert result.status == "unavailable"
    assert result.limitations == (
        "no Mission Target is in force for this Mission at the assessment time",)


def test_conflicting_target_state_uses_the_governed_failure_message(tmp_path):
    log, household, _, _, assessor, request = _fixture(tmp_path / "events.jsonl")
    mission = assessor.core.missions[request.mission_id]
    target = _targets(log).in_force(mission.id, request.as_of)
    assert target is not None
    duplicate_id = grammar.new_id()
    grammar.declare(log, "core", "mission_target", duplicate_id, {
        "entity_id": duplicate_id, "mission_id": mission.id,
        "household_id": household.id, "subject_id": household.id,
        "metric_id": TARGET_METRIC, "destination_value": 0.0,
        "destination_unit": "GBP", "destination_dimension": "currency",
        "destination_direction": "lower_is_better", "horizon_kind": "by_date",
        "horizon_at": target.horizon_at,
        "effective_from": target.effective_from,
    })

    result = MortgageFreedomAssessor(
        FinanceEntityProjection(log), EntityProjection(log), _metric_registry(18.0),
        MortgageEvidenceProjection(log)).assess(request)

    assert result.status == "unavailable"
    assert result.limitations == ("Mission Target state is in conflict",)


def test_projection_is_deterministic_ordered_and_separate_from_observation():
    inputs = MortgageProjectionInputs(
        .0333, .0433, .0533, 360, 120, 365, 12.0)
    kwargs = dict(
        current_rate=.0433, monthly_payment=1_701.47,
        fixed_rate_expiry=NOW + 365 * DAY)
    first = MortgageProjectionEngine.project(
        242_540.09, NOW, inputs, **kwargs)
    second = MortgageProjectionEngine.project(
        242_540.09, NOW, inputs, **kwargs)

    assert first == second
    assert first.points[0].low == first.points[0].base \
        == first.points[0].high == 242_540.09
    assert all(
        point.low <= point.base <= point.high for point in first.points)
    assert first.payoff_low <= first.payoff_base <= first.payoff_high
    assert first.interest_low <= first.interest_base <= first.interest_high


def test_projection_matches_hand_calculation_across_fixed_rate_boundary():
    inputs = MortgageProjectionInputs(
        0.0, 0.0, 0.0, 2, 120, 365, 12.0)

    result = MortgageProjectionEngine.project(
        100.0, NOW, inputs,
        current_rate=.12,
        monthly_payment=60.0,
        fixed_rate_expiry=NOW)

    assert tuple(point.base for point in result.points) == (100.0, 41.0, 0.0)
    assert result.interest_low == result.interest_base \
        == result.interest_high == pytest.approx(1.0)
    assert result.payoff_low == result.payoff_base \
        == result.payoff_high == NOW + 2 * MONTH
    assert result.points[-1].base == 0.0


def test_full_assessment_is_lower_is_better_and_has_complete_output(tmp_path):
    log, _, mortgage, _, assessor, request = _fixture(
        tmp_path / "events.jsonl")

    result = assessor.assess(request)

    assert result.status in ("green", "amber", "red")
    assert result.current_value.value == pytest.approx(242_540.09)
    assert result.current_value.metric_id == TARGET_METRIC
    assert result.current_milestone.label == "Repayment Underway"
    assert all(
        item.destination_direction == "lower_is_better"
        for item in result.milestones)
    assert result.eta is not None
    assert result.trajectory_state == "Accelerated"
    assert result.trajectory_movement == "advancing"
    assert result.forecast
    assert result.delta_v.days > 0
    assert result.delta_v.direction == "accelerated"
    assert result.mission_margin.label == "MORTGAGE MARGIN"
    assert result.mission_margin.format_kind == "plain"
    assert sum(
        item.display_region == "essential"
        for item in result.telemetry
    ) == 3
    assert sum(
        item.display_region == "headline"
        for item in result.telemetry
    ) == 1
    assert sum(
        item.display_region == "outcome"
        for item in result.telemetry
    ) == 1
    assert result.telemetry
    assert result.evidence_references
    assert result.assumption_references
    overpayment_refs = {
        record.event_id
        for record in MortgageEvidenceProjection(log).for_obligation(
            mortgage.id, request.as_of)
        if record.field == "recorded_overpayment"
    }
    assert overpayment_refs <= set(result.evidence_references)
    optional_property_refs = {
        record.event_id
        for record in MortgageEvidenceProjection(log).for_obligation(
            mortgage.id, request.as_of)
        if record.field in {"purchase_price", "purchase_date"}
    }
    assert len(optional_property_refs) == 2
    assert optional_property_refs <= set(result.evidence_references)
    assert optional_property_refs.isdisjoint(
        result.recommendations[0].evidence_references)
    assert "runway-input" in result.input_references
    assert "runway-evidence" in result.evidence_references
    assert "runway-evidence" in \
        result.recommendations[0].evidence_references
    obligation = assessor.finance.obligations[mortgage.id]
    asset_id = next(
        link.target for link in obligation.ownership
        if link.relation == "secures")
    asset = assessor.finance.assets[asset_id]
    member = assessor.core.members_of(request.scope.id)[0]
    assert set(asset.history) <= set(result.input_references)
    assert set(member.history) <= set(result.input_references)
    assert "NOT A PROBABILITY" in result.confidence_basis
    original_destination = _add_calendar_months(
        NOW - 365 * DAY, 300)
    assert result.eta + result.delta_v.days * DAY \
        == pytest.approx(original_destination)
    assert result.delta_v.months > 0
    assert "original contractual" in result.delta_v.description
    assert any(
        "historical one-off overpayments; no recurrence is assumed" in note
        for note in result.limitations)


def test_property_equity_calculations_are_direct_explanatory_attribution(
        tmp_path):
    log, _, mortgage, _, assessor, request = _fixture(
        tmp_path / "events.jsonl", acquisition_costs=7_500.0)

    result = assessor.assess(request)
    telemetry = _telemetry_by_id(result)

    assert telemetry[
        "finance.property_current_equity"].result.value == pytest.approx(
            436_638.42 - 242_540.09)
    assert telemetry[
        "finance.mortgage_ltv"].result.value == pytest.approx(
            242_540.09 / 436_638.42)
    assert telemetry[
        "finance.mortgage_principal_repaid"].result.value == pytest.approx(
            310_000.0 - 242_540.09)
    assert telemetry[
        "finance.property_valuation_movement"].result.value == pytest.approx(
            436_638.42 - 450_000.0)
    assert telemetry[
        "finance.mortgage_initial_deposit"].result.value == 140_000.0
    assert telemetry[
        "finance.mortgage_balance"].qualifier == "OBSERVED · JANUARY 2027"
    assert telemetry[
        "finance.property_acquisition_costs"].result.value == 7_500.0
    principal_refs = set(telemetry[
        "finance.mortgage_principal_repaid"].result.evidence_references)
    evidence = MortgageEvidenceProjection(log)
    payment_and_interest_refs = {
        record.event_id
        for record in evidence.for_obligation(mortgage.id, request.as_of)
        if record.field in {"monthly_payment", "interest_rate"}
    }
    assert principal_refs.isdisjoint(payment_and_interest_refs)
    assert any(
        "explanatory attribution only" in note
        and "Interest is excluded" in note
        and "monthly payment is never used" in note
        for note in result.limitations)
    assert any(
        "Acquisition costs are disclosed separately" in note
        for note in result.limitations)


def test_missing_acquisition_evidence_does_not_change_mortgage_behaviour(
        tmp_path):
    _, _, _, _, complete, complete_request = _fixture(
        tmp_path / "complete.jsonl")
    _, _, _, _, missing, missing_request = _fixture(
        tmp_path / "missing.jsonl",
        omit={"purchase_price", "purchase_date", "initial_deposit"})

    complete_result = complete.assess(complete_request)
    missing_result = missing.assess(missing_request)
    telemetry = _telemetry_by_id(missing_result)

    for attribute in (
        "status", "mission_complete", "eta", "trajectory_state",
        "confidence", "current_milestone", "milestones", "mission_margin",
        "delta_v", "trajectory", "forecast",
    ):
        assert getattr(missing_result, attribute) == getattr(
            complete_result, attribute)
    assert tuple(
        (
            recommendation.action,
            recommendation.amount,
            recommendation.estimated_delta_v_days,
        )
        for recommendation in missing_result.recommendations
    ) == tuple(
        (
            recommendation.action,
            recommendation.amount,
            recommendation.estimated_delta_v_days,
        )
        for recommendation in complete_result.recommendations
    )
    assert telemetry[
        "finance.property_current_equity"].result.status == "available"
    assert telemetry[
        "finance.mortgage_principal_repaid"].result.status == "available"
    assert telemetry[
        "finance.mortgage_initial_deposit"
    ].result.status == "unavailable"
    assert telemetry[
        "finance.property_valuation_movement"
    ].result.status == "unavailable"
    assert any(
        "partially unavailable" in note for note in missing_result.limitations)


def test_conflicting_acquisition_evidence_remains_visible_without_correction(
        tmp_path):
    path = tmp_path / "events.jsonl"
    log, _, mortgage, _, _, request = _fixture(path)
    conflicting_price = _record(
        log, mortgage.id, "purchase_price", 455_000.0,
        effective_at=NOW - 5 * DAY, unit_or_currency="GBP")
    conflicting_deposit = _record(
        log, mortgage.id, "initial_deposit", 145_000.0,
        effective_at=NOW - 5 * DAY, unit_or_currency="GBP")
    assessor = MortgageFreedomAssessor(
        FinanceEntityProjection(log), EntityProjection(log),
        _metric_registry(18.0), MortgageEvidenceProjection(log))

    result = assessor.assess(request)
    telemetry = _telemetry_by_id(result)
    records = MortgageEvidenceProjection(log).for_obligation(
        mortgage.id, request.as_of)
    purchase_records = tuple(
        record for record in records if record.field == "purchase_price")
    deposit_records = tuple(
        record for record in records if record.field == "initial_deposit")

    assert result.status != "unavailable"
    assert len(purchase_records) == len(deposit_records) == 2
    assert telemetry[
        "finance.property_purchase_price"].result.value == 455_000.0
    assert telemetry[
        "finance.mortgage_initial_deposit"].result.value == 145_000.0
    assert {record.event_id for record in purchase_records} <= set(
        result.evidence_references)
    assert {record.event_id for record in deposit_records} <= set(
        result.evidence_references)
    assert conflicting_price.event_id in result.evidence_references
    assert conflicting_deposit.event_id in result.evidence_references
    assert all(not hasattr(record, "supersedes_event_id") for record in records)
    conflict_notes = tuple(
        note for note in result.limitations if note.startswith("Conflicting"))
    assert len(conflict_notes) == 2
    assert all("no evidence is automatically corrected" in note
               for note in conflict_notes)


def test_negative_equity_is_reported_without_changing_mission_completion(
        tmp_path):
    _, _, _, _, assessor, request = _fixture(
        tmp_path / "events.jsonl", valuation=200_000.0)

    result = assessor.assess(request)
    telemetry = _telemetry_by_id(result)

    assert result.status != "unavailable"
    assert result.mission_complete is False
    assert telemetry[
        "finance.property_current_equity"].result.value == pytest.approx(
            -42_540.09)
    assert telemetry["finance.mortgage_ltv"].result.value > 1.0


def test_valuation_basis_is_explicit_and_never_inferred_from_source_text(
        tmp_path):
    _, _, _, _, explicit, request = _fixture(
        tmp_path / "explicit.jsonl")
    _, _, _, _, absent, absent_request = _fixture(
        tmp_path / "absent.jsonl", omit={"valuation_basis"})

    explicit_valuation = _telemetry_by_id(explicit.assess(request))[
        "finance.property_valuation"]
    absent_valuation = _telemetry_by_id(absent.assess(absent_request))[
        "finance.property_valuation"]

    assert (
        explicit_valuation.qualifier
        == "Estimated · Agent appraisal · manual lender statement"
        " · January 2027"
    )
    assert (
        absent_valuation.qualifier
        == "Estimated · Valuation basis: Not recorded; not inferred"
        " · manual lender statement · January 2027"
    )
    assert "Owner Estimate" not in absent_valuation.qualifier
    assert "Index Estimate" not in absent_valuation.qualifier


def test_equity_evidence_does_not_change_net_worth_or_its_valuation_basis(
        tmp_path):
    log, household, mortgage, _, assessor, request = _fixture(
        tmp_path / "events.jsonl")
    obligation = assessor.finance.obligations[mortgage.id]
    asset_id = next(
        link.target for link in obligation.ownership
        if link.relation == "secures")
    fin.declare_valuation(log, asset_id, 480_000.0, "GBP", NOW - DAY)
    scope = Subject("party", household.id)
    before = FinanceMetricProvider(
        FinanceEntityProjection(log), EntityProjection(log)).calculate(
            MetricRequest("finance.net_worth", scope, NOW))

    _record(
        log, mortgage.id, "acquisition_costs", 8_000.0,
        effective_at=NOW, unit_or_currency="GBP")
    after = FinanceMetricProvider(
        FinanceEntityProjection(log), EntityProjection(log)).calculate(
            MetricRequest("finance.net_worth", scope, NOW))
    mortgage_result = MortgageFreedomAssessor(
        FinanceEntityProjection(log), EntityProjection(log),
        _metric_registry(18.0), MortgageEvidenceProjection(log)).assess(
            request)

    assert replace(after, generated_at=before.generated_at) == before
    assert _telemetry_by_id(mortgage_result)[
        "finance.property_valuation"].result.value == 436_638.42
    assert any(
        "Net Worth retains its existing latest-applicable Finance valuation policy"
        in note for note in mortgage_result.limitations)


def test_additive_equity_evidence_preserves_all_mission_policy_outputs(
        tmp_path):
    path = tmp_path / "events.jsonl"
    log, _, mortgage, _, assessor, request = _fixture(
        path, omit={"initial_deposit", "valuation_basis"})
    before = assessor.assess(request)
    _record(
        log, mortgage.id, "initial_deposit", 140_000.0,
        effective_at=NOW, unit_or_currency="GBP")
    _record(
        log, mortgage.id, "valuation_basis", "owner_estimate",
        effective_at=NOW)
    after = MortgageFreedomAssessor(
        FinanceEntityProjection(log), EntityProjection(log),
        _metric_registry(18.0), MortgageEvidenceProjection(log)).assess(
            request)

    for attribute in (
        "status", "current_value", "mission_complete", "eta",
        "trajectory_state", "trajectory_tone", "confidence",
        "current_milestone", "milestones",
        "mission_margin", "delta_v", "trajectory", "forecast",
        "recommendations",
    ):
        assert getattr(after, attribute) == getattr(before, attribute)


def test_zero_balance_is_complete_not_an_epsilon_approximation(tmp_path):
    _, _, _, _, assessor, request = _fixture(
        tmp_path / "events.jsonl", balance=0.0)

    result = assessor.assess(request)

    assert result.mission_complete is True
    assert result.trajectory_state == "Complete"
    assert result.current_milestone.id == "mortgage_free"
    assert result.eta == NOW
    assert result.delta_v.days is None
    assert result.delta_v.period_label == "SINCE FIRST PAYMENT"
    assert result.delta_v.reference_start_label == "ORIGINAL START"
    assert result.delta_v.reference_destination_label \
        == "ORIGINAL DESTINATION"


def test_original_contractual_term_drives_trajectory_and_time_gained(tmp_path):
    _, _, _, _, assessor, request = _fixture(
        tmp_path / "events.jsonl")

    result = assessor.assess(request)
    mortgage_start = NOW - 365 * DAY
    contractual_destination = _add_calendar_months(mortgage_start, 300)
    calculated_days = (contractual_destination - result.eta) / DAY

    mission = assessor.core.missions[request.mission_id]
    assert mission.target_date == contractual_destination
    assert result.eta < contractual_destination
    assert result.trajectory_state == "Accelerated"
    assert result.delta_v.days == pytest.approx(calculated_days)
    assert result.delta_v.months == round(calculated_days / (MONTH / DAY))

    mission.target_date += MONTH
    forged = assessor.assess(request)
    assert forged.status == result.status
    assert forged.trajectory_state == result.trajectory_state

    mission.target_date = contractual_destination + DAY / 2
    subtly_forged = assessor.assess(request)
    assert subtly_forged.status == result.status
    assert subtly_forged.trajectory_state == result.trajectory_state


def test_historical_overpayments_do_not_become_recurring_forecast_inputs(
        tmp_path):
    _, _, _, _, with_history, request = _fixture(
        tmp_path / "with-history.jsonl")
    _, _, _, _, without_history, request_without = _fixture(
        tmp_path / "without-history.jsonl", include_overpayments=False)

    achieved = with_history.assess(request)
    no_history = without_history.assess(request_without)

    assert achieved.eta == no_history.eta
    assert achieved.delta_v == no_history.delta_v
    assert achieved.trajectory_state == no_history.trajectory_state \
        == "Accelerated"


def test_out_of_horizon_projection_preserves_reference_schedule_metadata(
        tmp_path):
    _, _, _, _, assessor, request = _fixture(
        tmp_path / "events.jsonl")
    assumption_set = next(iter(assessor.finance.assumption_sets.values()))
    assumption_set.assumptions["forecast_horizon_months"] = 1.0

    result = assessor.assess(request)

    assert result.eta is None
    assert result.applicability.eta == "unavailable"
    assert result.delta_v.days is None
    assert result.delta_v.period_label == "SINCE FIRST PAYMENT"
    assert result.delta_v.reference_start_label == "ORIGINAL START"
    assert result.delta_v.reference_destination_label \
        == "ORIGINAL DESTINATION"


def test_out_of_horizon_eta_survives_registry_with_provenance(tmp_path):
    _, _, _, _, assessor, request = _fixture(
        tmp_path / "events.jsonl")
    assumption_set = next(iter(assessor.finance.assumption_sets.values()))
    assumption_set.assumptions["forecast_horizon_months"] = 1.0
    registry = MissionAssessmentRegistry()
    registry.register(assessor)

    result = registry.dispatch(request)

    assert result.status != "unavailable"
    assert result.eta is None
    assert result.applicability.eta == "unavailable"
    assert result.current_value is not None
    assert result.milestones
    assert result.telemetry
    assert result.input_references
    assert result.evidence_references
    assert "assessment provider failed safely" not in result.limitations


def test_schedule_trajectory_does_not_infer_from_margin_or_confidence():
    target = NOW + 100 * DAY
    assert MortgageFreedomAssessor._schedule_assessment(
        False, target - 2 * MONTH, target - 2 * MONTH,
        target + DAY, target) \
        == ("green", "Accelerated", "green")
    assert MortgageFreedomAssessor._schedule_assessment(
        False, target - DAY, target - DAY, target + DAY, target) \
        == ("amber", "Nominal", "amber")
    assert MortgageFreedomAssessor._schedule_assessment(
        False, target - DAY, target + 2 * DAY, target + 2 * DAY, target) \
        == ("amber", "Constrained", "amber")
    assert MortgageFreedomAssessor._schedule_assessment(
        False, target + 2 * DAY, target + 2 * DAY,
        target + 2 * DAY, target) \
        == ("red", "Divergent", "red")
    assert MortgageFreedomAssessor._schedule_assessment(
        False, None, None, None, target) \
        == ("red", "Critical", "red")
    assert MortgageFreedomAssessor._schedule_assessment(
        True, None, None, None, target) \
        == ("green", "Complete", "green")


def test_recommendation_expresses_acceleration_and_interest_avoided(tmp_path):
    _, _, _, _, assessor, request = _fixture(tmp_path / "events.jsonl")

    recommendation = assessor.assess(request).recommendations[0]

    assert recommendation.amount == 250.0
    assert recommendation.cadence == "month"
    assert recommendation.estimated_delta_v_days > 0
    assert recommendation.estimated_delta_v_months > 0
    assert "sooner" in recommendation.action
    assert "projected interest" in recommendation.action
    assert recommendation.assumption_references
    assert recommendation.evidence_references


def test_financial_resilience_precedence_suppresses_recommendation(tmp_path):
    _, _, _, _, assessor, request = _fixture(
        tmp_path / "events.jsonl", runway=6.0)

    result = assessor.assess(request)

    assert len(result.recommendations) == 1
    recommendation = result.recommendations[0]
    assert recommendation.status == "suppressed"
    assert recommendation.action_label == "Preserve emergency liquidity"
    assert "current runway is 6.0 months" in recommendation.action
    assert result.trajectory_state == "Accelerated"
    assert (
        "Overpayment is not recommended because current liquidity runway "
        "is 6.0 months, below Mortgage Freedom's declared 12-month "
        "recommendation floor. Preserve emergency liquidity before "
        "deploying additional capital."
    ) in result.limitations
    combined = " ".join(result.limitations)
    assert "liquidity_floor_months" not in combined
    assert "finance.liquidity_runway" not in combined


def test_absent_scenario_invents_no_recommendation(tmp_path):
    _, _, _, _, assessor, request = _fixture(
        tmp_path / "events.jsonl", include_scenario=False)

    result = assessor.assess(request)

    assert result.recommendations == ()


def test_at_most_one_improving_recommendation_is_returned(tmp_path):
    log, _, _, assumptions, _, request = _fixture(
        tmp_path / "events.jsonl")
    fin.declare_scenario(
        log, "Test £100", assumptions.id,
        {"monthly_mortgage_overpayment": 100.0},
        action_type="increase_mortgage_payment",
        action_label="Add mortgage overpayment",
        unit_or_currency="GBP", cadence="month")
    assessor = MortgageFreedomAssessor(
        FinanceEntityProjection(log), EntityProjection(log),
        _metric_registry(18.0), MortgageEvidenceProjection(log))

    recommendations = assessor.assess(request).recommendations

    assert len(recommendations) == 1
    assert recommendations[0].amount == 250.0


def _metric_registry(runway):
    registry = MetricRegistry()
    registry.register(RunwayProvider(runway))
    return registry


@pytest.mark.parametrize("missing", ["balance", "original_term_months"])
def test_absent_required_evidence_fails_closed(tmp_path, missing):
    _, _, _, _, assessor, request = _fixture(
        tmp_path / "events.jsonl", omit={missing})

    result = assessor.assess(request)

    assert result.status == "unavailable"
    assert result.confidence.state == "Insufficient"
    expected_label = {
        "balance": "mortgage balance",
        "original_term_months": "original mortgage term",
    }[missing]
    assert expected_label in result.limitations[0]
    if "_" in missing:
        assert missing not in result.limitations[0]


def test_future_only_evidence_is_absent_at_assessment_time(tmp_path):
    log, _, mortgage, _, _, request = _fixture(
        tmp_path / "events.jsonl", omit={"balance"})
    _record(
        log, mortgage.id, "balance", 242_540.09,
        effective_at=NOW + DAY, unit_or_currency="GBP")
    assessor = MortgageFreedomAssessor(
        FinanceEntityProjection(log), EntityProjection(log),
        _metric_registry(18.0), MortgageEvidenceProjection(log))

    result = assessor.assess(request)

    assert result.status == "unavailable"
    assert "mortgage balance" in result.limitations[0]


def test_missing_assumption_is_not_replaced_by_hidden_policy(tmp_path):
    _, _, _, _, assessor, request = _fixture(
        tmp_path / "events.jsonl")
    assumption_set = next(iter(assessor.finance.assumption_sets.values()))
    del assumption_set.assumptions["high_post_fix_rate"]

    result = assessor.assess(request)

    assert result.status == "unavailable"
    assert result.limitations == (
        "Assumption Set missing: high_post_fix_rate",)


def test_fractional_integer_assumption_is_rejected_not_truncated(tmp_path):
    _, _, _, _, assessor, request = _fixture(
        tmp_path / "events.jsonl")
    assumption_set = next(iter(assessor.finance.assumption_sets.values()))
    assumption_set.assumptions["forecast_horizon_months"] = 480.9

    result = assessor.assess(request)

    assert result.status == "unavailable"
    assert result.limitations == (
        "Assumption Set forecast_horizon_months must be an integer",)


def test_non_finite_resilience_floor_cannot_bypass_precedence(tmp_path):
    _, _, _, _, assessor, request = _fixture(
        tmp_path / "events.jsonl", runway=6.0)
    assumption_set = next(iter(assessor.finance.assumption_sets.values()))
    assumption_set.assumptions["liquidity_floor_months"] = float("nan")

    result = assessor.assess(request)

    assert result.status == "unavailable"
    assert result.recommendations == ()
    assert result.limitations == (
        "Assumption Set liquidity_floor_months must be a finite number",)


def test_non_finite_runway_provider_cannot_bypass_precedence(tmp_path):
    _, _, _, _, assessor, request = _fixture(
        tmp_path / "events.jsonl", runway=float("nan"))

    result = assessor.assess(request)

    assert result.status != "unavailable"
    assert result.recommendations[0].status == "unavailable"
    assert result.mission_margin.state == "Negative Margin"
    assert "runway unavailable" in result.mission_margin.description
    assert any(
        "Liquidity evidence is absent" in note
        for note in result.limitations)


def test_cross_scope_runway_provider_cannot_influence_mission(tmp_path):
    _, _, _, _, assessor, request = _fixture(
        tmp_path / "events.jsonl")

    class CrossScopeRunwayProvider:
        def owned_metric_ids(self):
            return frozenset({"finance.liquidity_runway"})

        def calculate(self, metric_request):
            return MetricResult(
                metric_request.metric_id, 100.0, "months",
                Subject("party", "other-household"), metric_request.as_of,
                "available", "hostile-v1",
                generated_at=metric_request.as_of)

    assessor.metrics = MetricRegistry()
    assessor.metrics.register(CrossScopeRunwayProvider())

    result = assessor.assess(request)

    assert result.status != "unavailable"
    assert result.recommendations[0].status == "unavailable"
    assert result.mission_margin.state == "Negative Margin"
    assert any(
        "Liquidity evidence is absent" in note
        for note in result.limitations)


def test_stale_evidence_is_visible_and_confidence_is_provisional(tmp_path):
    _, _, _, _, assessor, request = _fixture(
        tmp_path / "events.jsonl",
        valuation_effective_at=NOW - 500 * DAY,
        balance_effective_at=NOW - 200 * DAY)

    result = assessor.assess(request)

    assert result.status != "unavailable"
    assert result.current_value.status == "stale"
    assert result.confidence.state == "Provisional"
    assert "stale" in result.confidence.basis
    assert any("dated valuation reference is stale" in note
               for note in result.limitations)


def test_low_confidence_overpayment_affects_confidence_not_margin(tmp_path):
    _, _, _, _, assessor, request = _fixture(
        tmp_path / "events.jsonl", balance=200_000.0,
        overpayment_confidence=.01)

    result = assessor.assess(request)

    assert result.status != "unavailable"
    assert result.mission_margin.state == "High Margin"
    assert result.confidence.state == "Insufficient"
    assert any(
        "does not determine Mission Margin" in note
        for note in result.limitations)


def test_malformed_hostile_evidence_degrades_only_the_provider(tmp_path):
    log, _, mortgage, _, _, request = _fixture(
        tmp_path / "events.jsonl")
    log.append("finance.mortgage_evidence.recorded", {
        "obligation_id": mortgage.id,
        "field": "balance",
        "value": "<script>alert(1)</script>",
        "effective_at": NOW,
        "confidence": {"forged": True},
        "source": "hostile",
        "lineage": "forged",
    })
    assessor = MortgageFreedomAssessor(
        FinanceEntityProjection(log), EntityProjection(log),
        _metric_registry(18.0), MortgageEvidenceProjection(log))

    result = assessor.assess(request)

    assert result.status == "unavailable"
    assert result.limitations == (
        "mortgage evidence envelope is malformed",)
    assert "script" not in result.limitations[0]


def test_malformed_overpayment_cannot_fabricate_margin(tmp_path):
    log, _, mortgage, _, _, request = _fixture(
        tmp_path / "events.jsonl")
    log.append("finance.mortgage_evidence.recorded", {
        "obligation_id": mortgage.id,
        "field": "recorded_overpayment",
        "value": "<not-a-number>",
        "effective_at": NOW,
        "confidence": .99,
        "source": "hostile",
        "lineage": "forged",
        "unit_or_currency": "GBP",
    })
    assessor = MortgageFreedomAssessor(
        FinanceEntityProjection(log), EntityProjection(log),
        _metric_registry(18.0), MortgageEvidenceProjection(log))

    result = assessor.assess(request)

    assert result.status == "unavailable"
    assert result.recommendations == ()
    assert result.mission_margin is None
    assert result.limitations == (
        "mortgage evidence envelope is malformed",)


def test_cross_currency_evidence_is_not_silently_treated_as_gbp(tmp_path):
    log, _, mortgage, _, _, request = _fixture(
        tmp_path / "events.jsonl")
    log.append("finance.mortgage_evidence.recorded", {
        "obligation_id": mortgage.id,
        "field": "balance",
        "value": 242_540.09,
        "effective_at": NOW,
        "confidence": .99,
        "source": "hostile",
        "lineage": "forged currency",
        "unit_or_currency": "USD",
    })
    assessor = MortgageFreedomAssessor(
        FinanceEntityProjection(log), EntityProjection(log),
        _metric_registry(18.0), MortgageEvidenceProjection(log))

    result = assessor.assess(request)

    assert result.status == "unavailable"
    assert result.limitations == (
        "mortgage evidence envelope is malformed",)


def test_future_malformed_evidence_does_not_poison_past_assessment(tmp_path):
    log, _, mortgage, _, _, request = _fixture(
        tmp_path / "events.jsonl")
    log.append("finance.mortgage_evidence.recorded", {
        "obligation_id": mortgage.id,
        "field": "balance",
        "value": "<future-hostile>",
        "effective_at": NOW + DAY,
        "confidence": .99,
        "source": "future",
        "lineage": "future malformed input",
        "unit_or_currency": "GBP",
    })
    assessor = MortgageFreedomAssessor(
        FinanceEntityProjection(log), EntityProjection(log),
        _metric_registry(18.0), MortgageEvidenceProjection(log))

    result = assessor.assess(request)

    assert result.status != "unavailable"
    assert result.current_value.value == pytest.approx(242_540.09)


def test_unrelated_malformed_obligation_does_not_poison_household(tmp_path):
    log, _, _, _, _, request = _fixture(
        tmp_path / "events.jsonl")
    log.append("finance.mortgage_evidence.recorded", {
        "obligation_id": "other-obligation",
        "field": "balance",
        "value": "<hostile>",
        "effective_at": NOW,
        "confidence": .99,
        "source": "other",
        "lineage": "unrelated malformed input",
        "unit_or_currency": "GBP",
    })
    assessor = MortgageFreedomAssessor(
        FinanceEntityProjection(log), EntityProjection(log),
        _metric_registry(18.0), MortgageEvidenceProjection(log))

    assert assessor.assess(request).status != "unavailable"


def test_contract_date_cannot_create_a_future_observation(tmp_path):
    log, _, mortgage, _, _, request = _fixture(
        tmp_path / "events.jsonl")
    _record(
        log, mortgage.id, "mortgage_start", NOW + DAY,
        effective_at=NOW)
    assessor = MortgageFreedomAssessor(
        FinanceEntityProjection(log), EntityProjection(log),
        _metric_registry(18.0), MortgageEvidenceProjection(log))

    result = assessor.assess(request)

    assert result.status == "unavailable"
    assert result.limitations == (
        "Mortgage start cannot be after assessment time",)


def test_unrepresentable_original_term_fails_closed(tmp_path):
    log, _, mortgage, _, _, request = _fixture(
        tmp_path / "events.jsonl")
    _record(
        log, mortgage.id, "original_term_months", 1e300,
        effective_at=NOW)
    assessor = MortgageFreedomAssessor(
        FinanceEntityProjection(log), EntityProjection(log),
        _metric_registry(18.0), MortgageEvidenceProjection(log))

    result = assessor.assess(request)

    assert result.status == "unavailable"
    assert result.recommendations == ()
    assert "represented safely" in result.limitations[0]


@pytest.mark.parametrize(("field", "value"), [
    ("target_date", float("nan")),
    ("target_date", float("inf")),
    ("target_date", False),
    ("target_value", False),
])
def test_legacy_mission_destination_metadata_is_ignored(
        tmp_path, field, value):
    _, _, _, _, assessor, request = _fixture(
        tmp_path / "events.jsonl")
    mission = assessor.core.missions[request.mission_id]
    setattr(mission, field, value)

    result = assessor.assess(request)

    assert result.status != "unavailable"


def test_cross_household_borrower_scope_fails_closed(tmp_path):
    log, _, mortgage, _, _, request = _fixture(
        tmp_path / "events.jsonl")
    outsider = declare_party(log, "person")
    fin.link_ownership(
        log, "obligation", mortgage.id, "owes", outsider.id)
    assessor = MortgageFreedomAssessor(
        FinanceEntityProjection(log), EntityProjection(log),
        _metric_registry(18.0), MortgageEvidenceProjection(log))

    result = assessor.assess(request)

    assert result.status == "unavailable"
    assert "household mortgage" in result.limitations[0]


def test_guarantee_only_relation_cannot_establish_mortgage_scope(tmp_path):
    _, _, mortgage, _, assessor, request = _fixture(
        tmp_path / "events.jsonl")
    obligation = assessor.finance.obligations[mortgage.id]
    owes = next(
        link for link in obligation.ownership if link.relation == "owes")
    owes.relation = "guarantees"

    result = assessor.assess(request)

    assert result.status == "unavailable"
    assert "household mortgage" in result.limitations[0]


def test_scope_provenance_uses_selected_mortgage_not_later_invalid_one(
        tmp_path):
    log, household, _, _, _, request = _fixture(
        tmp_path / "events.jsonl")
    outsider = declare_party(log, "person")
    other_home = fin.declare_asset(log, "property", "GBP")
    fin.link_ownership(
        log, "asset", other_home.id, "owner", outsider.id)
    other_mortgage = fin.declare_obligation(
        log, "mortgage", "GBP", amount=10_000.0)
    fin.link_ownership(
        log, "obligation", other_mortgage.id, "owes", outsider.id)
    fin.link_ownership(
        log, "obligation", other_mortgage.id, "secures", other_home.id)
    assessor = MortgageFreedomAssessor(
        FinanceEntityProjection(log), EntityProjection(log),
        _metric_registry(18.0), MortgageEvidenceProjection(log))
    member = assessor.core.members_of(household.id)[0]

    result = assessor.assess(request)

    assert result.status != "unavailable"
    assert set(member.history) <= set(result.input_references)
    assert set(assessor.core.parties[outsider.id].history).isdisjoint(
        result.input_references)


def _canonical_property_valuation(log, property_id, value, effective_at, *,
                                  basis="lender_valuation", source="NatWest", **changes):
    payload = {
        "entity_id": f"canonical-{value}-{effective_at}", "subject_id": property_id,
        "amount": value, "currency": "GBP", "as_of": effective_at,
        "valuation_basis": basis, "source": source,
        "provenance": {"evidence_id": "evidence-1", "proposal_id": "proposal-1",
                       "confirmed_by": "operator"},
    }
    payload.update(changes)
    return log.append("finance.valuation.declared", payload)


def test_canonical_secured_property_valuation_is_consumed_without_legacy_value(tmp_path):
    log, _, mortgage, _, _, request = _fixture(
        tmp_path / "events.jsonl", omit=("property_valuation",))
    home_id = next(link.target for link in FinanceEntityProjection(log).obligations[mortgage.id].ownership
                   if link.relation == "secures")
    canonical = _canonical_property_valuation(log, home_id, 530_000.0, NOW - DAY)
    assessor = MortgageFreedomAssessor(
        FinanceEntityProjection(log), EntityProjection(log), _metric_registry(18.0),
        MortgageEvidenceProjection(log))

    result = assessor.assess(request)

    assert _telemetry_by_id(result)["finance.property_valuation"].result.value == 530_000.0
    assert _telemetry_by_id(result)["finance.mortgage_ltv"].result.evidence_references == (canonical["id"],)
    assert "Lender valuation" in _telemetry_by_id(result)["finance.property_valuation"].qualifier


def test_canonical_and_legacy_valuations_use_effective_date_then_log_order(tmp_path):
    log, _, mortgage, _, _, request = _fixture(tmp_path / "events.jsonl")
    home_id = next(link.target for link in FinanceEntityProjection(log).obligations[mortgage.id].ownership
                   if link.relation == "secures")
    later = _canonical_property_valuation(log, home_id, 500_000.0, NOW - DAY)
    assessor = MortgageFreedomAssessor(FinanceEntityProjection(log), EntityProjection(log),
                                       _metric_registry(18.0), MortgageEvidenceProjection(log))
    assert _telemetry_by_id(assessor.assess(request))["finance.property_valuation"].result.value == 500_000.0

    same_date = _canonical_property_valuation(log, home_id, 510_000.0, NOW - DAY)
    assessor = MortgageFreedomAssessor(FinanceEntityProjection(log), EntityProjection(log),
                                       _metric_registry(18.0), MortgageEvidenceProjection(log))
    result = assessor.assess(request)
    assert _telemetry_by_id(result)["finance.property_valuation"].result.value == 510_000.0
    assert same_date["id"] in result.evidence_references
    assert later["id"] not in _telemetry_by_id(result)["finance.property_valuation"].result.evidence_references


@pytest.mark.parametrize("change", [
    {"currency": "USD"}, {"amount": 0.0}, {"valuation_basis": "invented"},
    {"source": ""}, {"provenance": {}},
])
def test_ineligible_canonical_valuation_does_not_replace_legacy_value(tmp_path, change):
    log, _, mortgage, _, _, request = _fixture(tmp_path / "events.jsonl")
    home_id = next(link.target for link in FinanceEntityProjection(log).obligations[mortgage.id].ownership
                   if link.relation == "secures")
    _canonical_property_valuation(log, home_id, 530_000.0, NOW - DAY, **change)
    assessor = MortgageFreedomAssessor(FinanceEntityProjection(log), EntityProjection(log),
                                       _metric_registry(18.0), MortgageEvidenceProjection(log))
    assert _telemetry_by_id(assessor.assess(request))["finance.property_valuation"].result.value == 436_638.42


def test_canonical_valuation_for_an_unsecured_property_is_not_eligible(tmp_path):
    log, _, _, _, _, request = _fixture(tmp_path / "events.jsonl")
    other = fin.declare_asset(log, "property", "GBP")
    _canonical_property_valuation(log, other.id, 530_000.0, NOW - DAY)
    assessor = MortgageFreedomAssessor(FinanceEntityProjection(log), EntityProjection(log),
                                       _metric_registry(18.0), MortgageEvidenceProjection(log))
    assert _telemetry_by_id(assessor.assess(request))["finance.property_valuation"].result.value == 436_638.42


def test_member_scope_cannot_reuse_household_assessment(tmp_path):
    _, household, _, _, assessor, request = _fixture(
        tmp_path / "events.jsonl")
    member = next(
        party for party in assessor.core.members_of(household.id))

    result = assessor.assess(replace(
        request, scope=Subject("party", member.id)))

    assert result.status == "unavailable"
    assert "household scope" in result.limitations[0]


def test_assessment_is_read_only_and_render_inputs_are_deterministic(tmp_path):
    path = tmp_path / "events.jsonl"
    log, _, _, _, assessor, request = _fixture(path)
    before = path.read_bytes()

    first = assessor.assess(request)
    second = assessor.assess(request)

    assert path.read_bytes() == before
    assert first == second
    assert _month_year(1_735_689_600.0) == "January 2025"
    assert log.verify()


def test_observations_never_include_future_projection_points(tmp_path):
    _, _, _, _, assessor, request = _fixture(tmp_path / "events.jsonl")

    result = assessor.assess(request)

    assert all(point.at <= request.as_of for point in result.trajectory)
    assert all(point.at >= request.as_of for point in result.forecast)
    assert {point.at for point in result.trajectory}.isdisjoint(
        point.at for point in result.forecast[1:])


def test_registry_isolates_malformed_mortgage_provider(tmp_path):
    _, _, _, _, assessor, request = _fixture(tmp_path / "events.jsonl")
    registry = MissionAssessmentRegistry()
    registry.register(assessor)

    class OtherProvider:
        def owned_policy_ids(self):
            return frozenset({"other.v1"})

        def assess(self, other_request):
            from foundry.core.mission_assessment import MissionAssessment
            return MissionAssessment.unavailable(other_request, "other")

    registry.register(OtherProvider())
    assessor.evidence.invalid_event_ids.append("hostile")

    mortgage = registry.dispatch(request)
    other = registry.dispatch(replace(request, policy_id="other.v1"))

    assert mortgage.status == "unavailable"
    assert other.limitations == ("other",)


def test_projection_failure_after_current_state_yields_partial_mortgage(
        tmp_path, monkeypatch):
    _, _, _, _, assessor, request = _fixture(tmp_path / "events.jsonl")

    def fail_projection(*args, **kwargs):
        raise ValueError("projection failed after current state")

    monkeypatch.setattr(assessor.projection, "project", fail_projection)
    result = assessor.assess(request)
    telemetry = _telemetry_by_id(result)

    assert result.completeness == "partial"
    assert result.status == "none"
    assert result.current_value.value is not None
    assert telemetry["finance.property_current_equity"].result.value is not None
    assert result.forecast == ()
    assert result.eta is None
    assert result.mission_margin is None
    assert result.delta_v is None


def test_missing_core_mortgage_evidence_remains_unavailable_not_partial(
        tmp_path):
    _, _, _, _, assessor, request = _fixture(
        tmp_path / "events.jsonl", omit={"balance"})

    result = assessor.assess(request)

    assert result.completeness == "unavailable"
    assert result.status == "unavailable"

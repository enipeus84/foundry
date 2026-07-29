"""RFC-007 Mortgage Freedom assessment and deterministic policy."""

from dataclasses import replace

import pytest

from foundry.core.entities import (
    EntityProjection,
    declare_mission,
    declare_party,
    join_household,
)
from foundry.core.metrics import MetricRegistry, MetricResult
from foundry.core.mission_assessment import (
    MissionAssessmentRegistry,
    MissionAssessmentRequest,
)
from foundry.core.scope import Subject
from foundry.eventlog import EventLog
from foundry.finance import entities as fin
from foundry.finance.entities import FinanceEntityProjection
from foundry.finance.mortgage_assessment import (
    DAY,
    MONTH,
    POLICY_ID,
    TARGET_METRIC,
    MortgageFreedomAssessor,
    MortgageProjectionEngine,
    MortgageProjectionInputs,
    _month_year,
)
from foundry.finance.mortgage_evidence import (
    MortgageEvidenceProjection,
    record_mortgage_evidence,
)


NOW = 1_785_170_000.0


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
             balance=242_540.09, omit=()):
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
    mission = declare_mission(
        log, "Mortgage free by contractual term",
        target_metric=TARGET_METRIC, target_value=0.0,
        target_date=NOW + 201 * MONTH,
        assessment_policy_id=POLICY_ID,
        assumption_set_id=assumptions.id)

    fields = {
        "property_role": "primary_residence",
        "purchase_price": 450_000.0,
        "purchase_date": NOW - 500 * DAY,
        "property_valuation": 436_638.42,
        "lender": "NatWest",
        "original_advance": 310_000.0,
        "mortgage_start": NOW - 365 * DAY,
        "balance": balance,
        "repayment_type": "capital_repayment",
        "interest_type": "fixed",
        "interest_rate": .0433,
        "monthly_payment": 1_701.47,
        "remaining_term_months": 201.0,
        "fixed_rate_expiry": NOW + 367 * DAY,
    }
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
                    "purchase_price", "property_valuation",
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
    assert result.forecast
    assert result.delta_v.days > 0
    assert result.delta_v.direction == "accelerated"
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


def test_zero_balance_is_complete_not_an_epsilon_approximation(tmp_path):
    _, _, _, _, assessor, request = _fixture(
        tmp_path / "events.jsonl", balance=0.0)

    result = assessor.assess(request)

    assert result.mission_complete is True
    assert result.trajectory_state == "Complete"
    assert result.current_milestone.id == "mortgage_free"
    assert result.eta == NOW
    assert result.delta_v.days is None


def test_schedule_trajectory_does_not_infer_from_margin_or_confidence():
    target = NOW + 100 * DAY
    assert MortgageFreedomAssessor._schedule_assessment(
        False, target - DAY, target - DAY, target - DAY, target) \
        == ("green", "Accelerated", "green")
    assert MortgageFreedomAssessor._schedule_assessment(
        False, target - DAY, target - DAY, target + DAY, target) \
        == ("amber", "Nominal", "amber")
    assert MortgageFreedomAssessor._schedule_assessment(
        False, target - DAY, target + DAY, target + DAY, target) \
        == ("amber", "Constrained", "amber")
    assert MortgageFreedomAssessor._schedule_assessment(
        False, target + DAY, target + DAY, target + DAY, target) \
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

    assert result.recommendations == ()
    assert any(
        "Financial Resilience takes precedence" in note
        for note in result.limitations)


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


def test_absent_required_evidence_fails_closed(tmp_path):
    _, _, _, _, assessor, request = _fixture(
        tmp_path / "events.jsonl", omit={"balance"})

    result = assessor.assess(request)

    assert result.status == "unavailable"
    assert result.confidence.state == "Insufficient"
    assert "balance" in result.limitations[0]


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
    assert "balance" in result.limitations[0]


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
    assert result.recommendations == ()
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
    assert result.recommendations == ()
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


@pytest.mark.parametrize(("field", "value"), [
    ("target_date", float("nan")),
    ("target_date", float("inf")),
    ("target_date", False),
    ("target_value", False),
])
def test_malformed_mission_target_policy_fails_closed(
        tmp_path, field, value):
    _, _, _, _, assessor, request = _fixture(
        tmp_path / "events.jsonl")
    mission = assessor.core.missions[request.mission_id]
    setattr(mission, field, value)

    result = assessor.assess(request)

    assert result.status == "unavailable"
    assert result.recommendations == ()


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

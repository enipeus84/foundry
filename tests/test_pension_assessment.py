"""RFC-009 Pension Independence mission behavior."""

import ast
import inspect

import pytest

from foundry.core.entities import (
    EntityProjection,
    declare_mission,
)
from foundry.core.metrics import MetricRegistry, MetricResult
from foundry.core.mission_assessment import (
    ForecastPoint,
    MissionAssessmentRequest,
)
from foundry.core.scope import Subject
from foundry.demo_data import build
from foundry.eventlog import EventLog
from foundry.finance import entities as fin
from foundry.finance.aggregation import FinanceAggregationService
from foundry.finance.entities import FinanceEntityProjection
from foundry.finance.metrics import FinanceMetricProvider
from foundry.finance.pension_assessment import (
    POLICY_ID,
    PensionIndependenceInputs,
    PensionIndependenceAssessor,
)
from foundry.finance.pension_evidence import (
    EVENT_KIND,
    PensionEvidenceProjection,
    record_pension_evidence,
)
from foundry.finance.pension_metrics import FinancePensionMetricProvider


def _seed(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    household = build(log)
    return log, household


def _assessor(log):
    core = EntityProjection(log)
    finance = FinanceEntityProjection(log)
    evidence = PensionEvidenceProjection(log)
    metrics = MetricRegistry()
    metrics.register(FinanceMetricProvider(finance, core))
    metrics.register(FinancePensionMetricProvider(finance, core, evidence))
    return PensionIndependenceAssessor(
        metrics, finance, core, evidence), core, finance


def _assessment(log, household, *, mission_id=None, as_of=None):
    assessor, core, _ = _assessor(log)
    if mission_id is None:
        mission = next(
            mission for mission in core.missions.values()
            if mission.assessment_policy_id == POLICY_ID)
    else:
        mission = core.missions[mission_id]
    if as_of is None:
        as_of = max(event["ts"] for event in log.events())
    return assessor.assess(MissionAssessmentRequest(
        mission.id,
        POLICY_ID,
        __import__("foundry.core.scope", fromlist=["Subject"]).Subject(
            "party", household.household_id),
        as_of,
    ))


def _new_assumptions(log, original, **changes):
    values = {**original.assumptions, **changes}
    return fin.declare_assumption_set(
        log, "Pension test variation", "v-test", values)


def test_governor_worked_shape_separates_completion_from_projection(tmp_path):
    log, household = _seed(tmp_path)

    assessment = _assessment(log, household)
    telemetry = {item.label: item for item in assessment.telemetry}

    assert assessment.current_value.value == 62_000.0
    assert assessment.current_value.assumption_references == ()
    assert assessment.mission_complete is False
    assert assessment.trajectory_state == "Nominal"
    assert assessment.forecast[-1].base == pytest.approx(785_000.0, abs=1.0)
    assert telemetry["REQUIRED RETIREMENT WEALTH"].result.value == 735_000.0
    assert telemetry[
        "ESTIMATED RETIREMENT INCOME"
    ].result.value == pytest.approx(42_000.0, abs=1.0)
    assert assessment.mission_margin.state == "Adequate Margin"
    assert assessment.current_milestone.label == "Dependent"
    assert assessment.applicability.trajectory == "unavailable"
    assert assessment.trajectory == ()


def test_return_changes_never_change_observed_value_or_completion(tmp_path):
    log, household = _seed(tmp_path)
    original = _assessment(log, household)
    _, _, finance = _assessor(log)
    assumption = finance.assumption_sets[
        next(
            mission.assumption_set_id
            for mission in EntityProjection(log).missions.values()
            if mission.assessment_policy_id == POLICY_ID
        )
    ]
    changed = _new_assumptions(
        log,
        assumption,
        low_real_return=.02,
        base_real_return=.06,
        high_real_return=.08,
    )
    mission = declare_mission(
        log,
        "Pension return sensitivity test",
        target_metric="finance.pension_wealth",
        assessment_policy_id=POLICY_ID,
        assumption_set_id=changed.id,
    )

    reassessed = _assessment(
        log, household, mission_id=mission.id)

    assert reassessed.current_value.value == original.current_value.value
    assert reassessed.mission_complete == original.mission_complete is False
    assert reassessed.forecast[-1].base != original.forecast[-1].base
    assert reassessed.current_value.assumption_references == ()


def test_completion_is_reversible_and_never_appends_an_event(tmp_path):
    log, household = _seed(tmp_path)
    before_count = len(list(log.events()))
    before_hash_ok = log.verify()
    as_of = max(event["ts"] for event in log.events())

    fin.declare_valuation(
        log, household.alex_pension_id, 500_000.0, "GBP", as_of + 1)
    fin.declare_valuation(
        log, household.sam_pension_id, 300_000.0, "GBP", as_of + 1)
    complete = _assessment(log, household, as_of=as_of + 1)

    fin.declare_valuation(
        log, household.alex_pension_id, 30_000.0, "GBP", as_of + 2)
    fin.declare_valuation(
        log, household.sam_pension_id, 20_000.0, "GBP", as_of + 2)
    incomplete = _assessment(log, household, as_of=as_of + 2)

    assert complete.mission_complete is True
    assert complete.current_milestone.label == "Pension Independent"
    assert incomplete.mission_complete is False
    assert incomplete.current_milestone.label == "Dependent"
    mission = next(
        mission for mission in EntityProjection(log).missions.values()
        if mission.assessment_policy_id == POLICY_ID)
    assert mission.status == "active"
    # Only the four explicit valuation observations were appended.
    assert len(list(log.events())) == before_count + 4
    assert before_hash_ok and log.verify()


def test_w_star_zero_is_complete_and_derivation_remains_visible(tmp_path):
    log, household = _seed(tmp_path)
    _, core, finance = _assessor(log)
    original_mission = next(
        mission for mission in core.missions.values()
        if mission.assessment_policy_id == POLICY_ID)
    original = finance.assumption_sets[original_mission.assumption_set_id]
    assumptions = _new_assumptions(
        log,
        original,
        required_retirement_income_annual=10_000.0,
    )
    mission = declare_mission(
        log,
        "Pension secured-income zero case",
        target_metric="finance.pension_wealth",
        assessment_policy_id=POLICY_ID,
        assumption_set_id=assumptions.id,
    )

    assessment = _assessment(log, household, mission_id=mission.id)
    required = next(
        item for item in assessment.telemetry
        if item.label == "REQUIRED RETIREMENT WEALTH")

    assert required.result.value == 0.0
    assert required.result.assumption_references
    assert assessment.mission_complete is True
    assert assessment.current_milestone.label == "Pension Independent"
    assert len(assessment.milestones) == 1
    assert assessment.milestones[0].lower_bound == 0.0
    assert assessment.milestones[0].upper_bound is None
    assert assessment.milestones[0].completes_mission is True


def test_pension_assessor_uses_supported_finance_aggregation_surface(tmp_path):
    log, _ = _seed(tmp_path)
    assessor, core, finance = _assessor(log)

    assert isinstance(assessor.basis, FinanceAggregationService)
    provider = FinanceMetricProvider(finance, core)
    assert isinstance(provider.aggregation, FinanceAggregationService)

    for provider_type in (
        PensionIndependenceAssessor,
        FinancePensionMetricProvider,
    ):
        source = inspect.getsource(provider_type)
        tree = ast.parse(source)
        private_aggregation_calls = {
            node.attr for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
            and node.attr in {
                "_scope_persons",
                "_attribute_to",
                "_owned_entities",
                "_shares",
                "_convert",
            }
        }
        assert not private_aggregation_calls


def test_milestone_contract_is_exactly_the_approved_w_star_hierarchy(tmp_path):
    log, household = _seed(tmp_path)
    assessment = _assessment(log, household)

    assert [item.label for item in assessment.milestones] == [
        "Dependent",
        "Foundation",
        "Building",
        "Approaching",
        "Pension Independent",
    ]
    assert [item.lower_bound for item in assessment.milestones] == [
        0.0, 183_750.0, 367_500.0, 551_250.0, 735_000.0,
    ]
    assert [item.upper_bound for item in assessment.milestones] == [
        183_750.0, 367_500.0, 551_250.0, 735_000.0, None,
    ]
    assert all(
        item.unit_or_currency == "GBP"
        and item.destination_direction == "higher_is_better"
        for item in assessment.milestones
    )
    assert [item.completes_mission for item in assessment.milestones] == [
        False, False, False, False, True,
    ]
    assert sum(item.is_current for item in assessment.milestones) == 1


def test_no_expected_crossing_keeps_forecast_but_marks_eta_unavailable(
        tmp_path):
    log, household = _seed(tmp_path)
    _, core, finance = _assessor(log)
    original_mission = next(
        mission for mission in core.missions.values()
        if mission.assessment_policy_id == POLICY_ID)
    assumptions = _new_assumptions(
        log,
        finance.assumption_sets[original_mission.assumption_set_id],
        required_retirement_income_annual=100_000.0,
    )
    mission = declare_mission(
        log,
        "Pension no-crossing test",
        target_metric="finance.pension_wealth",
        assessment_policy_id=POLICY_ID,
        assumption_set_id=assumptions.id,
    )

    assessment = _assessment(log, household, mission_id=mission.id)

    assert assessment.eta is None
    assert assessment.applicability.eta == "unavailable"
    assert assessment.applicability.delta_v == "unavailable"
    assert assessment.applicability.forecast == "applicable"
    assert assessment.forecast
    assert assessment.trajectory_state == "Critical"


def test_delta_v_uses_deterministic_lookback_and_paired_schedule_refs(
        tmp_path):
    log, household = _seed(tmp_path)
    _, core, finance = _assessor(log)
    original_mission = next(
        mission for mission in core.missions.values()
        if mission.assessment_policy_id == POLICY_ID)
    assumptions = _new_assumptions(
        log,
        finance.assumption_sets[original_mission.assumption_set_id],
        required_retirement_income_annual=25_000.0,
    )
    mission = declare_mission(
        log,
        "Pension lookback test",
        target_metric="finance.pension_wealth",
        assessment_policy_id=POLICY_ID,
        assumption_set_id=assumptions.id,
    )

    assessment = _assessment(log, household, mission_id=mission.id)

    assert assessment.applicability.delta_v == "applicable"
    assert assessment.delta_v is not None
    assert assessment.delta_v.lookback_days == 90
    assert assessment.delta_v.resolution == "month"
    assert assessment.delta_v.reference_start_at is not None
    assert assessment.delta_v.reference_start_label == "PLAN DECLARED"
    assert assessment.delta_v.reference_destination_at is not None
    assert (
        assessment.delta_v.reference_destination_label
        == "STATE PENSION AGE"
    )


def test_projection_applies_fee_once_then_end_of_month_contributions(
        tmp_path):
    log, _ = _seed(tmp_path)
    assessor, core, finance = _assessor(log)
    mission = next(
        mission for mission in core.missions.values()
        if mission.assessment_policy_id == POLICY_ID)
    inputs = PensionIndependenceInputs.from_assumption_set(
        finance.assumption_sets[mission.assumption_set_id])
    start = 1_700_000_000.0
    end = assessor._add_months(start, 1)

    forecast = assessor._project(
        ((1_000.0, 1_200.0, .01), (2_000.0, 0.0, .02)),
        start,
        end,
        inputs,
    )

    expected = (
        1_000.0 * (1.0 + .03 - .01) ** (1 / 12) + 100.0
        + 2_000.0 * (1.0 + .03 - .02) ** (1 / 12)
    )
    assert len(forecast) == 2
    assert forecast[-1].base == pytest.approx(expected)


def test_trajectory_state_boundaries_are_deterministic(tmp_path):
    log, _ = _seed(tmp_path)
    assessor, _, finance = _assessor(log)
    assumption_set = next(
        value for value in finance.assumption_sets.values()
        if value.name.startswith("Pension Independence"))
    inputs = PensionIndependenceInputs.from_assumption_set(assumption_set)
    terminal = ForecastPoint(100.0, 70.0, 80.0, 110.0)

    assert assessor._trajectory_state(
        True, 10.0, 10.0, terminal, 100.0, 100.0, inputs
    ) == ("Complete", "green")
    assert assessor._trajectory_state(
        False, 10.0, 10.0, terminal, 100.0,
        10.0 + 36 * 365.2425 * 86_400 / 12, inputs,
    ) == ("Accelerated", "green")
    assert assessor._trajectory_state(
        False, 99.0, 99.0, terminal, 100.0, 100.0, inputs
    ) == ("Nominal", "green")
    assert assessor._trajectory_state(
        False, None, 99.0, terminal, 100.0, 100.0, inputs
    ) == ("Constrained", "amber")
    assert assessor._trajectory_state(
        False, None, None, terminal, 100.0, 100.0, inputs
    ) == ("Divergent", "amber")
    critical = type(terminal)(100.0, 60.0, 70.0, 72.0)
    assert assessor._trajectory_state(
        False, None, None, critical, 100.0, 100.0, inputs
    ) == ("Critical", "red")


def test_liquidity_precedence_suppresses_contribution_recommendation(
        tmp_path):
    log, household = _seed(tmp_path)
    assessor, core, _ = _assessor(log)
    real_dispatch = assessor.metrics.dispatch

    def dispatch(request):
        if request.metric_id == "finance.liquidity_runway":
            return MetricResult(
                request.metric_id,
                3.0,
                "months",
                request.scope,
                request.as_of,
                "available",
                "test-v1",
                input_references=("liquidity-observation",),
            )
        return real_dispatch(request)

    assessor.metrics.dispatch = dispatch
    mission = next(
        value for value in core.missions.values()
        if value.assessment_policy_id == POLICY_ID)
    as_of = max(event["ts"] for event in log.events())
    assessment = assessor.assess(MissionAssessmentRequest(
        mission.id,
        POLICY_ID,
        Subject("party", household.household_id),
        as_of,
    ))

    assert len(assessment.recommendations) == 1
    recommendation = assessment.recommendations[0]
    assert recommendation.status == "suppressed"
    assert "3.0 months" in recommendation.action
    assert "36-month recommendation floor" not in recommendation.action
    assert "6-month recommendation floor" in recommendation.action
    assert "Financial Resilience takes precedence" in recommendation.action
    assert "recommendation_liquidity_floor_months" not in recommendation.action


def test_absent_state_pension_reliance_factor_is_explicitly_excluded(
        tmp_path):
    log, household = _seed(tmp_path)
    assessor, core, finance = _assessor(log)
    assessment = _assessment(log, household)
    mission = next(
        value for value in core.missions.values()
        if value.assessment_policy_id == POLICY_ID)
    assumption_set = finance.assumption_sets[mission.assumption_set_id]
    inputs = PensionIndependenceInputs.from_assumption_set(assumption_set)
    request = MissionAssessmentRequest(
        mission.id,
        POLICY_ID,
        Subject("party", household.household_id),
        assessment.as_of,
    )

    margin, factors = assessor._margin(
        1_000.0,
        40_000.0,
        assessment.eta,
        assessment.eta,
        assessment.eta,
        None,
        inputs,
        assessment.current_value,
        assessment.forecast[-1].base,
        assumption_set,
        request,
    )

    assert "State Pension reliance excluded" in margin.description
    assert all(
        item.label != "STATE PENSION RELIANCE BAND" for item in factors)


def test_invalid_envelope_is_quarantined_and_caps_confidence(tmp_path):
    log, household = _seed(tmp_path)
    hostile = "<script>alert('private')</script>"
    log.append(EVENT_KIND, {
        "subject_id": household.alex_pension_id,
        "field": "annual_fee_percent",
        "value": hostile,
        "effective_at": household.as_of,
        "confidence": .9,
        "source": hostile,
        "lineage": hostile,
        "unit_or_currency": "fraction",
    })

    assessment = _assessment(log, household)
    exposed = " ".join((
        assessment.confidence.basis,
        *assessment.limitations,
    ))

    assert assessment.confidence.state == "Provisional"
    assert "invalid pension envelopes are quarantined" \
        in assessment.confidence.basis
    assert hostile not in exposed


def test_future_evidence_is_excluded_with_visible_limitation(tmp_path):
    log, household = _seed(tmp_path)
    as_of = max(event["ts"] for event in log.events())
    before = _assessment(log, household, as_of=as_of)
    record_pension_evidence(
        log,
        household.alex_pension_id,
        "employee_contribution_annual",
        99_999.0,
        as_of + 86_400,
        confidence=.9,
        source="future declaration",
        lineage="future-dated regression fixture",
        unit_or_currency="GBP",
    )

    after = _assessment(log, household, as_of=as_of)

    assert after.current_value == before.current_value
    assert after.forecast == before.forecast
    assert any(
        "1 future-dated pension declaration(s) are excluded" in limitation
        for limitation in after.limitations
    )


def test_telemetry_hierarchy_has_three_essential_items_and_per_year_labels(
        tmp_path):
    log, household = _seed(tmp_path)
    assessment = _assessment(log, household)

    essential = [
        item for item in assessment.telemetry
        if item.display_region == "essential"
    ]
    assert [item.label for item in essential] == [
        "CURRENT PENSION",
        "REQUIRED RETIREMENT WEALTH",
        "FUNDING RATIO",
    ]
    assert not any(
        item.display_region == "hero" for item in assessment.telemetry)
    assert all(
        item.display_group for item in assessment.telemetry
        if item.display_region == "drilldown")
    for item in assessment.telemetry:
        if item.result.status in ("available", "stale"):
            assert (
                item.result.input_references
                or item.result.evidence_references
                or item.result.assumption_references
            )
        if "INCOME" in item.label or "CONTRIBUTIONS" in item.label:
            assert "PER YEAR" in item.label or "TAX YEAR" in item.label \
                or "THIS TAX YEAR" in item.label \
                or "PER YEAR" in item.qualifier
    projected = [
        item for item in assessment.telemetry
        if "PROJECTED" in item.label or "ESTIMATED RETIREMENT" in item.label
    ]
    assert projected
    assert all("PATH" in item.qualifier for item in projected)
    scenarios = [
        item.label for item in assessment.telemetry
        if item.display_group == "PROJECTION SCENARIOS"
    ]
    assert scenarios == [
        "EXPECTED PATH",
        "CONSERVATIVE CASE",
        "OPTIMISTIC CASE",
    ]


def test_assessment_and_render_inputs_are_deterministic_and_read_only(tmp_path):
    log, household = _seed(tmp_path)
    path = tmp_path / "events.jsonl"
    before = path.read_bytes()

    first = _assessment(log, household)
    second = _assessment(log, household)

    assert first == second
    assert path.read_bytes() == before
    assert log.verify()


def test_provider_has_no_registry_or_assessor_dependency():
    import foundry.finance.pension_assessment as module

    tree = ast.parse(inspect.getsource(module))
    imported = {
        alias.name for node in ast.walk(tree)
        if isinstance(node, ast.Import) for alias in node.names
    } | {
        node.module for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert not any(
        name and "MissionAssessmentRegistry" in name for name in imported)
    assert not any(
        name and (
            "mortgage_assessment" in name
            or "resilience_assessment" in name
        )
        for name in imported
    )
    source = inspect.getsource(PensionIndependenceAssessor)
    assert "MissionAssessmentRegistry" not in source


def test_no_probability_or_advice_boundary_language_in_assessment(tmp_path):
    log, household = _seed(tmp_path)
    assessment = _assessment(log, household)
    rendered_contract = " ".join((
        assessment.mission_margin.description,
        assessment.confidence.basis,
        *assessment.limitations,
        *(item.label + " " + item.qualifier for item in assessment.telemetry),
        *(recommendation.action for recommendation in assessment.recommendations),
    )).lower()

    for forbidden in (
        "chance of success",
        "success probability",
        "probability",
        "2 of 3",
        "pension transfer",
        "consolidat",
        "provider selection",
    ):
        assert forbidden not in rendered_contract
    assert "not regulated financial advice" in rendered_contract

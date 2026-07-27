"""RFC-005 Financial Independence calculation and assessment tests."""

import pytest

from foundry.core.entities import EntityProjection, declare_party, join_household
from foundry.core.metrics import MetricRegistry, MetricRequest
from foundry.core.mission_assessment import MissionAssessmentRequest
from foundry.core.scope import Subject
from foundry.demo_data import build
from foundry.eventlog import EventLog
from foundry.finance import entities as fin
from foundry.finance.entities import FinanceEntityProjection
from foundry.finance.metrics import FinanceMetricProvider
from foundry.finance.mission_assessment import (
    FinanceProjectionEngine, FinancialIndependenceAssessor,
    FinancialIndependencePolicy, ProjectionInputs, DAY, MONTH, MONTH_DAYS, YEAR,
)


NOW = 1_785_170_000.0


def _registry(log):
    core = EntityProjection(log)
    finance = FinanceEntityProjection(log)
    registry = MetricRegistry()
    registry.register(FinanceMetricProvider(finance, core))
    return core, finance, registry


@pytest.mark.parametrize("value,phase", [
    (449_999.99, "Building Capital"),
    (450_000.0, "Escape Velocity"),
    (749_999.99, "Escape Velocity"),
    (750_000.0, "Independent"),
    (1_500_000.0, "Independent"),
    (1_500_000.01, "Abundance"),
])
def test_phase_boundaries(value, phase):
    assert FinancialIndependencePolicy().phase_for(value).label == phase


def test_policy_bands_do_not_move_with_lifestyle_assumptions():
    policy = FinancialIndependencePolicy()
    original = tuple((p.label, p.lower_bound, p.upper_bound) for p in policy.phases)
    # Both are valid but imply very different lifestyle capital.
    for annual_spend, withdrawal_rate in ((30_000.0, .04), (48_000.0, .035)):
        implied = annual_spend / withdrawal_rate
        assert implied > 0
        assert tuple((p.label, p.lower_bound, p.upper_bound)
                     for p in policy.phases) == original


def test_policy_exposes_configurable_phase_presentation():
    policy = FinancialIndependencePolicy(
        building_capital_threshold=400_000.0,
        independent_threshold=800_000.0,
        abundance_threshold=1_600_000.0,
        building_capital_label="Capital Assembly",
        escape_velocity_label="Velocity Gate",
        independent_label="Choice Point",
        abundance_label="Surplus Orbit",
        unit_or_currency="USD",
    )

    phases = policy.phases
    assert tuple(phase.label for phase in phases) == (
        "Capital Assembly", "Velocity Gate", "Choice Point", "Surplus Orbit")
    assert tuple(phase.lower_bound for phase in phases) == (
        0.0, 400_000.0, 800_000.0, 1_600_000.0)
    assert tuple(phase.upper_bound for phase in phases) == (
        400_000.0, 800_000.0, 1_600_000.0, None)
    assessed = policy.phase_for(500_000.0)
    assert assessed.label == "Velocity Gate"
    assert assessed.unit_or_currency == "USD"


def test_policy_rejects_malformed_phase_configuration():
    with pytest.raises(ValueError, match="strictly increasing"):
        FinancialIndependencePolicy(
            building_capital_threshold=750_000.0,
            independent_threshold=750_000.0)
    with pytest.raises(ValueError, match="non-empty and unique"):
        FinancialIndependencePolicy(independent_label="")
    with pytest.raises(ValueError, match="unit_or_currency"):
        FinancialIndependencePolicy(unit_or_currency="")


def test_projection_is_deterministic_and_range_widens():
    inputs = ProjectionInputs(
        monthly_contribution=2_000.0,
        low_real_return=.01, base_real_return=.04, high_real_return=.07,
        horizon_years=20, history_months=12, delta_v_lookback_days=90,
        desired_annual_spending=30_000.0, withdrawal_rate=.04)
    a = FinanceProjectionEngine.project(100_000.0, NOW, inputs)
    b = FinanceProjectionEngine.project(100_000.0, NOW, inputs)
    assert a == b
    assert a[0].low == a[0].base == a[0].high
    assert a[-1].high - a[-1].low > a[12].high - a[12].low > 0


def test_accessible_assets_exclude_pension_property_and_vehicle(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    household = declare_party(log, "household")
    person = declare_party(log, "person")
    join_household(log, person.id, household.id)

    cash = fin.declare_account(
        log, "checking", "GBP", liquidity_classification="liquid")
    fin.link_ownership(log, "account", cash.id, "owner", person.id)
    fin.declare_transaction(log, cash.id, 1_000.0, "GBP", "income", NOW)

    isa = fin.declare_account(
        log, "brokerage", "GBP", tax_wrapper="isa",
        liquidity_classification="near_liquid")
    fin.link_ownership(log, "account", isa.id, "owner", person.id)
    fin.declare_position(
        log, isa.id, "Tracker", 1.0, 50_000.0, "GBP", 45_000.0,
        NOW, 50_000.0, "other")

    pension = fin.declare_account(
        log, "pension", "GBP", tax_wrapper="pension_wrapper",
        liquidity_classification="illiquid_long")
    fin.link_ownership(log, "account", pension.id, "owner", person.id)
    fin.declare_transaction(
        log, pension.id, 200_000.0, "GBP", "pension_contribution", NOW)

    home = fin.declare_asset(
        log, "property", "GBP", liquidity_classification="illiquid_long")
    fin.link_ownership(log, "asset", home.id, "owner", person.id)
    fin.declare_valuation(log, home.id, 600_000.0, "GBP", NOW)

    car = fin.declare_asset(
        log, "vehicle", "GBP", liquidity_classification="illiquid_short")
    fin.link_ownership(log, "asset", car.id, "owner", person.id)
    fin.declare_valuation(log, car.id, 20_000.0, "GBP", NOW)

    core, finance, registry = _registry(log)
    result = registry.dispatch(MetricRequest(
        "finance.accessible_assets", Subject("party", household.id), NOW))
    assert result.status == "available"
    assert result.value == pytest.approx(51_000.0)
    assert result.value < registry.dispatch(MetricRequest(
        "finance.net_worth", Subject("party", household.id), NOW)).value


def test_assumption_set_and_scenario_replay_deterministically(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    assumptions = fin.declare_assumption_set(
        log, "Baseline", "v1", {"base_real_return": .04})
    scenario = fin.declare_scenario(
        log, "Contribute more", assumptions.id,
        {"monthly_contribution_delta": 250.0})
    first = FinanceEntityProjection(log)
    second = FinanceEntityProjection(log)
    assert vars(first.assumption_sets[assumptions.id]) == \
           vars(second.assumption_sets[assumptions.id])
    assert vars(first.scenarios[scenario.id]) == vars(second.scenarios[scenario.id])


def test_structured_scenario_replays_deterministically(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    assumptions = fin.declare_assumption_set(
        log, "Baseline", "v1", {"base_real_return": .04})
    scenario = fin.declare_scenario(
        log, "The prose amount is deliberately £999", assumptions.id,
        {"monthly_contribution_delta": 250.0},
        action_type="increase_contribution",
        action_label="Increase ISA contribution",
        unit_or_currency="gbp",
        cadence="month",
    )
    first = FinanceEntityProjection(log).scenarios[scenario.id]
    second = FinanceEntityProjection(log).scenarios[scenario.id]

    assert first.adjustments["monthly_contribution_delta"] == 250.0
    assert first.action_label == "Increase ISA contribution"
    assert first.unit_or_currency == "GBP"
    assert first.cadence == "month"
    assert vars(first) == vars(second)


def test_monthly_contribution_accepts_only_monthly_cadence(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    assumptions = fin.declare_assumption_set(
        log, "Baseline", "v1", {"base_real_return": .04})

    scenario = fin.declare_scenario(
        log, "Valid monthly contribution", assumptions.id,
        {"monthly_contribution_delta": 250.0},
        action_type="increase_contribution",
        action_label="Increase ISA contribution",
        unit_or_currency="GBP",
        cadence="month")

    assert scenario.cadence == "month"
    assert FinanceEntityProjection(log).scenarios[scenario.id].cadence == "month"


@pytest.mark.parametrize("cadence", [
    "week",
    "year",
    "MONTH",
    "monthly",
    " month ",
])
def test_monthly_contribution_rejects_contradictory_or_malformed_cadence(
        tmp_path, cadence):
    log = EventLog(tmp_path / "events.jsonl")
    assumptions = fin.declare_assumption_set(
        log, "Baseline", "v1", {"base_real_return": .04})
    event_count = len(tuple(log.events()))

    with pytest.raises(
            ValueError,
            match="monthly_contribution_delta requires cadence 'month'"):
        fin.declare_scenario(
            log, "Invalid cadence", assumptions.id,
            {"monthly_contribution_delta": 250.0},
            action_type="increase_contribution",
            action_label="Increase ISA contribution",
            unit_or_currency="GBP",
            cadence=cadence)

    # Validation happens before the append-only log is mutated.
    assert len(tuple(log.events())) == event_count


def test_monthly_contribution_rejects_non_string_cadence_before_append(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    assumptions = fin.declare_assumption_set(
        log, "Baseline", "v1", {"base_real_return": .04})
    event_count = len(tuple(log.events()))

    with pytest.raises(ValueError, match="declared together"):
        fin.declare_scenario(
            log, "Malformed cadence", assumptions.id,
            {"monthly_contribution_delta": 250.0},
            action_type="increase_contribution",
            action_label="Increase ISA contribution",
            unit_or_currency="GBP",
            cadence=12)

    assert len(tuple(log.events())) == event_count


def test_structured_scenario_fields_are_validated_together(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    assumptions = fin.declare_assumption_set(
        log, "Baseline", "v1", {"base_real_return": .04})

    with pytest.raises(ValueError, match="declared together"):
        fin.declare_scenario(
            log, "Incomplete", assumptions.id,
            {"monthly_contribution_delta": 250.0},
            action_label="Increase ISA contribution")
    with pytest.raises(ValueError, match="three-letter currency"):
        fin.declare_scenario(
            log, "Bad currency", assumptions.id,
            {"monthly_contribution_delta": 250.0},
            action_type="increase_contribution",
            action_label="Increase ISA contribution",
            unit_or_currency="sterling",
            cadence="month")


def _assessment_with_replacement_scenario(path, amount, *,
                                          name="Any descriptive name",
                                          structured=True,
                                          unit_or_currency="GBP"):
    log = EventLog(path)
    household = build(log, as_of=NOW)
    initial = FinanceEntityProjection(log)
    original = next(
        scenario for scenario in initial.scenarios.values()
        if scenario.status == "active")
    fin.archive_scenario(log, original.id, "test replacement")
    presentation = {}
    if structured:
        presentation = {
            "action_type": "increase_contribution",
            "action_label": "Increase ISA contribution",
            "unit_or_currency": unit_or_currency,
            "cadence": "month",
        }
    fin.declare_scenario(
        log, name, original.assumption_set_id,
        {"monthly_contribution_delta": amount}, **presentation)

    core, finance, registry = _registry(log)
    mission = next(iter(core.missions.values()))
    as_of = max(event["ts"] for event in log.events())
    return FinancialIndependenceAssessor(
        finance, core, registry).assess(MissionAssessmentRequest(
            mission.id, mission.assessment_policy_id,
            Subject("party", household.household_id), as_of))


def test_recommendation_amount_comes_from_structured_adjustment_not_name(tmp_path):
    result = _assessment_with_replacement_scenario(
        tmp_path / "events.jsonl", 250.0,
        name="Descriptive name says £999 and must not drive presentation")
    recommendation = result.recommendations[0]

    assert recommendation.status == "available"
    assert recommendation.amount == 250.0
    assert recommendation.action == \
        "Descriptive name says £999 and must not drive presentation"
    assert recommendation.action_label == "Increase ISA contribution"
    assert recommendation.adjustment_key == "monthly_contribution_delta"
    assert recommendation.unit_or_currency == "GBP"
    assert recommendation.cadence == "month"


def test_structured_amount_changes_display_contract_and_modelled_impact(tmp_path):
    smaller = _assessment_with_replacement_scenario(
        tmp_path / "smaller.jsonl", 250.0)
    larger = _assessment_with_replacement_scenario(
        tmp_path / "larger.jsonl", 500.0)
    small_action = smaller.recommendations[0]
    large_action = larger.recommendations[0]

    assert small_action.amount == 250.0
    assert large_action.amount == 500.0
    assert large_action.estimated_delta_v_days \
        > small_action.estimated_delta_v_days > 0
    assert large_action.estimated_delta_v_months \
        >= small_action.estimated_delta_v_months >= 1


def test_missing_structured_scenario_data_returns_unavailable_recommendation(tmp_path):
    result = _assessment_with_replacement_scenario(
        tmp_path / "events.jsonl", 275.0, structured=False,
        name="Legacy prose £999")
    recommendation = result.recommendations[0]

    assert recommendation.status == "unavailable"
    assert recommendation.amount == 275.0
    assert recommendation.estimated_delta_v_days is None
    assert "incomplete" in recommendation.limitations[0]


def test_non_gbp_scenario_is_preserved_and_fails_currency_mismatch_honestly(tmp_path):
    result = _assessment_with_replacement_scenario(
        tmp_path / "events.jsonl", 275.0, unit_or_currency="USD")
    recommendation = result.recommendations[0]

    assert recommendation.status == "unavailable"
    assert recommendation.amount == 275.0
    assert recommendation.unit_or_currency == "USD"
    assert "currency does not match" in recommendation.limitations[0]


def test_malformed_structured_adjustment_fails_honestly(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    household = build(log, as_of=NOW)
    core = EntityProjection(log)
    finance = FinanceEntityProjection(log)
    scenario = next(iter(finance.scenarios.values()))
    scenario.adjustments["monthly_contribution_delta"] = "not-a-number"
    registry = MetricRegistry()
    registry.register(FinanceMetricProvider(finance, core))
    mission = next(iter(core.missions.values()))
    result = FinancialIndependenceAssessor(
        finance, core, registry).assess(MissionAssessmentRequest(
            mission.id, mission.assessment_policy_id,
            Subject("party", household.household_id), NOW))

    recommendation = result.recommendations[0]
    assert recommendation.status == "unavailable"
    assert recommendation.amount is None
    assert recommendation.estimated_delta_v_days is None
    assert "adjustment is invalid" in recommendation.limitations[0]


@pytest.mark.parametrize("status,complete,expected", [
    ("green", False, ("ahead", "Ahead")),
    ("amber", False, ("nominal", "Nominal")),
    ("red", False, ("at_risk", "At Risk")),
    ("green", True, ("complete", "Mission Complete")),
])
def test_flight_status_is_distinct_from_phase(status, complete, expected):
    assert FinancialIndependenceAssessor._flight_status(
        status, complete) == expected


def test_schedule_status_boundaries():
    target = NOW + YEAR
    assert FinancialIndependenceAssessor._status(
        False, target - DAY, target - DAY, target) == "green"
    assert FinancialIndependenceAssessor._status(
        False, target + DAY, target - DAY, target) == "amber"
    assert FinancialIndependenceAssessor._status(
        False, target + DAY, target + DAY, target) == "red"
    assert FinancialIndependenceAssessor._status(
        True, None, None, target) == "green"


def test_delta_v_precision_matches_monthly_projection_resolution():
    below_month = FinancialIndependenceAssessor._delta_v(
        NOW + (MONTH_DAYS - .01) * DAY, NOW, 90)
    one_month = FinancialIndependenceAssessor._delta_v(
        NOW + MONTH, NOW, 90)
    several_months = FinancialIndependenceAssessor._delta_v(
        NOW + 3 * MONTH, NOW, 90)
    delayed = FinancialIndependenceAssessor._delta_v(
        NOW - 2 * MONTH, NOW, 90)
    unavailable = FinancialIndependenceAssessor._delta_v(None, NOW, 90)
    complete = FinancialIndependenceAssessor._delta_v(
        NOW + MONTH, NOW, 90, complete=True)

    assert (below_month.months, below_month.direction) == (0, "accelerated")
    assert (one_month.months, one_month.direction) == (1, "accelerated")
    assert (several_months.months, several_months.direction) == (3, "accelerated")
    assert (delayed.months, delayed.direction) == (-2, "delayed")
    assert unavailable.months is None and unavailable.days is None
    assert complete.months is None and complete.days is None
    assert "Mission complete" in complete.description
    for result in (below_month, one_month, several_months, delayed):
        assert result.resolution == "month"


def test_full_financial_independence_assessment_is_read_only(tmp_path):
    path = tmp_path / "events.jsonl"
    log = EventLog(path)
    household = build(log, as_of=NOW)
    core, finance, registry = _registry(log)
    mission = next(iter(core.missions.values()))
    as_of = max(event["ts"] for event in log.events())
    before = path.read_bytes()

    result = FinancialIndependenceAssessor(
        finance, core, registry).assess(MissionAssessmentRequest(
            mission.id, mission.assessment_policy_id,
            Subject("party", household.household_id), as_of))

    assert path.read_bytes() == before
    assert result.status in ("green", "amber", "red")
    assert result.current_value.metric_id == "finance.accessible_assets"
    assert result.current_value.value < registry.dispatch(MetricRequest(
        "finance.net_worth", result.scope, as_of)).value
    assert result.phase.label == "Building Capital"
    assert result.flight_status_label in ("Ahead", "Nominal", "At Risk")
    assert len(result.phases) == 4
    assert result.phases[2].completes_mission
    assert all(phase.unit_or_currency == "GBP" for phase in result.phases)
    assert result.eta is not None
    assert result.forecast
    assert result.forecast[-1].high > result.forecast[-1].low
    assert result.delta_v.days is not None
    assert result.delta_v.months is not None
    assert result.recommendations[0].estimated_delta_v_days > 0
    assert result.recommendations[0].amount == 250.0
    assert result.recommendations[0].estimated_delta_v_months >= 1
    assert result.assumption_references
    assert "NOT A PROBABILITY" in result.confidence_basis
    assert "%" not in result.confidence_basis


def test_existing_mission_events_replay_without_assessment_fields(tmp_path):
    from foundry.core.entities import declare_mission

    log = EventLog(tmp_path / "events.jsonl")
    mission = declare_mission(
        log, "Legacy mission", target_metric="finance.net_worth",
        target_value=100_000.0)
    replayed = EntityProjection(log).missions[mission.id]
    assert replayed.assessment_policy_id is None
    assert replayed.assumption_set_id is None

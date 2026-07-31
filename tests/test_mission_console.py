"""RFC-010: the Mission Console Model is pure and domain-neutral."""

from dataclasses import replace

from foundry.core.metrics import MetricResult
from foundry.core.mission_assessment import (
    DeltaV,
    ForecastPoint,
    InstrumentApplicability,
    MissionAssessment,
    MissionConfidence,
    MissionDefinition,
    MissionMargin,
    MissionMilestone,
    RecommendationAssessment,
    TelemetryItem,
)
from foundry.core.mission_console import (
    DISCLOSURE_SLOT_ORDER,
    MissionConsoleModel,
)
from foundry.core.scope import Subject


def _assessment(*, essential_count=3, recommendation_status="available"):
    scope = Subject("party", "subject-1")
    current = MetricResult(
        "domain.capacity", 42.0, "units", scope, 100.0,
        "available", "domain-v1",
    )
    milestone = MissionMilestone(
        "operating", "Operating", 0.0, 100.0, .42,
        unit_or_currency="units", is_current=True,
        completes_mission=True, destination_value=100.0,
    )
    telemetry = tuple(
        TelemetryItem(
            replace(current, metric_id=f"domain.essential-{index}"),
            f"ESSENTIAL {index}",
            "number",
            display_region="essential",
        )
        for index in range(essential_count)
    ) + (
        TelemetryItem(
            current,
            "OPERATING CAPACITY",
            "number",
            display_region="drilldown",
            display_group="OPERATING EVIDENCE",
        ),
    )
    recommendation = RecommendationAssessment(
        action="Increase declared capacity by 5 units.",
        scenario_id="scenario-1",
        estimated_delta_v_days=30.0,
        status=recommendation_status,
        action_label="Increase capacity",
        amount=5.0,
        unit_or_currency="units",
        cadence="cycle",
        estimated_delta_v_months=1,
        delta_v_direction="accelerated",
        limitations=("Operate inside the declared safety envelope.",),
    )
    return MissionAssessment(
        mission_id="mission-1",
        policy_id="domain.mission.v1",
        scope=scope,
        as_of=100.0,
        status="green",
        calculation_version="domain-v1",
        current_value=current,
        eta=200.0,
        trajectory_state="Nominal",
        trajectory_tone="green",
        confidence=MissionConfidence("Provisional", "One input is stale."),
        current_milestone=milestone,
        milestones=(milestone,),
        mission_margin=MissionMargin(
            None, None, "Five units of tolerance.", "Adequate Margin",
            label="OPERATING RESERVE", value=5.0,
            unit_or_currency="units", format_kind="number",
        ),
        delta_v=DeltaV(
            30.0, 30, "one month accelerated", months=1,
            direction="accelerated",
        ),
        forecast=(ForecastPoint(100.0, 42.0, 42.0, 42.0),),
        telemetry=telemetry,
        recommendations=(recommendation,),
        confidence_basis="One input is stale.",
        limitations=("Forecast is deterministic.",),
        applicability=InstrumentApplicability(trajectory="unavailable"),
    )


def _definition():
    return MissionDefinition(
        "operating-capacity", "Operating Capacity", 1,
        "higher_is_better", "Maintain sufficient operating capacity.",
        "domain.mission.v1",
    )


def test_model_owns_fixed_region_order_and_omits_no_declared_cell():
    view = MissionConsoleModel().build(_definition(), _assessment())

    assert view.region_order == (
        "mission-hero",
        "flight-analysis",
        "essential-telemetry",
        "next-burn",
        "progressive-disclosure",
    )
    assert len(view.essential.items) == 3
    assert len(view.analysis.supporting) == 3
    assert all(item.value is not None for item in view.analysis.supporting)


def test_zero_essential_items_omits_the_region_without_padding():
    view = MissionConsoleModel().build(
        _definition(), _assessment(essential_count=0))

    assert view.essential is None
    assert "essential-telemetry" not in view.region_order


def test_one_essential_item_remains_one_item_without_padding():
    view = MissionConsoleModel().build(
        _definition(), _assessment(essential_count=1))

    assert view.essential is not None
    assert len(view.essential.items) == 1
    assert view.essential.items[0].label == "ESSENTIAL 0"
    assert len(view.analysis.supporting) == 3


def test_disclosure_slot_order_and_provider_titles_are_preserved():
    view = MissionConsoleModel().build(_definition(), _assessment())
    slot_rank = {slot: index for index, slot in enumerate(
        DISCLOSURE_SLOT_ORDER)}

    assert [section.slot for section in view.disclosure] == sorted(
        [section.slot for section in view.disclosure],
        key=slot_rank.__getitem__,
    )
    assert view.disclosure[0].title == "OPERATING EVIDENCE"
    assert view.disclosure[0].telemetry[0].label == "OPERATING CAPACITY"


def test_disclosure_stays_collapsed_when_evidence_reports_a_conflict():
    assessment = replace(
        _assessment(),
        limitations=("Critical source conflict remains visible.",),
    )

    view = MissionConsoleModel().build(_definition(), assessment)

    assert all(not section.open_by_default for section in view.disclosure)


def test_primary_burn_hoists_limitations_and_provisional_confidence_basis():
    view = MissionConsoleModel().build(_definition(), _assessment())

    assert view.next_burn.state == "available"
    assert view.hero.burn_preview == "Increase capacity"
    assert view.next_burn.safety_notices == (
        "Operate inside the declared safety envelope.",
        "One input is stale.",
    )


def test_unknown_movement_is_a_legitimate_non_degrading_state():
    view = MissionConsoleModel().build(_definition(), _assessment())

    assert view.hero.trajectory.movement == "unknown"
    assert view.hero.trajectory.tone == "green"
    assert "unavailable" in view.hero.trajectory.evidence_note.lower()

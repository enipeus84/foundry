"""RFC-005: Core owns assessment shapes and routing, never domain logic."""

import ast
from dataclasses import fields
import inspect
import pkgutil
import importlib

import pytest

from foundry.core.metrics import MetricResult
from foundry.core.mission_assessment import (
    DeltaV, ForecastPoint, MissionAssessment, MissionAssessmentRegistry,
    MissionAssessmentRequest, MissionConfidence, MissionDefinition,
    MissionMargin, MissionMilestone,
    InstrumentApplicability, RecommendationAssessment, TelemetryItem,
    TrajectoryPoint,
)
from foundry.core.scope import Subject
from foundry.errors import DuplicateMissionAssessmentError


class _Provider:
    def __init__(self, policy_id="alpha.mission.v1"):
        self.policy_id = policy_id

    def owned_policy_ids(self):
        return frozenset({self.policy_id})

    def assess(self, request):
        return MissionAssessment(
            mission_id=request.mission_id, policy_id=request.policy_id,
            scope=request.scope, as_of=request.as_of, status="green",
            calculation_version="test-v1",
            eta=request.as_of + 1.0,
            delta_v=DeltaV(1.0, 1, "test schedule change"),
            mission_margin=MissionMargin(
                None, None, "one unit of operating tolerance",
                "Adequate Margin", value=1.0, unit_or_currency="units"),
            trajectory=(TrajectoryPoint(request.as_of, 1.0),),
            forecast=(
                ForecastPoint(request.as_of, 1.0, 1.0, 1.0),
            ))


def _request(policy_id="alpha.mission.v1"):
    return MissionAssessmentRequest(
        mission_id="mission-1", policy_id=policy_id,
        scope=Subject("party", "household-1"), as_of=1.0)


def test_registry_dispatches_by_policy_id():
    registry = MissionAssessmentRegistry()
    registry.register(_Provider())
    result = registry.dispatch(_request())
    assert result.status == "green"
    assert result.policy_id == "alpha.mission.v1"


def test_household_and_member_subjects_remain_explicit_and_distinct():
    registry = MissionAssessmentRegistry()
    registry.register(_Provider())
    member_request = MissionAssessmentRequest(
        mission_id="mission-1",
        policy_id="alpha.mission.v1",
        scope=Subject("party", "member-1"),
        as_of=1.0,
    )

    member_result = registry.dispatch(member_request)

    assert member_result.scope == Subject("party", "member-1")
    assert member_result.scope != _request().scope


def test_unknown_policy_fails_closed():
    result = MissionAssessmentRegistry().dispatch(_request("nobody.owns.this"))
    assert result.status == "unavailable"
    assert result.calculation_version == ""
    assert "no provider registered" in result.limitations[0]


def test_duplicate_policy_registration_fails_closed():
    registry = MissionAssessmentRegistry()
    registry.register(_Provider())
    with pytest.raises(DuplicateMissionAssessmentError):
        registry.register(_Provider())


def test_definitions_are_discovered_in_stable_order():
    registry = MissionAssessmentRegistry()
    registry.register_definition(MissionDefinition(
        slug="mission-b", label="Mission B", order=20,
        destination_direction="lower_is_better"))
    registry.register_definition(MissionDefinition(
        slug="mission-a", label="Mission A", order=10,
        destination_direction="higher_is_better",
        assessment_policy_id="alpha.mission.v1"))

    assert [item.slug for item in registry.definitions()] == [
        "mission-a", "mission-b",
    ]
    assert registry.definition_for_slug("mission-a").label == "Mission A"
    assert (
        registry.definition_for_policy("alpha.mission.v1").slug
        == "mission-a"
    )


@pytest.mark.parametrize("slug", [
    "../mission", "Mission Name", "mission/name", "mission?name", "",
])
def test_forged_or_unsafe_definition_slug_is_rejected(slug):
    with pytest.raises(ValueError):
        MissionDefinition(
            slug=slug, label="Mission", order=1,
            destination_direction="higher_is_better")


def test_unsupported_definition_direction_is_rejected():
    with pytest.raises(ValueError):
        MissionDefinition(
            slug="mission", label="Mission", order=1,
            destination_direction="sideways")


@pytest.mark.parametrize("overrides", [
    {"order": float("nan")},
    {"definition": None},
    {"assessment_policy_id": 123},
])
def test_unsupported_definition_runtime_data_is_rejected(overrides):
    values = {
        "slug": "mission",
        "label": "Mission",
        "order": 1,
        "destination_direction": "higher_is_better",
    }
    values.update(overrides)
    with pytest.raises(ValueError):
        MissionDefinition(**values)


def test_duplicate_definition_order_and_policy_fail_closed():
    registry = MissionAssessmentRegistry()
    registry.register_definition(MissionDefinition(
        "mission-a", "Mission A", 1, "higher_is_better",
        assessment_policy_id="alpha.mission.v1"))
    with pytest.raises(DuplicateMissionAssessmentError):
        registry.register_definition(MissionDefinition(
            "mission-b", "Mission B", 1, "higher_is_better"))
    with pytest.raises(DuplicateMissionAssessmentError):
        registry.register_definition(MissionDefinition(
            "mission-b", "Mission B", 2, "higher_is_better",
            assessment_policy_id="alpha.mission.v1"))


class _MalformedProvider(_Provider):
    def assess(self, request):
        raise ValueError("private provider detail")


class _ForgedEnvelopeProvider(_Provider):
    def assess(self, request):
        return MissionAssessment(
            mission_id="somebody-elses-mission",
            policy_id=request.policy_id,
            scope=request.scope,
            as_of=request.as_of,
            status="green",
            calculation_version="test-v1",
        )


class _CrossScopeProvider(_Provider):
    def assess(self, request):
        return MissionAssessment(
            mission_id=request.mission_id,
            policy_id=request.policy_id,
            scope=Subject("party", "member-1"),
            as_of=request.as_of,
            status="green",
            calculation_version="test-v1",
        )


class _MalformedMilestoneProvider(_Provider):
    def assess(self, request):
        milestone = MissionMilestone(
            "milestone", None, 0.0, 1.0, .5)
        return MissionAssessment(
            mission_id=request.mission_id,
            policy_id=request.policy_id,
            scope=request.scope,
            as_of=request.as_of,
            status="green",
            calculation_version="test-v1",
            current_milestone=milestone,
            milestones=(milestone,),
        )


class _MalformedForecastProvider(_Provider):
    def assess(self, request):
        return MissionAssessment(
            mission_id=request.mission_id,
            policy_id=request.policy_id,
            scope=request.scope,
            as_of=request.as_of,
            status="green",
            calculation_version="test-v1",
            forecast=(ForecastPoint(2.0, 1.0, float("nan"), 3.0),),
        )


class _CrossScopeMetricProvider(_Provider):
    def assess(self, request):
        return MissionAssessment(
            mission_id=request.mission_id,
            policy_id=request.policy_id,
            scope=request.scope,
            as_of=request.as_of,
            status="green",
            calculation_version="test-v1",
            current_value=MetricResult(
                "alpha.metric", 1.0, None,
                Subject("party", "member-1"), request.as_of,
                "available", "test-v1"),
        )


class _WrongTimestampMetricProvider(_Provider):
    def assess(self, request):
        return MissionAssessment(
            mission_id=request.mission_id,
            policy_id=request.policy_id,
            scope=request.scope,
            as_of=request.as_of,
            status="green",
            calculation_version="test-v1",
            current_value=MetricResult(
                "alpha.metric", 1.0, None, request.scope,
                request.as_of - 1.0, "available", "test-v1"),
        )


class _MissingMetricValueProvider(_Provider):
    def __init__(self, evidence_status):
        super().__init__()
        self.evidence_status = evidence_status

    def assess(self, request):
        return MissionAssessment(
            mission_id=request.mission_id,
            policy_id=request.policy_id,
            scope=request.scope,
            as_of=request.as_of,
            status="green",
            calculation_version="test-v1",
            current_value=MetricResult(
                "alpha.metric", None, None, request.scope,
                request.as_of, self.evidence_status, "test-v1"),
        )


class _FutureObservationProvider(_Provider):
    def assess(self, request):
        return MissionAssessment(
            mission_id=request.mission_id,
            policy_id=request.policy_id,
            scope=request.scope,
            as_of=request.as_of,
            status="green",
            calculation_version="test-v1",
            trajectory=(
                TrajectoryPoint(request.as_of + 1.0, 1.0),
            ),
        )


class _PastForecastProvider(_Provider):
    def assess(self, request):
        return MissionAssessment(
            mission_id=request.mission_id,
            policy_id=request.policy_id,
            scope=request.scope,
            as_of=request.as_of,
            status="green",
            calculation_version="test-v1",
            forecast=(
                ForecastPoint(request.as_of - 1.0, 1.0, 2.0, 3.0),
            ),
        )


class _HostileDeltaVProvider(_Provider):
    def assess(self, request):
        delta_v = DeltaV(
            days=30.0,
            lookback_days=90,
            description="hostile schedule",
            reference_start_at=100.0,
            reference_start_label="REFERENCE START",
        )
        object.__setattr__(delta_v, "reference_start_label", "")
        return MissionAssessment(
            mission_id=request.mission_id,
            policy_id=request.policy_id,
            scope=request.scope,
            as_of=request.as_of,
            status="green",
            calculation_version="test-v1",
            delta_v=delta_v,
        )


class _HostileDeltaVTimestampProvider(_Provider):
    def assess(self, request):
        delta_v = DeltaV(
            days=30.0,
            lookback_days=90,
            description="hostile schedule",
            reference_destination_at=200.0,
            reference_destination_label="REFERENCE DESTINATION",
        )
        object.__setattr__(delta_v, "reference_destination_at", 1e300)
        return MissionAssessment(
            mission_id=request.mission_id,
            policy_id=request.policy_id,
            scope=request.scope,
            as_of=request.as_of,
            status="green",
            calculation_version="test-v1",
            delta_v=delta_v,
        )


@pytest.mark.parametrize("provider", [
    _MalformedProvider(),
    _ForgedEnvelopeProvider(),
    _CrossScopeProvider(),
    _MalformedMilestoneProvider(),
    _MalformedForecastProvider(),
    _CrossScopeMetricProvider(),
    _WrongTimestampMetricProvider(),
    _MissingMetricValueProvider("available"),
    _MissingMetricValueProvider("stale"),
    _FutureObservationProvider(),
    _PastForecastProvider(),
    _HostileDeltaVProvider(),
    _HostileDeltaVTimestampProvider(),
])
def test_malformed_provider_is_isolated_to_an_unavailable_envelope(provider):
    registry = MissionAssessmentRegistry()
    registry.register(provider)

    result = registry.dispatch(_request())

    assert result.status == "unavailable"
    assert result.confidence == MissionConfidence(
        "Insufficient", "assessment provider failed safely")
    assert result.limitations == ("assessment provider failed safely",)
    assert "private provider detail" not in repr(result)


def test_definition_direction_is_authoritative_for_provider_milestones():
    class DirectionProvider(_Provider):
        def __init__(self, direction):
            super().__init__()
            self.direction = direction

        def assess(self, request):
            milestone = MissionMilestone(
                "destination", "Destination", 0.0, 100.0, .5,
                is_current=True,
                destination_direction=self.direction,
                destination_value=50.0)
            return MissionAssessment(
                mission_id=request.mission_id,
                policy_id=request.policy_id,
                scope=request.scope,
                as_of=request.as_of,
                status="green",
                calculation_version="test-v1",
                current_milestone=milestone,
                milestones=(milestone,),
                eta=request.as_of + 1.0,
                    delta_v=DeltaV(1.0, 1, "test schedule change"),
                    mission_margin=MissionMargin(
                        None, None, "declared tolerance",
                        "Adequate Margin", value=1.0),
                trajectory=(TrajectoryPoint(request.as_of, 50.0),),
                forecast=(
                    ForecastPoint(request.as_of, 50.0, 50.0, 50.0),
                ),
            )

    definition = MissionDefinition(
        "mission", "Mission", 1, "lower_is_better",
        assessment_policy_id="alpha.mission.v1")
    mismatched = MissionAssessmentRegistry()
    mismatched.register_definition(definition)
    mismatched.register(DirectionProvider("higher_is_better"))
    matching = MissionAssessmentRegistry()
    matching.register_definition(definition)
    matching.register(DirectionProvider("lower_is_better"))

    assert mismatched.dispatch(_request()).status == "unavailable"
    assert matching.dispatch(_request()).status == "green"


def test_assessment_dimensions_are_independently_supplied():
    result = MissionAssessment(
        mission_id="mission-1", policy_id="alpha.mission.v1",
        scope=Subject("party", "household-1"), as_of=1.0,
        status="red", calculation_version="test-v1",
        trajectory_state="Accelerated",
        trajectory_tone="green",
        trajectory_movement="receding",
        mission_margin=MissionMargin(
            1.0, -1.0, "mixed margin signals", "Low Margin"),
        confidence=MissionConfidence("Established", "verified evidence"),
    )

    assert result.trajectory_state == "Accelerated"
    assert result.trajectory_tone == "green"
    assert result.trajectory_movement == "receding"
    assert result.mission_margin.state == "Low Margin"
    assert result.confidence.state == "Established"


def test_assessment_rejects_unknown_trajectory_movement_vocabulary():
    with pytest.raises(ValueError, match="unsupported trajectory movement"):
        MissionAssessment(
            mission_id="mission-1", policy_id="alpha.mission.v1",
            scope=Subject("party", "household-1"), as_of=1.0,
            status="red", calculation_version="test-v1",
            trajectory_movement="deteriorating",
        )


def test_milestone_direction_and_explicit_destination_are_domain_neutral():
    milestone = MissionMilestone(
        id="destination", label="Destination", lower_bound=0.0,
        upper_bound=100.0, completion=.25,
        destination_direction="lower_is_better", destination_value=12.0)

    assert milestone.target_value == 12.0
    assert "phase" not in {field.name for field in fields(MissionAssessment)}
    assert "phases" not in {field.name for field in fields(MissionAssessment)}
    assert "phase_thresholds" not in {
        field.name for field in fields(MissionAssessment)
    }


def test_core_assessment_contract_imports_no_product_domain():
    import foundry.core as core_pkg

    for _, name, _ in pkgutil.iter_modules(
            core_pkg.__path__, prefix="foundry.core."):
        module = importlib.import_module(name)
        tree = ast.parse(inspect.getsource(module))
        imported = {
            alias.name for node in ast.walk(tree)
            if isinstance(node, ast.Import) for alias in node.names
        } | {
            node.module for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        assert not any(
            module_name.startswith("foundry.finance")
            for module_name in imported), name


def test_extended_assessment_contract_is_domain_neutral_after_alias_retirement():
    milestone = MissionMilestone(
        id="phase-a", label="Phase A", lower_bound=0.0,
        upper_bound=10.0, completion=.5)
    delta_v = DeltaV(
        days=30.0, lookback_days=90, description="advanced")
    recommendation = RecommendationAssessment(
        action="Do the declared action", scenario_id="scenario-a",
        estimated_delta_v_days=30.0)
    result = MissionAssessment(
        mission_id="mission-a", policy_id="domain.policy.v1",
        scope=Subject("party", "household-a"), as_of=1.0,
        status="green", calculation_version="domain-v1",
        current_milestone=milestone, milestones=(milestone,), delta_v=delta_v,
        recommendations=(recommendation,))

    assert result.milestones == (milestone,)
    assert result.flight_status_id == ""
    assert result.forecast_resolution == "month"
    assert milestone.unit_or_currency is None
    assert milestone.completes_mission is False
    assert delta_v.months is None
    assert delta_v.period_label == ""
    assert delta_v.reference_start_at is None
    assert delta_v.reference_destination_at is None
    assert recommendation.amount is None
    assert recommendation.status == "available"


def test_delta_v_reference_schedule_metadata_is_explicit_and_paired():
    delta_v = DeltaV(
        days=30.0,
        lookback_days=365,
        description="advanced against the declared schedule",
        months=1,
        direction="accelerated",
        period_label="SINCE DECLARATION",
        reference_start_at=100.0,
        reference_start_label="REFERENCE START",
        reference_destination_at=200.0,
        reference_destination_label="REFERENCE DESTINATION",
    )

    assert delta_v.reference_start_label == "REFERENCE START"
    assert delta_v.reference_destination_label == "REFERENCE DESTINATION"

    with pytest.raises(ValueError, match="supplied together"):
        DeltaV(
            days=30.0,
            lookback_days=365,
            description="missing reference label",
            reference_start_at=100.0,
        )
    with pytest.raises(ValueError, match="finite"):
        DeltaV(
            days=30.0,
            lookback_days=365,
            description="hostile timestamp",
            reference_destination_at=float("nan"),
            reference_destination_label="REFERENCE DESTINATION",
        )
    with pytest.raises(ValueError, match="representable UTC timestamp"):
        DeltaV(
            days=30.0,
            lookback_days=365,
            description="unrepresentable timestamp",
            reference_destination_at=1e300,
            reference_destination_label="REFERENCE DESTINATION",
        )


def test_instrument_applicability_is_closed_and_defaults_to_applicable():
    applicability = InstrumentApplicability()
    assert (
        applicability.eta,
        applicability.delta_v,
        applicability.trajectory,
        applicability.forecast,
        applicability.margin,
    ) == ("applicable",) * 5

    with pytest.raises(ValueError, match="unsupported eta applicability"):
        InstrumentApplicability(eta="sometimes")


def test_telemetry_regions_are_closed_inert_and_grouped_for_disclosure():
    result = MetricResult(
        "domain.capacity",
        1.0,
        "units",
        _request().scope,
        _request().as_of,
        "available",
        "domain-v1",
    )
    default = TelemetryItem(result, "CAPACITY")

    assert default.display_region == "drilldown"
    assert default.display_group == ""

    for retired in ("hero", "analysis", "sidebar"):
        with pytest.raises(
                ValueError, match="unsupported telemetry display region"):
            TelemetryItem(result, "CAPACITY", display_region=retired)
    essential = TelemetryItem(
        result, "CAPACITY", display_region="essential")
    disclosure = TelemetryItem(
        result, "CAPACITY", display_region="drilldown",
        display_group="OPERATING POSITION")

    assert essential.display_region == "essential"
    assert disclosure.display_group == "OPERATING POSITION"

    with pytest.raises(ValueError, match="cannot declare a display group"):
        TelemetryItem(
            result,
            "CAPACITY",
            display_region="essential",
            display_group="POSITION",
        )
    with pytest.raises(ValueError, match="invalid telemetry display group"):
        TelemetryItem(
            result,
            "CAPACITY",
            display_region="drilldown",
            display_group="   ",
        )
    with pytest.raises(ValueError, match="invalid telemetry display group"):
        TelemetryItem(
            result,
            "CAPACITY",
            display_region="drilldown",
            display_group="X" * 81,
        )


@pytest.mark.parametrize(
    "count,status,expected",
    [(6, "available", "green"), (7, "available", "unavailable"),
     (1, "unavailable", "unavailable")],
)
def test_provider_envelope_caps_essential_telemetry_and_requires_evidence(
        count, status, expected):
    class EssentialProvider(_Provider):
        def assess(self, request):
            base = super().assess(request)
            result = MetricResult(
                "domain.capacity",
                1.0 if status == "available" else None,
                "units",
                request.scope,
                request.as_of,
                status,
                "domain-v1" if status == "available" else "",
            )
            return MissionAssessment(**{
                **base.__dict__,
                "telemetry": tuple(
                    TelemetryItem(
                        result,
                        f"CAPACITY {index}",
                        display_region="essential",
                    )
                    for index in range(count)
                ),
            })

    registry = MissionAssessmentRegistry()
    registry.register(EssentialProvider())

    assert registry.dispatch(_request()).status == expected


@pytest.mark.parametrize(
    "applicability,overrides",
    [
        (InstrumentApplicability(eta="applicable"), {"eta": None}),
        (
            InstrumentApplicability(delta_v="not_applicable"),
            {"delta_v": DeltaV(1.0, 1, "must be absent")},
        ),
        (
            InstrumentApplicability(trajectory="unavailable"),
            {"trajectory": (TrajectoryPoint(1.0, 1.0),)},
        ),
    ],
)
def test_applicability_and_instrument_presence_must_be_consistent(
    applicability, overrides
):
    class Provider(_Provider):
        def assess(self, request):
            values = {
                "mission_id": request.mission_id,
                "policy_id": request.policy_id,
                "scope": request.scope,
                "as_of": request.as_of,
                "status": "green",
                "calculation_version": "test-v1",
                "eta": request.as_of + 1.0,
                "delta_v": DeltaV(1.0, 1, "test schedule change"),
                "trajectory": (TrajectoryPoint(request.as_of, 1.0),),
                "forecast": (
                    ForecastPoint(request.as_of, 1.0, 1.0, 1.0),
                ),
                "applicability": applicability,
            }
            values.update(overrides)
            return MissionAssessment(**values)

    registry = MissionAssessmentRegistry()
    registry.register(Provider())
    result = registry.dispatch(_request())

    assert result.status == "unavailable"
    assert result.limitations == ("assessment provider failed safely",)


def test_unavailable_instrument_may_use_renderer_fallback_explanation():
    class Provider(_Provider):
        def assess(self, request):
            return MissionAssessment(
                mission_id=request.mission_id,
                policy_id=request.policy_id,
                scope=request.scope,
                as_of=request.as_of,
                status="green",
                calculation_version="test-v1",
                eta=request.as_of + 1.0,
                delta_v=DeltaV(1.0, 1, "test schedule change"),
                trajectory=(),
                forecast=(
                    ForecastPoint(request.as_of, 1.0, 1.0, 1.0),
                ),
                mission_margin=MissionMargin(
                    None, None, "declared tolerance", "Adequate Margin",
                    value=1.0),
                applicability=InstrumentApplicability(
                    trajectory="unavailable"),
            )

    registry = MissionAssessmentRegistry()
    registry.register(Provider())
    result = registry.dispatch(_request())

    assert result.status == "green"
    assert result.limitations == ()


def test_fail_closed_assessment_declares_its_empty_instruments_unavailable():
    registry = MissionAssessmentRegistry()
    registry.register(_Provider())
    request = _request(policy_id="missing.policy.v1")

    result = registry.dispatch(request)

    assert result.status == "unavailable"
    assert result.applicability == InstrumentApplicability(
        eta="unavailable",
        delta_v="unavailable",
        trajectory="unavailable",
        forecast="unavailable",
        margin="unavailable",
    )
    assert result.eta is None
    assert result.delta_v is None
    assert result.trajectory == ()
    assert result.forecast == ()


def test_invalid_completeness_is_rejected():
    with pytest.raises(ValueError, match="unsupported assessment completeness"):
        MissionAssessment(
            mission_id="mission-1",
            policy_id="alpha.mission.v1",
            scope=Subject("party", "household-1"),
            as_of=1.0,
            status="green",
            calculation_version="test-v1",
            completeness="halfway",
        )


def test_unavailable_status_cannot_claim_complete_completeness():
    with pytest.raises(ValueError, match="requires unavailable completeness"):
        MissionAssessment(
            mission_id="mission-1",
            policy_id="alpha.mission.v1",
            scope=Subject("party", "household-1"),
            as_of=1.0,
            status="unavailable",
            calculation_version="",
            completeness="complete",
        )


def test_unavailable_constructor_sets_unavailable_completeness():
    result = MissionAssessment.unavailable(_request(), "no provider")

    assert result.completeness == "unavailable"


def test_default_successful_assessment_is_complete():
    result = MissionAssessment(
        mission_id="mission-1",
        policy_id="alpha.mission.v1",
        scope=Subject("party", "household-1"),
        as_of=1.0,
        status="green",
        calculation_version="test-v1",
    )

    assert result.completeness == "complete"


def test_applicability_metadata_does_not_mutate_assessment_state():
    from dataclasses import replace

    request = _request()
    original = _Provider().assess(request)
    changed = replace(
        original,
        eta=None,
        delta_v=None,
        trajectory=(),
        forecast=(),
        mission_margin=None,
        applicability=InstrumentApplicability(
            eta="not_applicable",
            delta_v="not_applicable",
            trajectory="not_applicable",
            forecast="not_applicable",
            margin="not_applicable",
        ),
    )

    presentation_fields = {
        "eta", "delta_v", "trajectory", "forecast", "mission_margin",
        "applicability",
    }
    for field in original.__dataclass_fields__:
        if field not in presentation_fields:
            assert getattr(changed, field) == getattr(original, field)

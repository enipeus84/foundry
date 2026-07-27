"""RFC-005: Core owns assessment shapes and routing, never domain logic."""

import ast
import inspect
import pkgutil
import importlib

import pytest

from foundry.core.mission_assessment import (
    DeltaV, MissionAssessment, MissionAssessmentRegistry,
    MissionAssessmentRequest, MissionPhaseAssessment,
    RecommendationAssessment,
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
            calculation_version="test-v1")


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


def test_extended_assessment_contract_is_backward_compatible_and_domain_neutral():
    phase = MissionPhaseAssessment(
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
        phase=phase, delta_v=delta_v,
        recommendations=(recommendation,))

    assert result.phases == ()
    assert result.flight_status_id == ""
    assert result.forecast_resolution == "month"
    assert phase.unit_or_currency is None
    assert phase.completes_mission is False
    assert delta_v.months is None
    assert recommendation.amount is None
    assert recommendation.status == "available"

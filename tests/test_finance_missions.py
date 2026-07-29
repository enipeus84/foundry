"""RFC-006 Finance mission discovery and canonical ordering."""

from foundry.core.mission_assessment import MissionAssessmentRegistry
from foundry.finance.mission_assessment import POLICY_ID
from foundry.finance.mortgage_assessment import POLICY_ID as MORTGAGE_POLICY_ID
from foundry.finance.missions import register_finance_mission_definitions
from foundry.finance.resilience_assessment import (
    POLICY_ID as RESILIENCE_POLICY_ID,
)


def _registry():
    registry = MissionAssessmentRegistry()
    register_finance_mission_definitions(registry)
    return registry


def test_finance_mission_definitions_have_canonical_order():
    assert [
        definition.label for definition in _registry().definitions()
    ] == [
        "Financial Resilience",
        "Financial Independence",
        "Pension Independence",
        "Mortgage Freedom",
    ]


def test_children_is_outside_the_fixed_finance_hierarchy():
    assert all(
        "children" not in definition.slug
        for definition in _registry().definitions()
    )


def test_only_implemented_missions_declare_assessment_policies():
    definitions = _registry().definitions()

    assert [
        definition.label
        for definition in definitions
        if definition.assessment_policy_id is not None
    ] == [
        "Financial Resilience",
        "Financial Independence",
        "Mortgage Freedom",
    ]
    assert (
        _registry().definition_for_policy(RESILIENCE_POLICY_ID).slug
        == "financial-resilience"
    )
    assert (
        _registry().definition_for_policy(POLICY_ID).slug
        == "financial-independence"
    )
    assert (
        _registry().definition_for_policy(MORTGAGE_POLICY_ID).slug
        == "mortgage-freedom"
    )


def test_mortgage_freedom_keeps_lower_destination_direction_with_policy():
    definition = _registry().definition_for_slug("mortgage-freedom")

    assert definition.destination_direction == "lower_is_better"
    assert definition.assessment_policy_id == MORTGAGE_POLICY_ID

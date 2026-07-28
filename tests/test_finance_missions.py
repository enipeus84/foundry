"""RFC-006 Finance mission discovery and canonical ordering."""

from foundry.core.mission_assessment import MissionAssessmentRegistry
from foundry.finance.mission_assessment import POLICY_ID
from foundry.finance.missions import register_finance_mission_definitions


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


def test_only_financial_independence_declares_an_assessment_policy():
    definitions = _registry().definitions()

    assert [
        definition.label
        for definition in definitions
        if definition.assessment_policy_id is not None
    ] == ["Financial Independence"]
    assert (
        _registry().definition_for_policy(POLICY_ID).slug
        == "financial-independence"
    )


def test_mortgage_freedom_proves_lower_destination_direction_without_policy():
    definition = _registry().definition_for_slug("mortgage-freedom")

    assert definition.destination_direction == "lower_is_better"
    assert definition.assessment_policy_id is None

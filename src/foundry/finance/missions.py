"""Finance mission discovery metadata (RFC-006/RFC-007/RFC-008).

Financial Resilience, Financial Independence and Mortgage Freedom declare
assessment policies. Pension Independence remains honest metadata only: no
targets, thresholds, evidence, or assessment provider is implied.
"""

from foundry.core.mission_assessment import MissionDefinition

from .mission_assessment import POLICY_ID
from .mortgage_assessment import POLICY_ID as MORTGAGE_POLICY_ID
from .resilience_assessment import POLICY_ID as RESILIENCE_POLICY_ID


FINANCE_MISSION_DEFINITIONS: tuple[MissionDefinition, ...] = (
    MissionDefinition(
        slug="financial-resilience",
        label="Financial Resilience",
        order=1,
        destination_direction="higher_is_better",
        definition=(
            "The household can absorb a serious, unexpected disruption "
            "from its own liquid resources — 18 months of essential outflow "
            "held in reserve — without being forced into a damaging "
            "financial decision."
        ),
        assessment_policy_id=RESILIENCE_POLICY_ID,
    ),
    MissionDefinition(
        slug="financial-independence",
        label="Financial Independence",
        order=2,
        destination_direction="higher_is_better",
        definition=(
            "The ability to choose whether you work because your accessible "
            "assets can indefinitely support your desired lifestyle."
        ),
        assessment_policy_id=POLICY_ID,
    ),
    MissionDefinition(
        slug="pension-independence",
        label="Pension Independence",
        order=3,
        destination_direction="higher_is_better",
    ),
    MissionDefinition(
        slug="mortgage-freedom",
        label="Mortgage Freedom",
        order=4,
        destination_direction="lower_is_better",
        definition=(
            "The primary residence mortgage is fully repaid while "
            "household resilience remains protected."
        ),
        assessment_policy_id=MORTGAGE_POLICY_ID,
    ),
)


def register_finance_mission_definitions(registry) -> None:
    """Register Finance definitions without registering any provider."""
    for definition in FINANCE_MISSION_DEFINITIONS:
        registry.register_definition(definition)

"""Application queries for the Pension Independence commissioning slice.

The service is an adapter-facing composition root.  It does not calculate a
mission result itself: Finance metric providers and the canonical Pension
Independence assessor remain the only owners of those semantics.
"""

from __future__ import annotations

from datetime import datetime, timezone
import time
from typing import Any

from foundry.core.entities import EntityProjection
from foundry.core.metrics import MetricRegistry, MetricResult
from foundry.core.mission_assessment import MissionAssessment, MissionAssessmentRequest
from foundry.core.scope import Subject
from foundry.eventlog import EventLog
from foundry.finance.entities import FinanceEntityProjection
from foundry.finance.metrics import FinanceMetricProvider
from foundry.finance.pension_assessment import (
    POLICY_ID,
    PensionIndependenceAssessor,
)
from foundry.finance.pension_evidence import PensionEvidenceProjection
from foundry.finance.pension_metrics import FinancePensionMetricProvider
from foundry.finance.pension_projection import PensionProviderProjectionProjection

from .mission_assumptions import MissionAssumptionService


class PensionMissionQueryError(LookupError):
    """The requested Pension Independence Mission is not visible or unique."""


def _iso(timestamp: float | None) -> str | None:
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _timestamp(value: str | None) -> float:
    if value is None:
        return time.time()
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise PensionMissionQueryError("as_of must be a valid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise PensionMissionQueryError("as_of must include a timezone")
    return parsed.timestamp()


def _metric(result: MetricResult | None) -> dict[str, Any] | None:
    if result is None:
        return None
    return {
        "metric_id": result.metric_id,
        "value": result.value,
        "unit_or_currency": result.unit_or_currency,
        "status": result.status,
        "as_of": _iso(result.as_of),
        "generated_at": _iso(result.generated_at),
        "calculation_version": result.calculation_version,
        "input_references": list(result.input_references),
        "evidence_references": list(result.evidence_references),
        "assumption_references": list(result.assumption_references),
        "limitations": list(result.limitations),
    }


class PensionMissionQueryService:
    """Household-scoped read facade over canonical Pension Mission machinery."""

    def __init__(self, log: EventLog, household_id: str):
        self.log = log
        self.household_id = household_id

    def _composition(self):
        core = EntityProjection(self.log)
        finance = FinanceEntityProjection(self.log)
        evidence = PensionEvidenceProjection(self.log)
        metrics = MetricRegistry()
        metrics.register(FinanceMetricProvider(finance, core))
        metrics.register(FinancePensionMetricProvider(finance, core, evidence))
        assessor = PensionIndependenceAssessor(
            metrics,
            finance,
            core,
            evidence,
            provider_projections=PensionProviderProjectionProjection(self.log),
        )
        return core, finance, assessor

    def _mission(self, core: EntityProjection, mission_id: str | None):
        candidates = tuple(
            mission for mission in core.missions.values()
            if mission.household_id == self.household_id
            and mission.status == "active"
            and mission.assessment_policy_id == POLICY_ID
        )
        if mission_id is not None:
            mission = core.missions.get(mission_id)
            if mission not in candidates:
                raise PensionMissionQueryError("Pension Independence Mission not found")
            return mission
        if not candidates:
            raise PensionMissionQueryError("Pension Independence Mission not found")
        if len(candidates) != 1:
            raise PensionMissionQueryError(
                "multiple active Pension Independence Missions require an explicit mission_id")
        return candidates[0]

    @staticmethod
    def _target(assessment: MissionAssessment) -> MetricResult | None:
        return next((
            item.result for item in assessment.telemetry
            if item.result.metric_id == "finance.retirement_wealth_required"
        ), None)

    def evaluate(self, mission_id: str | None = None,
                 as_of: str | None = None) -> dict[str, Any]:
        assessed_at = _timestamp(as_of)
        core, finance, assessor = self._composition()
        mission = self._mission(core, mission_id)
        request = MissionAssessmentRequest(
            mission.id, POLICY_ID, Subject("party", self.household_id), assessed_at)
        assessment = assessor.assess(request)
        readiness = MissionAssumptionService(self.log).readiness(
            mission.id, self.household_id)
        assumption_set = finance.assumption_sets.get(mission.assumption_set_id or "")
        target = self._target(assessment)
        current = assessment.current_value
        gap = None
        if current is not None and current.value is not None \
                and target is not None and target.value is not None:
            gap = float(target.value) - float(current.value)
        blockers = (list(assessment.limitations)
                    if assessment.status == "unavailable"
                    else list(readiness.blockers))
        blockers = list(dict.fromkeys(blockers))
        return {
            "mission": {
                "id": mission.id,
                "name": mission.name,
                "lifecycle_status": mission.status,
                "policy_id": mission.assessment_policy_id,
                "subject": {"kind": "party", "id": self.household_id},
                "target_metric": mission.target_metric,
            },
            "evaluable": assessment.status != "unavailable",
            "status": assessment.trajectory_state or assessment.status,
            "assessment_status": assessment.status,
            "mission_complete": assessment.mission_complete,
            "current_relevant_value": _metric(current),
            "target": _metric(target),
            "gap": ({
                "value": gap,
                "unit_or_currency": target.unit_or_currency if target else None,
                "meaning": "target minus current; positive is a shortfall",
            } if gap is not None else None),
            "horizon": {
                "planning_at": _iso(assessment.forecast[-1].at) if assessment.forecast else None,
                "estimated_independence_at": _iso(assessment.eta),
                "forecast_resolution": assessment.forecast_resolution,
            },
            "assumptions_used": ({
                "id": assumption_set.id,
                "name": assumption_set.name,
                "version": assumption_set.version,
                "status": assumption_set.status,
                "values": dict(assumption_set.assumptions),
                "provenance": list(assumption_set.provenance),
            } if assumption_set is not None else None),
            "provenance": {
                "assessment_as_of": _iso(assessment.as_of),
                "calculation_version": assessment.calculation_version,
                "input_references": list(assessment.input_references),
                "evidence_references": list(assessment.evidence_references),
                "assumption_references": list(assessment.assumption_references),
            },
            "blockers": blockers,
            "limitations": list(assessment.limitations) if assessment.status != "unavailable" else [],
        }

    def inspect(self, mission_id: str | None = None,
                as_of: str | None = None) -> dict[str, Any]:
        """Return the same canonical evaluation, including exact blockers."""
        return self.evaluate(mission_id, as_of)

    def current_value(self, mission_id: str | None = None,
                      as_of: str | None = None) -> dict[str, Any]:
        """Return an aggregated canonical value; never expose observation history."""
        result = self.evaluate(mission_id, as_of)
        return {
            "mission_id": result["mission"]["id"],
            "subject": result["mission"]["subject"],
            "current_pension_value": result["current_relevant_value"],
            "evaluable": result["evaluable"],
            "blockers": result["blockers"],
        }

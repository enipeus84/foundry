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
from foundry.core.mission_assessment import MissionAssessmentRegistry
from foundry.core.mission_targets import MissionTargetProjection
from foundry.core.scope import Subject
from foundry.eventlog import EventLog
from foundry.finance.entities import FinanceEntityProjection
from foundry.finance.metrics import FinanceMetricProvider
from foundry.finance.pension_assessment import (
    DAY, POLICY_ID, PensionIndependenceInputs,
    PensionIndependenceAssessor,
)
from foundry.finance.pension_evidence import PensionEvidenceProjection
from foundry.finance.pension_metrics import FinancePensionMetricProvider
from foundry.finance.pension_projection import PensionProviderProjectionProjection
from foundry.finance.mission_targets import FinanceTargetMetricResolver
from foundry.finance.missions import register_finance_mission_definitions

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
        definitions = MissionAssessmentRegistry()
        register_finance_mission_definitions(definitions)
        targets = MissionTargetProjection(
            self.log, core, definitions, FinanceTargetMetricResolver())
        return core, finance, assessor, targets

    def _mission(self, core: EntityProjection, targets: MissionTargetProjection,
                 mission_id: str | None, assessed_at: float):
        """Resolve household scope from an in-force Mission Target.

        A Mission is programme metadata, not a household-owned entity.  The
        target is the canonical household binding; ``Mission.household_id`` is
        retained only to replay pre-RFC-016 history and must not gate reads.
        """
        candidates = tuple(
            (mission, target) for mission in core.missions.values()
            if mission.status == "active"
            and mission.assessment_policy_id == POLICY_ID
            and (target := targets.in_force(mission.id, assessed_at)) is not None
            and target.household_id == self.household_id
        )
        if mission_id is not None:
            candidate = next((item for item in candidates if item[0].id == mission_id), None)
            if candidate is None:
                raise PensionMissionQueryError("Pension Independence Mission is not authorised for this household")
            return self._require_subject(candidate)
        if not candidates:
            missions = tuple(mission for mission in core.missions.values()
                             if mission.assessment_policy_id == POLICY_ID)
            if not missions:
                raise PensionMissionQueryError("Pension Independence Mission is not declared")
            if any(mission.id in targets.conflicts for mission in missions):
                raise PensionMissionQueryError(
                    "Pension Independence Mission has ambiguous canonical Mission Target state")
            if any(targets.in_force(mission.id, assessed_at) is not None for mission in missions):
                raise PensionMissionQueryError(
                    "Pension Independence Mission is not authorised for this household")
            raise PensionMissionQueryError(
                "Pension Independence Mission has no active canonical Mission Target")
        if len(candidates) != 1:
            raise PensionMissionQueryError(
                "multiple active Pension Independence Missions require an explicit mission_id")
        return self._require_subject(candidates[0])

    @staticmethod
    def _require_subject(candidate):
        """Legacy null-target subjects are not a household-scope shorthand."""
        if candidate[1].subject_id is None:
            raise PensionMissionQueryError(
                "Pension Independence Mission Target has no canonical subject")
        return candidate

    @staticmethod
    def _target(assessment: MissionAssessment) -> MetricResult | None:
        return next((
            item.result for item in assessment.telemetry
            if item.result.metric_id == "finance.retirement_wealth_required"
        ), None)

    def evaluate(self, mission_id: str | None = None,
                 as_of: str | None = None) -> dict[str, Any]:
        assessed_at = _timestamp(as_of)
        core, finance, assessor, targets = self._composition()
        mission, target_binding = self._mission(core, targets, mission_id, assessed_at)
        request = MissionAssessmentRequest(
            mission.id, POLICY_ID, Subject("party", target_binding.subject_id), assessed_at)
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
                "subject": {"kind": "party", "id": target_binding.subject_id},
                "authorising_household": self.household_id,
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

    def explain_planning_point(self, mission_id: str | None = None,
                               as_of: str | None = None) -> dict[str, Any]:
        """Explain the assessor-owned planning-point compatibility decision.

        This deliberately serializes only the participant timing facts and
        provider illustrations that can affect this one Mission calculation.
        """
        assessed_at = _timestamp(as_of)
        core, finance, assessor, targets = self._composition()
        mission, target_binding = self._mission(core, targets, mission_id, assessed_at)
        request = MissionAssessmentRequest(
            mission.id, POLICY_ID, Subject("party", target_binding.subject_id), assessed_at)
        assessment = assessor.assess(request)
        members, participant_error = assessor._participants(request)
        assumption_set = finance.assumption_sets.get(mission.assumption_set_id or "")
        input_error = participant_error
        inputs = None
        if input_error is None:
            if assumption_set is None or assumption_set.status != "active":
                input_error = "active pension Assumption Set not found"
            else:
                try:
                    inputs = PensionIndependenceInputs.from_assumption_set(assumption_set)
                except (TypeError, ValueError) as exc:
                    input_error = str(exc)

        detail = None
        if input_error is None:
            detail = assessor._planning_point_detail(members, assessed_at, inputs)
            input_error = detail.error
        participants = [] if detail is None else [{
            "participant_id": item.participant_id,
            "date_of_birth": item.date_of_birth,
            "current_age": item.current_age,
            "state_pension_age": item.state_pension_age,
            "state_pension_age_evidence_reference": item.state_pension_evidence_event_id,
            "derived_horizon_years": item.horizon_years,
        } for item in detail.participants]
        planning_at = None if detail is None else detail.planning_at

        provider_records = []
        if planning_at is not None:
            accounts, _ = assessor._projection_accounts(
                {member.id for member in members}, assessed_at, inputs)
            account_ids = assessor._provider_evaluation_ids(
                accounts, {member.id for member in members})
            for account_id in account_ids:
                if not assessor._requires_provider_projection(account_id):
                    continue
                record = assessor.provider_projections.latest(account_id, assessed_at)
                item = {
                    "resource_id": account_id,
                    "projection_authority": "provider_managed",
                    "latest_provider_projection": None,
                    "record_planning_at": None,
                    "delta_seconds": None,
                    "absolute_delta_seconds": None,
                    "compatibility_result": None,
                }
                if record is not None:
                    record_planning_at, record_error = assessor._provider_record_planning_at(
                        account_id, record, assessed_at)
                    delta = (record_planning_at - planning_at
                             if record_planning_at is not None else None)
                    item.update({
                        "latest_provider_projection": {
                            "provider": record.provider,
                            "observed_at": _iso(record.observed_at),
                            "retirement_age": record.retirement_age,
                            "retirement_at": _iso(record.retirement_at),
                            "evidence_reference": record.event_id,
                        },
                        "record_planning_at": _iso(record_planning_at),
                        "delta_seconds": delta,
                        "absolute_delta_seconds": abs(delta) if delta is not None else None,
                        "compatibility_result": (
                            abs(delta) <= DAY if delta is not None else False),
                        "resolution_error": record_error,
                    })
                provider_records.append(item)

        compatibility = [item["compatibility_result"] for item in provider_records]
        return {
            "mission": {
                "id": mission.id,
                "policy_id": mission.assessment_policy_id,
                "subject": {"kind": "party", "id": target_binding.subject_id},
            },
            "assessment": {
                "status": assessment.status,
                "blocker": next(iter(assessment.limitations), None)
                if assessment.status == "unavailable" else None,
            },
            "planning_point": {
                "selection_rule": (
                    "explicit planning_age" if inputs is not None and inputs.planning_age is not None
                    else "latest active adult participant State Pension age"),
                "planning_at": _iso(planning_at),
                "participants": participants,
                "driving_participant_ids": [] if detail is None else list(detail.driving_participant_ids),
                "calculation_error": input_error,
            },
            "provider_projections": provider_records,
            "compatibility": {
                "tolerance_seconds": DAY,
                "tolerance": "P1D",
                "result": all(compatibility) if compatibility else None,
            },
        }

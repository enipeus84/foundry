"""Application read for the Mortgage Freedom commissioning slice.

This service is an adapter-facing composition root.  It owns no Mission
semantics: ``MortgageFreedomAssessor`` remains the only place completeness,
blockers, equity, LTV, forecast and margin are decided.  Everything here
resolves scope, invokes that assessor once, and serializes what it returned.
"""

from __future__ import annotations

from typing import Any

from foundry.core.entities import EntityProjection
from foundry.core.metrics import MetricRegistry, MetricResult
from foundry.core.mission_assessment import (
    MissionAssessment, MissionAssessmentRegistry, MissionAssessmentRequest,
)
from foundry.core.mission_targets import MissionTargetProjection
from foundry.core.scope import Subject
from foundry.eventlog import EventLog
from foundry.finance.entities import FinanceEntityProjection
from foundry.finance.metrics import FinanceMetricProvider
from foundry.finance.mission_targets import FinanceTargetMetricResolver
from foundry.finance.missions import register_finance_mission_definitions
from foundry.finance.mortgage_assessment import POLICY_ID, MortgageFreedomAssessor
from foundry.finance.mortgage_evidence import MortgageEvidenceProjection
from foundry.finance.resilience_evidence import ResilienceEvidenceProjection
from foundry.finance.resilience_metrics import FinanceResilienceMetricProvider

from .mission_serialization import as_of_timestamp, iso, metric


class MortgageMissionQueryError(LookupError):
    """The requested Mortgage Freedom read cannot be served."""


#: Present-state telemetry, separated from forecast output for the reader.
_CURRENT_POSITION_METRICS = (
    "finance.mortgage_balance",
    "finance.property_valuation",
    "finance.property_current_equity",
    "finance.mortgage_ltv",
    "finance.mortgage_principal_repaid",
    "finance.mortgage_interest_rate",
    "finance.mortgage_payment",
    "finance.mortgage_initial_advance",
    "finance.property_purchase_price",
    "finance.property_valuation_movement",
    "finance.mortgage_initial_deposit",
    "finance.property_acquisition_costs",
)

_FORECAST_METRICS = (
    "finance.mortgage_projected_interest",
    "finance.mortgage_fixed_protection",
)


class MortgageMissionQueryService:
    """Household-scoped read facade over the canonical Mortgage assessor.

    The household is always the authenticated principal's own.  A caller
    supplied ``mission_id`` may narrow which Mission is read, never which
    household is assessed.
    """

    def __init__(self, log: EventLog, household_id: str):
        self.log = log
        self.household_id = household_id

    # ----------------------------------------------------------- composition

    def _composition(self):
        core = EntityProjection(self.log)
        finance = FinanceEntityProjection(self.log)
        metrics = MetricRegistry()
        metrics.register(FinanceMetricProvider(finance, core))
        metrics.register(FinanceResilienceMetricProvider(
            finance, core, ResilienceEvidenceProjection(self.log)))
        assessor = MortgageFreedomAssessor(
            finance, core, metrics, MortgageEvidenceProjection(self.log))
        definitions = MissionAssessmentRegistry()
        register_finance_mission_definitions(definitions)
        targets = MissionTargetProjection(
            self.log, core, definitions, FinanceTargetMetricResolver())
        return core, finance, assessor, targets

    # ----------------------------------------------------------- scope

    def _visible_missions(self, core: EntityProjection,
                          targets: MissionTargetProjection, assessed_at: float):
        """Missions this household is canonically entitled to read.

        A Mission is programme metadata.  Entitlement comes from an in-force
        Mission Target bound to this household, or from the Mission's own
        canonical household binding when no Target has been commissioned yet.
        Neither path lets a caller name another household's Mission.
        """
        visible = []
        for mission in core.missions.values():
            if mission.assessment_policy_id != POLICY_ID:
                continue
            target = targets.in_force(mission.id, assessed_at)
            if target is not None and target.household_id == self.household_id:
                visible.append((mission, target))
            elif target is None and mission.household_id == self.household_id:
                visible.append((mission, None))
        return visible

    def _resolve(self, core: EntityProjection, targets: MissionTargetProjection,
                 mission_id: str | None, assessed_at: float):
        """Return ``(mission, target, mission_state)``; absence is not an error."""
        visible = self._visible_missions(core, targets, assessed_at)
        active = [item for item in visible if item[0].status == "active"]
        if mission_id is not None:
            candidate = next(
                (item for item in visible if item[0].id == mission_id), None)
            if candidate is None:
                raise MortgageMissionQueryError(
                    "Mortgage Freedom Mission is not authorised for this household")
            return candidate[0], candidate[1], "declared"
        if not active:
            if visible:
                return None, None, "closed"
            declared = any(mission.assessment_policy_id == POLICY_ID
                           for mission in core.missions.values())
            return None, None, (
                "not_authorised_for_household" if declared else "not_declared")
        if len(active) != 1:
            raise MortgageMissionQueryError(
                "multiple active Mortgage Freedom Missions require an explicit mission_id")
        return active[0][0], active[0][1], "declared"

    # ----------------------------------------------------------- serialization

    @staticmethod
    def _blockers_and_limitations(
            assessment: MissionAssessment) -> tuple[list[str], list[str]]:
        """Preserve the assessor's own blocking/non-blocking distinction."""
        if assessment.completeness == "complete":
            return [], list(assessment.limitations)
        if assessment.completeness == "unavailable":
            return list(assessment.limitations), []
        blocker = assessment.confidence_basis or next(
            iter(assessment.limitations), "")
        blocking = [blocker] if blocker else []
        return blocking, [note for note in assessment.limitations if note != blocker]

    @staticmethod
    def _telemetry(assessment: MissionAssessment) -> dict[str, MetricResult]:
        return {item.result.metric_id: item.result for item in assessment.telemetry}

    def _mission_absent(self, mission_state: str, assessed_at: float) -> dict[str, Any]:
        """Report a canonically absent Mission without manufacturing one."""
        blocker = (
            "Mortgage Freedom Mission is not declared"
            if mission_state == "not_declared"
            else "Mortgage Freedom Mission is closed"
            if mission_state == "closed"
            else "Mortgage Freedom Mission is not authorised for this household")
        return {
            "policy_id": POLICY_ID,
            "subject": {"kind": "party", "id": self.household_id},
            "assessed_as_of": iso(assessed_at),
            "mission": None,
            "mission_state": mission_state,
            "target": {"state": "not_applicable",
                       "reason": "no Mission to bind a Mission Target to"},
            "assumption_set": {"state": "not_applicable",
                               "reason": "no Mission to bind an Assumption Set to"},
            "evaluable": False,
            "completeness": "unavailable",
            "status": None,
            "assessment_status": None,
            "mission_complete": False,
            "confidence": None,
            "current_position": None,
            "forecast": None,
            "mission_margin": None,
            "delta_v": None,
            "current_milestone": None,
            "provenance": None,
            "blockers": [blocker],
            "limitations": [],
        }

    def _target_state(self, mission, target) -> dict[str, Any]:
        if target is None:
            return {
                "state": "absent",
                "reason": "no in-force canonical Mission Target is declared for this Mission",
                "mission_destination": {
                    "target_metric": mission.target_metric,
                    "target_value": mission.target_value,
                    "target_date": iso(mission.target_date),
                },
            }
        return {
            "state": "in_force",
            "id": target.id,
            "metric_id": target.metric_id,
            "subject_id": target.subject_id,
            "destination": {"value": target.destination.value,
                            "unit_or_currency": target.destination.unit_or_currency},
            "destination_direction": target.destination_direction,
            "horizon_kind": target.horizon_kind,
            "horizon_at": iso(target.horizon_at),
            "effective_from": iso(target.effective_from),
            "basis": target.basis,
            "provenance": list(target.provenance),
        }

    def _assumption_state(self, finance: FinanceEntityProjection,
                          mission) -> dict[str, Any]:
        if not mission.assumption_set_id:
            return {"state": "absent",
                    "reason": "Mission declares no Assumption Set"}
        assumption_set = finance.assumption_sets.get(mission.assumption_set_id)
        if assumption_set is None:
            return {"state": "absent", "id": mission.assumption_set_id,
                    "reason": "declared Assumption Set does not exist canonically"}
        if assumption_set.status != "active":
            return {"state": "inactive", "id": assumption_set.id,
                    "status": assumption_set.status,
                    "reason": "declared Assumption Set is not active"}
        return {
            "state": "active",
            "id": assumption_set.id,
            "name": assumption_set.name,
            "version": assumption_set.version,
            "status": assumption_set.status,
            "values": dict(assumption_set.assumptions),
            "provenance": list(assumption_set.provenance),
        }

    def _current_position(self, assessment: MissionAssessment) -> dict[str, Any] | None:
        telemetry = self._telemetry(assessment)
        available = {name: metric(telemetry[name])
                     for name in _CURRENT_POSITION_METRICS if name in telemetry}
        current = metric(assessment.current_value)
        if not available and current is None:
            return None
        return {"mortgage_balance": current, **available}

    def _forecast(self, assessment: MissionAssessment) -> dict[str, Any] | None:
        telemetry = self._telemetry(assessment)
        available = {name: metric(telemetry[name])
                     for name in _FORECAST_METRICS if name in telemetry}
        if not assessment.forecast and assessment.eta is None and not available:
            return None
        return {
            "estimated_payoff_at": iso(assessment.eta),
            "forecast_resolution": assessment.forecast_resolution,
            "applicability": {
                "eta": assessment.applicability.eta,
                "delta_v": assessment.applicability.delta_v,
                "forecast": assessment.applicability.forecast,
                "trajectory": assessment.applicability.trajectory,
                "margin": assessment.applicability.margin,
            },
            "points": [{"at": iso(point.at), "low": point.low,
                        "base": point.base, "high": point.high}
                       for point in assessment.forecast],
            **available,
        }

    # ----------------------------------------------------------- public read

    def inspect(self, mission_id: str | None = None,
                as_of: str | None = None) -> dict[str, Any]:
        """Return the canonical Mortgage Freedom assessment; never mutate state."""
        try:
            assessed_at = as_of_timestamp(as_of)
        except ValueError as exc:
            raise MortgageMissionQueryError(str(exc)) from exc
        core, finance, assessor, targets = self._composition()
        mission, target, mission_state = self._resolve(
            core, targets, mission_id, assessed_at)
        if mission is None:
            return self._mission_absent(mission_state, assessed_at)

        request = MissionAssessmentRequest(
            mission.id, POLICY_ID, Subject("party", self.household_id), assessed_at)
        assessment = assessor.assess(request)
        blocking, non_blocking = self._blockers_and_limitations(assessment)
        margin = assessment.mission_margin
        delta_v = assessment.delta_v
        milestone = assessment.current_milestone
        return {
            "policy_id": POLICY_ID,
            "subject": {"kind": "party", "id": self.household_id},
            "assessed_as_of": iso(assessed_at),
            "mission": {
                "id": mission.id,
                "name": mission.name,
                "lifecycle_status": mission.status,
                "policy_id": mission.assessment_policy_id,
                "target_metric": mission.target_metric,
                "authorising_household": self.household_id,
            },
            "mission_state": mission_state,
            "target": self._target_state(mission, target),
            "assumption_set": self._assumption_state(finance, mission),
            "evaluable": assessment.completeness == "complete",
            "completeness": assessment.completeness,
            "status": assessment.trajectory_state or assessment.status,
            "assessment_status": assessment.status,
            "mission_complete": assessment.mission_complete,
            "flight_status": {"id": assessment.flight_status_id,
                              "label": assessment.flight_status_label},
            "confidence": ({"state": assessment.confidence.state,
                            "basis": assessment.confidence.basis}
                           if assessment.confidence is not None else None),
            "contractual_maturity_at": iso(mission.target_date),
            "current_position": self._current_position(assessment),
            "forecast": self._forecast(assessment),
            "mission_margin": ({
                "state": margin.state, "label": margin.label,
                "value": margin.value, "unit_or_currency": margin.unit_or_currency,
                "pace_percent": margin.pace_percent,
                "schedule_buffer_days": margin.schedule_buffer_days,
                "description": margin.description,
            } if margin is not None else None),
            "delta_v": ({
                "days": delta_v.days, "months": delta_v.months,
                "direction": delta_v.direction, "resolution": delta_v.resolution,
                "period_label": delta_v.period_label,
                "lookback_days": delta_v.lookback_days,
                "reference_start_at": iso(delta_v.reference_start_at),
                "reference_destination_at": iso(delta_v.reference_destination_at),
                "description": delta_v.description,
            } if delta_v is not None else None),
            "current_milestone": ({
                "id": milestone.id, "label": milestone.label,
                "completion": milestone.completion,
                "is_complete": milestone.is_complete,
                "completes_mission": milestone.completes_mission,
                "estimated_at": iso(milestone.estimated_at),
            } if milestone is not None else None),
            "provenance": {
                "assessment_as_of": iso(assessment.as_of),
                "calculation_version": assessment.calculation_version,
                "input_references": list(assessment.input_references),
                "evidence_references": list(assessment.evidence_references),
                "assumption_references": list(assessment.assumption_references),
            },
            "blockers": list(dict.fromkeys(blocking)),
            "limitations": non_blocking if assessment.completeness != "unavailable" else [],
        }

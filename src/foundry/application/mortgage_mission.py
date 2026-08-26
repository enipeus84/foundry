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
from foundry.finance.mortgage_evidence import (
    EVIDENCE_FIELDS, MortgageEvidence, MortgageEvidenceProjection,
)
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

#: Mirrors the confidence gate MortgageFreedomAssessor applies to required
#: evidence. It is reported, never enforced: this read blocks nothing.
ASSESSOR_CONFIDENCE_FLOOR = .5

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

    # ----------------------------------------------------------- provenance reads

    def _evidence_scope(self, assessor: MortgageFreedomAssessor,
                        obligation_id: str | None):
        """Resolve the household's one mortgage obligation, canonically.

        Scope is deliberately delegated to the assessor's own resolver rather
        than reimplemented here: ``MortgageFreedomAssessor`` remains the only
        place a household's mortgage is decided.  Nothing about the assessor
        is modified; this is a read of its scoping result.
        """
        if self.household_id not in assessor.core.parties:
            return None, "household is not canonically declared"
        obligation, _asset, _refs, reason = assessor._scoped_mortgage(
            self.household_id)
        if obligation is None:
            return None, reason
        if obligation_id is not None and obligation_id != obligation.id:
            # A caller may narrow to the household's own obligation; naming
            # another household's obligation is never a read of it.
            return None, "obligation is not authorised for this household"
        return obligation, ""

    @staticmethod
    def _evidence_record(record: MortgageEvidence, *, is_current: bool) -> dict[str, Any]:
        return {
            "field": record.field,
            "value": record.value,
            "unit_or_currency": record.unit_or_currency,
            "effective_at": iso(record.effective_at),
            "confidence": record.confidence,
            "source": record.source,
            "lineage": record.lineage,
            "event_id": record.event_id,
            "is_current": is_current,
            "below_assessor_confidence_floor": (
                record.confidence < ASSESSOR_CONFIDENCE_FLOOR),
        }

    def evidence_history(self, obligation_id: str | None = None,
                         as_of: str | None = None,
                         field: str | None = None) -> dict[str, Any]:
        """Return canonical mortgage evidence and how the assessor resolves it.

        This read never records, repairs or reinterprets evidence.  Absent or
        malformed evidence is reported as exactly that.
        """
        try:
            read_at = as_of_timestamp(as_of)
        except ValueError as exc:
            raise MortgageMissionQueryError(str(exc)) from exc
        if field is not None and field not in EVIDENCE_FIELDS:
            raise MortgageMissionQueryError("unsupported mortgage evidence field")
        core, _finance, assessor, _targets = self._composition()
        evidence = assessor.evidence
        obligation, reason = self._evidence_scope(assessor, obligation_id)
        base = {
            "subject": {"kind": "party", "id": self.household_id},
            "read_as_of": iso(read_at),
            "obligation_id": obligation_id,
        }
        if obligation is None:
            return {**base, "obligation_state": "unresolved", "reason": reason,
                    "records": [], "record_count": 0, "fields": {},
                    "required_field_resolution": None,
                    "malformed_envelopes": None}

        visible = evidence.for_obligation(obligation.id, read_at)
        current_event_ids = {
            resolved.event_id for resolved in (
                evidence.latest(obligation.id, name, read_at)
                for name in {record.field for record in visible})
            if resolved is not None}
        selected = tuple(record for record in visible
                         if field is None or record.field == field)
        records = [self._evidence_record(
                       record, is_current=record.event_id in current_event_ids)
                   for record in sorted(
                       selected, key=lambda item: (item.field, item.effective_at))]

        by_field: dict[str, Any] = {}
        for name in sorted({record.field for record in selected}):
            resolved = evidence.latest(obligation.id, name, read_at)
            by_field[name] = {
                "observation_count": sum(
                    1 for record in selected if record.field == name),
                "current": (self._evidence_record(resolved, is_current=True)
                            if resolved is not None else None),
            }

        # Resolved with the assessor's own accessor, so this answers whether
        # the assessor can see the evidence, not merely whether it was written.
        required = {
            name: evidence.latest(obligation.id, name, read_at)
            for name in sorted(MortgageFreedomAssessor._REQUIRED_FIELDS)}
        missing = sorted(name for name, record in required.items() if record is None)
        low_confidence = sorted(
            name for name, record in required.items()
            if record is not None and record.confidence < ASSESSOR_CONFIDENCE_FLOOR)
        return {
            **base,
            "obligation_id": obligation.id,
            "obligation_state": "resolved",
            "records": records,
            "record_count": len(records),
            "fields": by_field,
            "required_field_resolution": {
                "required_count": len(MortgageFreedomAssessor._REQUIRED_FIELDS),
                "resolved": sorted(name for name, record in required.items()
                                   if record is not None),
                "resolved_count": sum(
                    1 for record in required.values() if record is not None),
                "missing": missing,
                "below_confidence_floor": low_confidence,
                "confidence_floor": ASSESSOR_CONFIDENCE_FLOOR,
                "assessor_resolves_all_required": not missing and not low_confidence,
            },
            "malformed_envelopes": {
                "affects_this_obligation": evidence.has_invalid_for(
                    obligation.id, read_at),
                "event_ids": list(evidence.invalid_event_ids),
            },
        }

    def _target_declaration(self, event_id: str) -> dict[str, Any] | None:
        """Return who declared a target and when, straight from the log."""
        event = self.log.get(event_id)
        if event is None:
            return None
        return {"event_id": event_id, "kind": event.get("kind"),
                "actor": event.get("actor"), "recorded_at": iso(event.get("ts"))}

    def _target_entry(self, target, targets: MissionTargetProjection,
                      in_force_id: str | None, read_at: float) -> dict[str, Any]:
        successors = sorted(
            other.id for other in targets.targets.values()
            if other.supersedes == target.id)
        if target.id == in_force_id:
            state = "in_force"
        elif target.closed_at is not None:
            state = "withdrawn"
        elif successors:
            state = "superseded"
        elif target.effective_from > read_at:
            state = "not_yet_effective"
        else:
            state = "not_in_force"
        declaration_event_id = target.provenance[0] if target.provenance else None
        return {
            "id": target.id,
            "state": state,
            "metric_id": target.metric_id,
            "household_id": target.household_id,
            "subject_id": target.subject_id,
            "target_value": target.destination.value,
            "unit_or_currency": target.destination.unit_or_currency,
            "destination_direction": target.destination_direction,
            "horizon_kind": target.horizon_kind,
            "horizon_at": iso(target.horizon_at),
            "effective_from": iso(target.effective_from),
            "declared_at": iso(target.declared_at),
            "withdrawn_at": iso(target.closed_at),
            "basis": target.basis,
            "supersedes": target.supersedes,
            "superseded_by": successors,
            "declaration_event_id": declaration_event_id,
            "declaration": (self._target_declaration(declaration_event_id)
                            if declaration_event_id else None),
            "provenance": list(target.provenance),
            "history": list(target.history),
        }

    def target_history(self, mission_id: str | None = None,
                       as_of: str | None = None) -> dict[str, Any]:
        """Return every Mission Target declared for this Mission, and its state.

        This read never declares, withdraws or supersedes a Mission Target.
        """
        try:
            read_at = as_of_timestamp(as_of)
        except ValueError as exc:
            raise MortgageMissionQueryError(str(exc)) from exc
        core, _finance, _assessor, targets = self._composition()
        mission, _target, mission_state = self._resolve(
            core, targets, mission_id, read_at)
        base = {
            "subject": {"kind": "party", "id": self.household_id},
            "read_as_of": iso(read_at),
            "policy_id": POLICY_ID,
        }
        if mission is None:
            return {**base, "mission": None, "mission_state": mission_state,
                    "targets": [], "target_count": 0, "in_force_target_id": None,
                    "mission_destination_metadata": None, "conflicts": []}

        in_force = targets.in_force(mission.id, read_at)
        in_force_id = in_force.id if in_force is not None else None
        declared = sorted(
            (item for item in targets.targets.values()
             if item.mission_id == mission.id),
            key=lambda item: (item.effective_from, item.declared_at))
        return {
            **base,
            "mission": {
                "id": mission.id, "name": mission.name,
                "lifecycle_status": mission.status,
                "policy_id": mission.assessment_policy_id,
                "target_metric": mission.target_metric,
                "authorising_household": self.household_id,
            },
            "mission_state": mission_state,
            "in_force_target_id": in_force_id,
            "targets": [self._target_entry(item, targets, in_force_id, read_at)
                        for item in declared],
            "target_count": len(declared),
            # The Mission entity's own destination fields. The canonical
            # assessor gates on these, not on the RFC-016 Mission Target, so
            # a divergence between the two is visible in one read.
            "mission_destination_metadata": {
                "target_value": mission.target_value,
                "target_date": iso(mission.target_date),
                "assumption_set_id": mission.assumption_set_id,
                "provenance": list(mission.provenance),
            },
            "conflicts": [
                {"mission_id": key, "target_ids": list(value)}
                for key, value in sorted(targets.conflicts.items())],
        }

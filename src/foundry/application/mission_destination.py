"""Governed amendment of a Mission's target metric.

The service owns the proposal/execute receipt only.  The successful command
remains one canonical ``core.mission.updated`` event; it never changes a
Mission Target or Finance assessment semantics.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import time
from typing import Any

from foundry.core import grammar, vocab
from foundry.core.entities import EntityProjection, Mission
from foundry.core.mission_assessment import MissionAssessmentRegistry
from foundry.core.mission_targets import MissionTargetProjection
from foundry.core.principal_authority import PrincipalHouseholdAuthority
from foundry.eventlog import EventLog
from foundry.finance.mission_targets import FinanceTargetMetricResolver
from foundry.finance.missions import register_finance_mission_definitions


class MissionDestinationDenied(PermissionError):
    """A Mission target-metric amendment is not currently admissible."""


def _digest(value: dict[str, Any]) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MissionDestinationDenied(f"{field} is required")
    return value.strip()


@dataclass(frozen=True)
class MissionDestinationService:
    """Receipt-bound, household-authorised Mission metric amendments."""

    log: EventLog
    principal: str
    household_id: str
    client: str = "mcp"
    witness_model: str = ""

    def _authorised(self) -> None:
        if not PrincipalHouseholdAuthority(self.log).permits_write(
                self.principal, self.household_id):
            raise MissionDestinationDenied(
                "principal is not authorised to mutate this household")

    def _state(self) -> tuple[EntityProjection, MissionTargetProjection, MissionAssessmentRegistry]:
        core = EntityProjection(self.log)
        definitions = MissionAssessmentRegistry()
        register_finance_mission_definitions(definitions)
        targets = MissionTargetProjection(
            self.log, core, definitions, FinanceTargetMetricResolver())
        return core, targets, definitions

    def _mission_household(self, mission: Mission,
                           targets: MissionTargetProjection) -> str:
        target_households = {
            target.household_id for target in targets.targets.values()
            if target.mission_id == mission.id
        }
        if len(target_households) > 1 or mission.id in targets.conflicts:
            raise MissionDestinationDenied("Mission Target history is conflicted")
        target_household = next(iter(target_households), None)
        if (target_household is not None and mission.household_id is not None
                and target_household != mission.household_id):
            raise MissionDestinationDenied("Mission household binding is inconsistent")
        household_id = target_household or mission.household_id
        if household_id != self.household_id:
            raise MissionDestinationDenied("mission is not authorised for this household")
        return household_id

    def _request(self, mission_id: str, target_metric: str, reason: str) -> dict[str, Any]:
        self._authorised()
        mission_id = _text(mission_id, "mission_id")
        target_metric = _text(target_metric, "target_metric")
        reason = _text(reason, "reason")
        core, targets, definitions = self._state()
        mission = core.missions.get(mission_id)
        if mission is None or mission.status != "active":
            raise MissionDestinationDenied("mission is not active")
        household_id = self._mission_household(mission, targets)
        household = core.parties.get(household_id)
        if household is None or household.party_type != "household" or household.status != "active":
            raise MissionDestinationDenied("Mission household is unavailable")
        if target_metric == mission.target_metric:
            raise MissionDestinationDenied("target_metric is already current")
        resolver = FinanceTargetMetricResolver()
        descriptor = resolver.describe(target_metric)
        horizon_kind = resolver.horizon_kind(target_metric)
        definition = definitions.definition_for_policy(mission.assessment_policy_id or "")
        if descriptor is None or horizon_kind not in vocab.TARGET_HORIZON_KIND:
            raise MissionDestinationDenied("target_metric is not a recognised Finance Mission Target metric")
        if definition is None or descriptor.destination_direction != definition.destination_direction:
            raise MissionDestinationDenied("target_metric destination direction is incompatible with this Mission")
        if targets.in_force(mission.id, time.time()) is not None:
            raise MissionDestinationDenied("Mission Target is currently in force")
        target_state = [
            {"id": target.id, "history": list(target.history),
             "effective_from": target.effective_from, "closed_at": target.closed_at}
            for target in sorted(targets.targets.values(), key=lambda target: target.id)
            if target.mission_id == mission.id
        ]
        state_digest = _digest({
            "mission_history": mission.history,
            "target_state": target_state,
            "target_conflicts": targets.conflicts.get(mission.id, ()),
        })
        return {
            "operation": "amend_mission_target_metric", "mission_id": mission.id,
            "household_id": household_id, "current_target_metric": mission.target_metric,
            "target_metric": target_metric, "reason": reason, "principal": self.principal,
            "state_digest": state_digest,
        }

    @staticmethod
    def _command_values(mission_id: str, household_id: str, target_metric: str,
                        reason: str, principal: str) -> dict[str, str]:
        return {
            "operation": "amend_mission_target_metric", "mission_id": mission_id,
            "household_id": household_id, "target_metric": target_metric,
            "reason": reason, "principal": principal,
        }

    def propose_mission_target_metric(self, *, mission_id: str, target_metric: str,
                                      reason: str) -> dict[str, Any]:
        request = self._request(mission_id, target_metric, reason)
        digest = _digest(request)
        proposal_id = f"mission-target-metric-{digest[:24]}"
        for event in self.log.events():
            if (event["kind"] == "application.mission_destination.proposed"
                    and event["payload"].get("proposal_id") == proposal_id):
                return {"proposal_id": proposal_id, "request_digest": digest,
                        "state": "proposed"}
        self.log.append("application.mission_destination.proposed", {
            "proposal_id": proposal_id, "request_digest": digest, "request": request,
            "principal": self.principal, "client": self.client,
            "witness_model": self.witness_model,
        }, actor=f"mcp:{self.principal}")
        return {"proposal_id": proposal_id, "request_digest": digest, "state": "proposed"}

    def execute_mission_target_metric(self, *, mission_id: str, target_metric: str,
                                      reason: str, proposal_id: str,
                                      command_id: str) -> dict[str, Any]:
        command_id = _text(command_id, "command_id")
        mission_id = _text(mission_id, "mission_id")
        target_metric = _text(target_metric, "target_metric")
        reason = _text(reason, "reason")
        command_values = self._command_values(
            mission_id, self.household_id, target_metric, reason, self.principal)
        command_digest = _digest(command_values)
        for event in self.log.events():
            if event["kind"] != "application.mission_destination.executed":
                continue
            payload = event["payload"]
            if payload.get("household_id") != self.household_id or payload.get("command_id") != command_id:
                continue
            if (payload.get("proposal_id") != proposal_id
                    or payload.get("command_digest") != command_digest):
                raise MissionDestinationDenied("command_id was already used for a different operation")
            return dict(payload["result"])
        request = self._request(mission_id, target_metric, reason)
        digest = _digest(request)
        proposal = next((event["payload"] for event in self.log.events()
                         if event["kind"] == "application.mission_destination.proposed"
                         and event["payload"].get("proposal_id") == proposal_id), None)
        if proposal is None or proposal.get("request_digest") != digest:
            raise MissionDestinationDenied("proposal is stale or does not match current canonical state")
        update = grammar.update(
            self.log, "core", "mission", request["mission_id"],
            {"target_metric": request["target_metric"]}, request["reason"],
            actor=f"mcp:{self.principal}")
        result = {
            "mission_id": request["mission_id"],
            "previous_target_metric": request["current_target_metric"],
            "target_metric": request["target_metric"], "provenance": [update["id"]],
        }
        self.log.append("application.mission_destination.executed", {
            "household_id": request["household_id"], "command_id": command_id,
            "command_digest": command_digest, "proposal_id": proposal_id,
            "request_digest": digest, "result": result, "principal": self.principal,
            "client": self.client, "witness_model": self.witness_model,
        }, actor=f"mcp:{self.principal}")
        return result

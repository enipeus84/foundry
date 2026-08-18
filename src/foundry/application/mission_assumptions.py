"""One governed lifecycle for mission Assumption Set onboarding."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import math
from typing import Any

from foundry.core import grammar
from foundry.core.entities import EntityProjection
from foundry.eventlog import EventLog
from foundry.finance.entities import AssumptionSet, FinanceEntityProjection
from foundry.finance.mission_assessment import ProjectionInputs, POLICY_ID as FI_POLICY_ID
from foundry.finance.missions import FINANCE_MISSION_DEFINITIONS
from foundry.finance.mortgage_assessment import MortgageProjectionInputs, POLICY_ID as MORTGAGE_POLICY_ID
from foundry.finance.pension_assessment import PensionIndependenceInputs, POLICY_ID as PENSION_POLICY_ID
from foundry.finance.resilience_assessment import FinancialResilienceInputs, TARGET_MONTHS, POLICY_ID as RESILIENCE_POLICY_ID
from foundry.finance.entities import declare_assumption_set, archive_assumption_set


class MissionAssumptionError(ValueError):
    pass


@dataclass(frozen=True)
class MissionAssumptionSchema:
    policy_id: str
    mission: str
    fields: tuple[str, ...]
    governed: dict[str, float]
    validator: Any


@dataclass(frozen=True)
class Readiness:
    mission_id: str
    mission: str
    household_id: str
    active_set_id: str | None
    active_set_version: str | None
    required_editable_fields: tuple[str, ...]
    blockers: tuple[str, ...]

    @property
    def has_active_set(self) -> bool:
        return self.active_set_id is not None and not self.blockers

    def as_dict(self) -> dict[str, Any]:
        return {"mission": self.mission, "mission_id": self.mission_id,
                "household_id": self.household_id,
                "has_active_set": self.has_active_set,
                "active_set_id": self.active_set_id,
                "active_set_version": self.active_set_version,
                "required_editable_fields": list(self.required_editable_fields),
                "current_blockers": list(self.blockers)}


def _schema(policy_id: str) -> MissionAssumptionSchema:
    common = {
        FI_POLICY_ID: (
            ("monthly_contribution", "low_real_return", "base_real_return", "high_real_return",
             "horizon_years", "history_months", "delta_v_lookback_days",
             "desired_annual_spending", "withdrawal_rate"), {}, ProjectionInputs),
        RESILIENCE_POLICY_ID: (
            ("critical_floor_months", "income_concentration_limit", "outflow_crosscheck_tolerance",
             "evidence_stale_after_days", "movement_lookback_days", "income_reduction_fraction",
             "income_reduction_months", "unexpected_expenditure", "rate_shock_monthly_cost",
             "temporary_unemployment_months"),
            {"reserve_target_months": TARGET_MONTHS, "secure_floor_months": 6.0,
             "commitment_horizon_months": 12.0}, FinancialResilienceInputs),
        PENSION_POLICY_ID: (
            ("required_retirement_income_annual", "low_real_return", "base_real_return", "high_real_return",
             "sustainable_withdrawal_rate", "assumed_annual_fee_percent", "contribution_stale_after_days",
             "valuation_stale_after_days", "evidence_crosscheck_tolerance", "accelerated_threshold_months",
             "divergent_floor_fraction", "surplus_high_fraction", "shortfall_low_fraction",
             "sp_reliance_low_fraction", "sp_reliance_mid_fraction", "sp_reliance_high_fraction",
             "delta_v_lookback_days", "recommendation_liquidity_floor_months", "planning_age"),
            {"milestone_fraction_1": .25, "milestone_fraction_2": .5,
             "milestone_fraction_3": .75, "milestone_fraction_4": 1.0}, PensionIndependenceInputs),
        MORTGAGE_POLICY_ID: (
            ("low_post_fix_rate", "base_post_fix_rate", "high_post_fix_rate", "forecast_horizon_months",
             "balance_stale_after_days", "valuation_stale_after_days", "liquidity_floor_months"), {}, MortgageProjectionInputs),
    }
    try:
        fields, governed, validator = common[policy_id]
    except KeyError as exc:
        raise MissionAssumptionError("unsupported mission policy") from exc
    label = next((d.label for d in FINANCE_MISSION_DEFINITIONS if d.assessment_policy_id == policy_id), policy_id)
    return MissionAssumptionSchema(policy_id, label, fields, governed, validator)


def _digest(values: dict[str, Any]) -> str:
    return sha256(json.dumps(values, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class MissionAssumptionService:
    def __init__(self, log: EventLog):
        self.log = log

    def _state(self) -> tuple[EntityProjection, FinanceEntityProjection]:
        return EntityProjection(self.log), FinanceEntityProjection(self.log)

    def _mission(self, mission_id: str, household_id: str):
        core, finance = self._state()
        mission = core.missions.get(mission_id)
        if mission is None or mission.status != "active":
            raise MissionAssumptionError("mission not found")
        if mission.household_id != household_id:
            raise MissionAssumptionError("mission is not authorised for this household")
        schema = _schema(mission.assessment_policy_id or "")
        return core, finance, mission, schema

    def schema(self, mission_id: str, household_id: str) -> MissionAssumptionSchema:
        return self._mission(mission_id, household_id)[3]

    def readiness(self, mission_id: str, household_id: str) -> Readiness:
        _, finance, mission, schema = self._mission(mission_id, household_id)
        current = finance.assumption_sets.get(mission.assumption_set_id or "")
        blockers: list[str] = []
        if current is None or current.status != "active":
            blockers.append("active Assumption Set not found")
        elif set(current.assumptions) != (set(schema.fields) - {"planning_age"}) | set(schema.governed) | ({"planning_age"} & set(current.assumptions)):
            blockers.append("active Assumption Set does not match mission schema")
        return Readiness(mission.id, schema.mission, household_id,
                         current.id if current and current.status == "active" else None,
                         current.version if current and current.status == "active" else None,
                         schema.fields, tuple(blockers))

    def _payload(self, mission_id: str, household_id: str, assumptions: dict[str, Any]) -> tuple[Any, dict[str, float]]:
        _, _, mission, schema = self._mission(mission_id, household_id)
        allowed = set(schema.fields) | ({"planning_age"} if "planning_age" in schema.fields else set())
        required = allowed - {"planning_age"}
        if not isinstance(assumptions, dict) or not required <= set(assumptions) or set(assumptions) - allowed:
            missing = sorted(required - set(assumptions or {}))
            extra = sorted(set(assumptions or {}) - allowed)
            raise MissionAssumptionError(f"assumption fields invalid; missing={missing}, extra={extra}")
        values: dict[str, float] = {}
        for key, value in assumptions.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                raise MissionAssumptionError(f"{key} must be a finite number")
            values[key] = float(value)
        canonical = {**values, **schema.governed}
        candidate = AssumptionSet("candidate", "candidate", "v1", canonical)
        try:
            schema.validator.from_assumption_set(candidate)
        except (TypeError, ValueError) as exc:
            raise MissionAssumptionError(str(exc)) from exc
        return mission, canonical

    def declare(self, *, mission_id: str, household_id: str, assumptions: dict[str, Any],
                actor: str = "user", version: str = "v1") -> dict[str, Any]:
        mission, canonical_values = self._payload(mission_id, household_id, assumptions)
        _, finance = self._state()
        previous = finance.assumption_sets.get(mission.assumption_set_id or "")
        created = declare_assumption_set(self.log, f"{mission.name} assumptions", version,
                                         canonical_values, actor=actor)
        grammar.update(self.log, "core", "mission", mission.id,
                       {"assumption_set_id": created.id},
                       "activate mission assumption set", actor=actor)
        if previous is not None and previous.status == "active":
            archive_assumption_set(self.log, previous.id, "superseded by mission assumption revision", actor=actor)
        return {"mission_id": mission.id, "assumption_set_id": created.id,
                "version": created.version, "replaced_assumption_set_id": previous.id if previous else None}

    def propose(self, *, mission_id: str, household_id: str, assumptions: dict[str, Any], principal: str) -> dict[str, str]:
        self._payload(mission_id, household_id, assumptions)
        values = {"mission_id": mission_id, "household_id": household_id,
                  "assumptions": assumptions, "principal": principal}
        digest = _digest(values)
        proposal_id = f"mission-assumptions-{digest[:24]}"
        if not any(e["kind"] == "application.mission_assumption.proposed" and e["payload"].get("proposal_id") == proposal_id for e in self.log.events()):
            self.log.append("application.mission_assumption.proposed",
                            {"proposal_id": proposal_id, "request_digest": digest, **values}, actor=f"mcp:{principal}")
        return {"proposal_id": proposal_id, "request_digest": digest}

    def execute(self, *, proposal_id: str, mission_id: str, household_id: str,
                assumptions: dict[str, Any], principal: str, command_id: str) -> dict[str, Any]:
        if not command_id.strip():
            raise MissionAssumptionError("command_id is required")
        for event in self.log.events():
            if event["kind"] == "application.mission_assumption.executed" and event["payload"].get("command_id") == command_id:
                return event["payload"]["result"]
        expected = {"mission_id": mission_id, "household_id": household_id,
                    "assumptions": assumptions, "principal": principal}
        digest = _digest(expected)
        match = next((e["payload"] for e in self.log.events()
                      if e["kind"] == "application.mission_assumption.proposed"
                      and e["payload"].get("proposal_id") == proposal_id), None)
        if not match or match.get("request_digest") != digest:
            raise MissionAssumptionError("proposal does not match the requested operation")
        result = self.declare(mission_id=mission_id, household_id=household_id,
                              assumptions=assumptions, actor=f"mcp:{principal}")
        self.log.append("application.mission_assumption.executed",
                        {"command_id": command_id, "proposal_id": proposal_id, "result": result},
                        actor=f"mcp:{principal}")
        return result

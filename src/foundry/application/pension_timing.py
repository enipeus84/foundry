"""Governed commands for the two pension-timing facts.

This is deliberately not a generic identity or evidence writer.  The service
owns the MCP proposal/execute receipt and delegates each fact to its existing
canonical domain command.
"""

from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import json
import math
from numbers import Real
from typing import Any

from foundry.core.entities import EntityProjection
from foundry.core.identity import (
    PersonIdentityError,
    declare_person_date_of_birth,
    parse_date_of_birth,
)
from foundry.eventlog import EventLog
from foundry.finance.pension_evidence import record_pension_evidence


class PensionTimingError(ValueError):
    """A timing declaration is unauthorised or does not match its receipt."""


def _digest(values: dict[str, Any]) -> str:
    return sha256(json.dumps(values, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _effective_at(value: str) -> float:
    if not isinstance(value, str):
        raise PensionTimingError("effective_at must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PensionTimingError("effective_at must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise PensionTimingError("effective_at must include a timezone")
    return parsed.timestamp()


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PensionTimingError(f"{field} is required")
    return value.strip()


class PensionTimingService:
    """Household-authorised, idempotent timing declarations."""

    def __init__(self, log: EventLog, household_id: str):
        self.log, self.household_id = log, household_id

    def _person(self, person_id: str) -> None:
        person_id = _text(person_id, "person_id")
        person = EntityProjection(self.log).parties.get(person_id)
        if (person is None or person.party_type != "person" or person.status != "active"
                or self.household_id not in person.memberships):
            raise PensionTimingError("person is not an active member of the authorised household")

    def _dob_values(self, person_id: str, date_of_birth: str, principal: str) -> dict[str, Any]:
        self._person(person_id)
        try:
            dob = parse_date_of_birth(date_of_birth)
        except PersonIdentityError as exc:
            raise PensionTimingError(str(exc)) from exc
        return {"operation": "declare_person_date_of_birth", "household_id": self.household_id,
                "person_id": person_id, "date_of_birth": dob.isoformat(), "principal": principal}

    def _state_pension_values(self, person_id: str, state_pension_age: float,
                              effective_at: str, source: str, lineage: str,
                              confidence: float, principal: str) -> dict[str, Any]:
        self._person(person_id)
        if (isinstance(state_pension_age, bool) or not isinstance(state_pension_age, Real)
                or not math.isfinite(float(state_pension_age)) or not 0 < float(state_pension_age) <= 120):
            raise PensionTimingError("state_pension_age must be an age in years")
        if (isinstance(confidence, bool) or not isinstance(confidence, Real)
                or not math.isfinite(float(confidence)) or not 0 <= float(confidence) <= 1):
            raise PensionTimingError("confidence must be between zero and one")
        return {
            "operation": "declare_state_pension_age", "household_id": self.household_id,
            "person_id": person_id, "state_pension_age": float(state_pension_age),
            "effective_at": _effective_at(effective_at), "source": _text(source, "source"),
            "lineage": _text(lineage, "lineage"), "confidence": float(confidence),
            "principal": principal,
        }

    def _propose(self, values: dict[str, Any]) -> dict[str, Any]:
        digest = _digest(values)
        proposal_id = f"pension-timing-{digest[:24]}"
        if not any(event["kind"] == "application.pension_timing.proposed"
                   and event["payload"].get("proposal_id") == proposal_id
                   for event in self.log.events()):
            self.log.append("application.pension_timing.proposed", {
                "proposal_id": proposal_id, "request_digest": digest, **values,
            }, actor=f"mcp:{values['principal']}")
        return {"proposal_id": proposal_id, "request_digest": digest,
                "operation": values["operation"]}

    def propose_person_date_of_birth(self, *, person_id: str, date_of_birth: str,
                                     principal: str) -> dict[str, Any]:
        return self._propose(self._dob_values(person_id, date_of_birth, principal))

    def propose_state_pension_age(self, *, person_id: str, state_pension_age: float,
                                  effective_at: str, source: str, lineage: str,
                                  confidence: float, principal: str) -> dict[str, Any]:
        return self._propose(self._state_pension_values(
            person_id, state_pension_age, effective_at, source, lineage, confidence, principal))

    def _execute(self, proposal_id: str, command_id: str, values: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(command_id, str) or not command_id.strip():
            raise PensionTimingError("command_id is required")
        digest = _digest(values)
        for event in self.log.events():
            if (event["kind"] == "application.pension_timing.executed"
                    and event["payload"].get("household_id") == self.household_id
                    and event["payload"].get("command_id") == command_id):
                if (event["payload"].get("proposal_id") != proposal_id
                        or event["payload"].get("request_digest") != digest):
                    raise PensionTimingError("command_id was already used for a different operation")
                return event["payload"]["result"]
        proposed = next((event["payload"] for event in self.log.events()
                         if event["kind"] == "application.pension_timing.proposed"
                         and event["payload"].get("proposal_id") == proposal_id), None)
        if proposed is None or proposed.get("request_digest") != digest:
            raise PensionTimingError("proposal does not match the requested operation")
        if values["operation"] == "declare_person_date_of_birth":
            event = declare_person_date_of_birth(
                self.log, values["person_id"], values["date_of_birth"], actor=f"mcp:{values['principal']}")
            result = {"person_id": values["person_id"], "date_of_birth": values["date_of_birth"],
                      "provenance": [event["id"]]}
        else:
            evidence = record_pension_evidence(
                self.log, values["person_id"], "state_pension_age", values["state_pension_age"],
                values["effective_at"], confidence=values["confidence"], source=values["source"],
                lineage=values["lineage"], unit_or_currency="years", actor=f"mcp:{values['principal']}")
            result = {"person_id": values["person_id"], "state_pension_age": values["state_pension_age"],
                      "effective_at": values["effective_at"], "provenance": [evidence.event_id]}
        self.log.append("application.pension_timing.executed", {
            "household_id": self.household_id, "command_id": command_id,
            "proposal_id": proposal_id, "request_digest": digest, "result": result,
        }, actor=f"mcp:{values['principal']}")
        return result

    def declare_person_date_of_birth(self, *, proposal_id: str, command_id: str,
                                     person_id: str, date_of_birth: str,
                                     principal: str) -> dict[str, Any]:
        return self._execute(proposal_id, command_id,
                             self._dob_values(person_id, date_of_birth, principal))

    def declare_state_pension_age(self, *, proposal_id: str, command_id: str,
                                  person_id: str, state_pension_age: float,
                                  effective_at: str, source: str, lineage: str,
                                  confidence: float, principal: str) -> dict[str, Any]:
        return self._execute(proposal_id, command_id, self._state_pension_values(
            person_id, state_pension_age, effective_at, source, lineage, confidence, principal))

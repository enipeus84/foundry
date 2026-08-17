"""Durable, fail-closed authority grants for privileged principal actions."""

from __future__ import annotations

from dataclasses import dataclass, field

from foundry.eventlog import EventLog


def _principal(value: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 256 or any(ch in value for ch in "\r\n\x00"):
        raise ValueError("principal must be a non-empty short identifier")
    return value


def _household(value: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 256 or any(ch in value for ch in "\r\n\x00"):
        raise ValueError("household id must be a non-empty short identifier")
    return value


@dataclass(frozen=True)
class PrincipalHouseholdAuthority:
    """Projection of explicit principal grants; no membership or ownership inference."""

    log: EventLog
    grants: set[tuple[str, str]] = field(init=False, default_factory=set, compare=False)

    def __post_init__(self):
        self.rebuild()

    def rebuild(self) -> None:
        self.grants.clear()
        for event in self.log.events():
            payload = event["payload"]
            try:
                principal, household_id = _principal(payload["principal"]), _household(payload["household_id"])
            except (KeyError, TypeError, ValueError):
                continue
            key = (principal, household_id)
            if event["kind"] == "core.principal_household_authority.granted":
                self.grants.add(key)
            elif event["kind"] == "core.principal_household_authority.revoked":
                self.grants.discard(key)

    def permits_write(self, principal: str, household_id: str) -> bool:
        return (_principal(principal), _household(household_id)) in self.grants


def grant_principal_household_authority(log: EventLog, principal: str, household_id: str,
                                        *, actor: str = "user") -> dict:
    principal, household_id = _principal(principal), _household(household_id)
    return log.append("core.principal_household_authority.granted", {
        "principal": principal, "household_id": household_id,
    }, actor=actor)


def revoke_principal_household_authority(log: EventLog, principal: str, household_id: str,
                                         *, actor: str = "user") -> dict:
    principal, household_id = _principal(principal), _household(household_id)
    return log.append("core.principal_household_authority.revoked", {
        "principal": principal, "household_id": household_id,
    }, actor=actor)

"""RFC-015 Capture Target Registry projection.

This is deliberately a projection over canonical declarations.  It owns no
event stream and imports no domain model: a domain supplies the small resolver
which tells it whether a registered subject is an active, compatible entity.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from foundry.core.acquisition import (
    AcquisitionError, AssetRegistration, AssetRegistry, TelemetryStream,
    TelemetryStreamRegistry,
)
from foundry.eventlog import EventLog


@dataclass(frozen=True)
class CaptureTargetEntity:
    """The domain-owned facts required to decide target eligibility."""

    subject_id: str
    display_name: str | None
    entity_type: str
    status: str


class CaptureTargetResolver(Protocol):
    """Narrow domain seam; Core never imports Finance to resolve a target."""

    def resolve(self, subject_id: str) -> CaptureTargetEntity | None: ...

    def supports(self, entity: CaptureTargetEntity, property_name: str) -> bool: ...


@dataclass(frozen=True)
class CaptureTarget:
    """An eligible target, derived entirely from the canonical log."""

    stream: TelemetryStream
    registration: AssetRegistration
    entity: CaptureTargetEntity

    @property
    def id(self) -> str:
        return self.stream.id

    @property
    def household_id(self) -> str:
        return self.stream.household_id

    @property
    def subject_id(self) -> str:
        return self.stream.subject_id

    @property
    def property(self) -> str:
        return self.stream.property


@dataclass(frozen=True)
class TelemetryStreamRetirement:
    stream_id: str
    reason: str
    retired_at: float
    superseded_by: str | None = None


class CaptureTargetRegistry:
    """Fail-closed projection and declaration gate for capture targets."""

    def __init__(self, log: EventLog, resolver: CaptureTargetResolver):
        self.log, self.resolver = log, resolver
        self.streams = TelemetryStreamRegistry(log)
        self.assets = AssetRegistry(log, entity_exists=lambda subject_id: resolver.resolve(subject_id) is not None)
        self.targets: dict[str, CaptureTarget] = {}
        self.conflicts: dict[tuple[str, str, str], tuple[str, ...]] = {}
        self.rebuild()

    def rebuild(self) -> None:
        self.streams.rebuild()
        self.assets.rebuild()
        candidates: dict[tuple[str, str, str], list[CaptureTarget]] = {}
        for stream in self.streams.streams.values():
            target = self._candidate(stream)
            if target is not None:
                candidates.setdefault((stream.household_id, stream.subject_id, stream.property), []).append(target)
        self.conflicts = {
            key: tuple(sorted(target.id for target in grouped))
            for key, grouped in candidates.items() if len(grouped) > 1
        }
        self.targets = {
            target.id: target for key, grouped in candidates.items() if key not in self.conflicts
            for target in grouped
        }

    def _candidate(self, stream: TelemetryStream) -> CaptureTarget | None:
        if stream.channel != "manual" or stream.id in self.streams.retired:
            return None
        registration = self.assets.registrations.get(stream.subject_id)
        if (registration is None or registration.household_id != stream.household_id
                or registration.lifecycle_state != "active"):
            return None
        entity = self.resolver.resolve(stream.subject_id)
        if entity is None or entity.status != "active" or not self.resolver.supports(entity, stream.property):
            return None
        return CaptureTarget(stream, registration, entity)

    def for_household(self, household_id: str) -> tuple[CaptureTarget, ...]:
        return tuple(sorted((target for target in self.targets.values()
                             if target.household_id == household_id), key=lambda target: target.id))

    def for_contract(self, household_id: str, contract) -> tuple[CaptureTarget, ...]:
        return tuple(target for target in self.for_household(household_id)
                     if contract.accepts_stream(target.property))

    def declare(self, stream: TelemetryStream, actor: str = "user") -> TelemetryStream:
        """Declare only an immediately eligible, non-conflicting target."""
        if stream.channel != "manual":
            raise AcquisitionError("capture targets require a manual telemetry stream")
        if self._candidate(stream) is None:
            raise AcquisitionError("telemetry stream is not an eligible capture target")
        key = (stream.household_id, stream.subject_id, stream.property)
        if key in self.conflicts or any((target.household_id, target.subject_id, target.property) == key
                                        for target in self.targets.values()):
            raise AcquisitionError("duplicate active capture target")
        declared = self.streams.declare(stream, actor=actor)
        self.rebuild()
        return declared

    def retire(self, stream_id: str, reason: str, retired_at: float,
               *, superseded_by: str | None = None, actor: str = "user") -> TelemetryStreamRetirement:
        if stream_id not in self.streams.streams:
            raise AcquisitionError("unknown telemetry stream")
        if stream_id in self.streams.retired:
            raise AcquisitionError("telemetry stream is already retired")
        if not isinstance(reason, str) or not reason.strip():
            raise AcquisitionError("telemetry stream retirement reason is required")
        if not isinstance(retired_at, (int, float)):
            raise AcquisitionError("telemetry stream retirement time is required")
        if superseded_by is not None and (not isinstance(superseded_by, str) or not superseded_by):
            raise AcquisitionError("invalid superseding telemetry stream")
        retirement = TelemetryStreamRetirement(stream_id, reason.strip(), float(retired_at), superseded_by)
        payload = {"stream_id": retirement.stream_id, "reason": retirement.reason,
                   "retired_at": retirement.retired_at}
        if retirement.superseded_by is not None:
            payload["superseded_by"] = retirement.superseded_by
        self.log.append("core.telemetry_stream.retired", payload, actor=actor)
        self.rebuild()
        return retirement

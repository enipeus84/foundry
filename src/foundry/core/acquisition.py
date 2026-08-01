"""RFC-011's domain-neutral, evidence-first acquisition seam.

This module deliberately has no Finance imports.  Providers can write an
envelope, interpreters can write an inert proposal, and only the confirmation
gate can append a supplied canonical-domain draft.  The Asset Registry holds
routing metadata only; values and ownership remain with their domain.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from typing import Any, Callable, Iterable, Protocol

from foundry.eventlog import EventLog

from . import vocab


MAX_EVIDENCE_BYTES = 256 * 1024
MAX_LABEL_LENGTH = 256
_SAFE_MEDIA_TYPES = frozenset({"application/json", "text/plain"})
_LIFECYCLES = frozenset({"active", "closed", "archived"})
_PROPOSAL_STATES = frozenset({"pending", "confirmed", "rejected", "superseded"})
_CONDITION_STATES = frozenset({"pending", "satisfied", "lapsed", "revoked"})
_GRADE_ORDER = {"authoritative": 0, "confirmed": 1, "declared": 2,
                "assumed": 2, "extracted": 3}
_CADENCE_SECONDS = {"continuous": 0, "daily": 86400, "weekly": 7 * 86400,
                    "monthly": 31 * 86400, "quarterly": 92 * 86400,
                    "annual": 366 * 86400}
_CREDENTIAL_NAME = re.compile(
    r"(?:^|[_.-])(?:api[_-]?key|private[_-]?key|session[_-]?id|credentials?|"
    r"authorization|password|secret|access[_-]?token|refresh[_-]?token|"
    r"id[_-]?token|token|cookie)(?:$|[_.-])", re.IGNORECASE)
_CREDENTIAL_VALUE = re.compile(
    r"(?:-----BEGIN [A-Z ]*PRIVATE KEY-----|"
    r"\b(?:api[_ -]?key|private[_ -]?key|session[_ -]?id|credentials?|"
    r"authorization|password|secret|access[_ -]?token|refresh[_ -]?token|"
    r"id[_ -]?token|token|cookie)\b\s*[:=]\s*\S+|"
    r"\bbearer\s+[A-Za-z0-9._~+/=-]{8,}|"
    r"\b(?:sk|ghp|github_pat)_[A-Za-z0-9_=-]{8,})", re.IGNORECASE)


class AcquisitionError(ValueError):
    """Input is unsupported or would breach the acquisition contract."""


class EvidenceUnavailable(AcquisitionError):
    """Evidence is missing, corrupt, redacted, or the caller is unauthorized."""


class DomainDraftContract(Protocol):
    """Domain-owned validation for inert drafts crossing the Core seam.

    Core owns the proposal and confirmation lifecycle.  The vocabulary and
    payload shape of a canonical event remain the receiving domain's concern.
    """

    interpreter_id: str
    interpreter_version: str
    interpreter_class: str

    def validate_interpretation(self, draft: dict[str, Any]) -> None: ...

    def validate_confirmation(self, draft: dict[str, Any],
                              observation: dict[str, Any]) -> None: ...


def _stable(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any) -> str:
    return sha256(_stable(value).encode("utf-8")).hexdigest()


def _identifier(value: str, label: str) -> str:
    if not isinstance(value, str) or not value or len(value) > MAX_LABEL_LENGTH:
        raise AcquisitionError(f"{label} must be a non-empty short string")
    if any(ch in value for ch in ("\x00", "\r", "\n")):
        raise AcquisitionError(f"{label} contains a control character")
    return value


def _timestamp(value: Any, label: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise AcquisitionError(f"{label} must be a numeric timestamp")
    return float(value)


def contains_credential(value: Any) -> bool:
    """Conservative deterministic detection for append-only evidence input."""
    if isinstance(value, dict):
        return any((isinstance(key, str) and _CREDENTIAL_NAME.search(key)) or
                   contains_credential(nested) for key, nested in value.items())
    if isinstance(value, (list, tuple)):
        return any(contains_credential(item) for item in value)
    return isinstance(value, str) and bool(_CREDENTIAL_VALUE.search(value))


def redact_credentials(value: Any) -> Any:
    """Return a structurally equivalent display value without credentials."""
    if isinstance(value, dict):
        return {key: "[redacted]" if isinstance(key, str) and _CREDENTIAL_NAME.search(key)
                else redact_credentials(nested) for key, nested in value.items()}
    if isinstance(value, list):
        return [redact_credentials(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_credentials(item) for item in value)
    return "[redacted]" if isinstance(value, str) and _CREDENTIAL_VALUE.search(value) else value


def weakest_grade(grades: Iterable[str]) -> str:
    """Categorical dominance, never confidence arithmetic."""
    values = list(grades)
    if not values:
        raise AcquisitionError("at least one evidence grade is required")
    for grade in values:
        if grade not in vocab.EVIDENCE_GRADE:
            raise AcquisitionError(f"unknown evidence grade {grade!r}")
    return max(values, key=lambda grade: _GRADE_ORDER[grade])


def confidence_cap(grades: Iterable[str], stale: bool = False) -> str:
    grade = weakest_grade(grades)
    if stale or grade == "extracted":
        return "Insufficient"
    if grade in {"declared", "confirmed", "assumed"}:
        return "Provisional"
    return "Established"


@dataclass(frozen=True)
class ExternalRef:
    """A typed external identifier.  Values are exact; no fuzzy matching."""
    namespace: str
    value: str

    def __post_init__(self) -> None:
        _identifier(self.namespace, "ExternalRef namespace")
        _identifier(self.value, "ExternalRef value")

    def as_dict(self) -> dict[str, str]:
        return {"namespace": self.namespace, "value": self.value}

    @classmethod
    def from_value(cls, value: dict[str, Any] | "ExternalRef") -> "ExternalRef":
        if isinstance(value, cls):
            return value
        if not isinstance(value, dict) or set(value) != {"namespace", "value"}:
            raise AcquisitionError("ExternalRef must contain namespace and value only")
        return cls(value["namespace"], value["value"])


@dataclass(frozen=True)
class TelemetryStream:
    id: str
    subject_id: str
    property: str
    channel: str
    refresh_policy: str
    confirmation_policy: str
    source_identity: str
    unit_or_currency: str
    validation_contract: str
    household_id: str
    expected_cadence: str | None = None

    def __post_init__(self) -> None:
        for label, value in (("stream id", self.id), ("subject id", self.subject_id),
                             ("property", self.property), ("source identity", self.source_identity),
                             ("unit or currency", self.unit_or_currency),
                             ("validation contract", self.validation_contract),
                             ("household id", self.household_id)):
            _identifier(value, label)
        if self.channel not in vocab.UPDATE_STRATEGY:
            raise AcquisitionError(f"unknown update strategy {self.channel!r}")
        if self.refresh_policy not in vocab.REFRESH_POLICY:
            raise AcquisitionError(f"unknown refresh policy {self.refresh_policy!r}")
        if self.confirmation_policy not in vocab.CONFIRMATION_POLICY:
            raise AcquisitionError(f"unknown confirmation policy {self.confirmation_policy!r}")
        if self.expected_cadence is not None and self.expected_cadence != self.refresh_policy:
            raise AcquisitionError("expected cadence must equal the frozen refresh policy")

    def as_dict(self) -> dict[str, Any]:
        return vars(self).copy()


class TelemetryStreamRegistry:
    """Replayable stream metadata.  Providers must register operationally too."""

    def __init__(self, log: EventLog):
        self.log = log
        self.streams: dict[str, TelemetryStream] = {}
        self.rebuild()

    def rebuild(self) -> None:
        self.streams = {}
        for event in self.log.events():
            if event["kind"] == "core.telemetry_stream.declared":
                payload = event["payload"]
                try:
                    stream = TelemetryStream(**{key: payload[key] for key in TelemetryStream.__dataclass_fields__})
                except (KeyError, TypeError, AcquisitionError):
                    continue  # hostile log events are not authority
                self.streams.setdefault(stream.id, stream)

    def declare(self, stream: TelemetryStream, actor: str = "user") -> TelemetryStream:
        if stream.id in self.streams:
            raise AcquisitionError(f"duplicate telemetry stream {stream.id!r}")
        self.log.append("core.telemetry_stream.declared", stream.as_dict(), actor=actor)
        self.streams[stream.id] = stream
        return stream


@dataclass(frozen=True)
class AssetRegistration:
    subject_id: str
    domain: str
    household_id: str
    external_refs: tuple[ExternalRef, ...] = ()
    accessibility_profile_ref: str | None = None
    lifecycle_state: str = "active"


class AssetRegistry:
    """Core routing metadata, never a financial ledger or ownership store."""

    def __init__(self, log: EventLog, entity_exists: Callable[[str], bool]):
        self.log, self.entity_exists = log, entity_exists
        self.registrations: dict[str, AssetRegistration] = {}
        self.parents: dict[str, str] = {}
        self.rebuild()

    def rebuild(self) -> None:
        self.registrations, self.parents = {}, {}
        for event in self.log.events():
            payload, kind = event["payload"], event["kind"]
            if kind == "core.asset_registry.declared":
                try:
                    refs = tuple(ExternalRef.from_value(value) for value in payload.get("external_refs", ()))
                    record = AssetRegistration(payload["subject_id"], payload["domain"],
                                               payload["household_id"], refs,
                                               payload.get("accessibility_profile_ref"),
                                               payload.get("lifecycle_state", "active"))
                except (KeyError, AcquisitionError, TypeError):
                    continue
                if record.subject_id not in self.registrations:
                    self.registrations[record.subject_id] = record
            elif kind == "core.asset_registry.linked" and payload.get("relation") == "contains":
                parent, child = payload.get("entity_id"), payload.get("target")
                if parent in self.registrations and child in self.registrations and child not in self.parents:
                    self.parents[child] = parent

    def register(self, registration: AssetRegistration, actor: str = "user") -> AssetRegistration:
        if registration.lifecycle_state not in _LIFECYCLES:
            raise AcquisitionError("invalid asset lifecycle state")
        if not self.entity_exists(registration.subject_id):
            raise AcquisitionError("unknown domain entity reference")
        if registration.subject_id in self.registrations:
            raise AcquisitionError("duplicate asset registration")
        payload = {"subject_id": registration.subject_id, "domain": registration.domain,
                   "household_id": registration.household_id,
                   "external_refs": [ref.as_dict() for ref in registration.external_refs],
                   "lifecycle_state": registration.lifecycle_state}
        if registration.accessibility_profile_ref is not None:
            payload["accessibility_profile_ref"] = registration.accessibility_profile_ref
        self.log.append("core.asset_registry.declared", payload, actor=actor)
        self.registrations[registration.subject_id] = registration
        return registration

    def contain(self, container_id: str, holding_id: str, actor: str = "user") -> dict:
        container, holding = self.registrations.get(container_id), self.registrations.get(holding_id)
        if container is None or holding is None:
            raise AcquisitionError("containment requires registered subjects")
        if container.household_id != holding.household_id:
            raise AcquisitionError("cross-household containment is forbidden")
        if container_id == holding_id:
            raise AcquisitionError("containment cycle")
        if holding_id in self.parents:
            raise AcquisitionError("duplicate or incompatible containment edge")
        cursor = container_id
        while cursor in self.parents:
            cursor = self.parents[cursor]
            if cursor == holding_id:
                raise AcquisitionError("containment cycle")
        event = self.log.append("core.asset_registry.linked", {
            "entity_id": container_id, "relation": "contains", "target": holding_id,
        }, actor=actor)
        self.parents[holding_id] = container_id
        return event

    def children_of(self, subject_id: str) -> tuple[str, ...]:
        return tuple(child for child, parent in self.parents.items() if parent == subject_id)


class EvidenceVault:
    """Content-addressed, permission-checked private evidence storage.

    V1 uses a process-private directory (0700) and files (0600).  Encryption
    is intentionally not improvised with a home-grown cipher; deployment may
    place this directory on encrypted storage.  The log commits only hashes.
    """

    def __init__(self, root: str | Path, authorized: Callable[[str], bool]):
        self.root, self.authorized = Path(root), authorized
        self.root.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.root, 0o700)
        except OSError:
            pass

    def _authorize(self, actor: str) -> None:
        if not actor or not self.authorized(actor):
            raise EvidenceUnavailable("evidence access is unauthorized")

    def _path(self, payload_hash: str) -> Path:
        if not re.fullmatch(r"[0-9a-f]{64}", payload_hash):
            raise EvidenceUnavailable("invalid evidence reference")
        return self.root / payload_hash

    def put(self, payload: bytes, actor: str) -> tuple[str, str]:
        self._authorize(actor)
        if not isinstance(payload, bytes) or not payload or len(payload) > MAX_EVIDENCE_BYTES:
            raise AcquisitionError("evidence payload is empty or exceeds the size limit")
        payload_hash = sha256(payload).hexdigest()
        path = self._path(payload_hash)
        if not path.exists():
            temp = path.with_suffix(".tmp")
            temp.write_bytes(payload)
            os.chmod(temp, 0o600)
            temp.replace(path)
        return payload_hash, f"vault:{payload_hash}"

    def get(self, payload_hash: str, actor: str) -> bytes:
        self._authorize(actor)
        path = self._path(payload_hash)
        if not path.exists():
            raise EvidenceUnavailable("evidence is missing or redacted")
        payload = path.read_bytes()
        if sha256(payload).hexdigest() != payload_hash:
            raise EvidenceUnavailable("evidence hash mismatch")
        return payload

    def redact(self, log: EventLog, payload_hash: str, reason: str, actor: str) -> dict:
        self._authorize(actor)
        _identifier(reason, "redaction reason")
        path = self._path(payload_hash)
        if not path.exists():
            raise EvidenceUnavailable("evidence is already missing")
        path.unlink()
        return log.append("core.evidence.redacted", {
            "payload_hash": payload_hash, "reason": reason,
        }, actor=actor)


@dataclass(frozen=True)
class TelemetryEnvelope:
    id: str
    stream_id: str
    channel: str
    source_identity: str
    received_at: float
    payload_hash: str
    payload_ref: str
    payload_media_type: str
    external_ref: str | None
    evidence_grade: str
    recorded_at: float


class EnvelopeProjection:
    def __init__(self, log: EventLog):
        self.log = log
        self.envelopes: dict[str, TelemetryEnvelope] = {}
        self.rebuild()

    def rebuild(self) -> None:
        self.envelopes = {}
        for event in self.log.events():
            if event["kind"] != "core.telemetry_envelope.declared":
                continue
            payload = event["payload"]
            try:
                envelope = TelemetryEnvelope(
                    **{key: payload[key] for key in TelemetryEnvelope.__dataclass_fields__ if key != "recorded_at"},
                    recorded_at=float(event["ts"]),
                )
            except (KeyError, TypeError, ValueError):
                continue
            self.envelopes.setdefault(envelope.id, envelope)

    def duplicate(self, stream_id: str, external_ref: str | None, payload_hash: str) -> TelemetryEnvelope | None:
        return next((item for item in self.envelopes.values()
                     if (item.stream_id, item.external_ref, item.payload_hash) ==
                     (stream_id, external_ref, payload_hash)), None)


class AcquisitionProviderRegistry:
    """Operational wiring, intentionally rebuilt at startup rather than logged."""
    def __init__(self):
        self._providers: dict[str, "ManualAcquisitionProvider"] = {}

    def register(self, provider: "ManualAcquisitionProvider") -> None:
        for stream_id in provider.stream_ids:
            if stream_id in self._providers:
                raise AcquisitionError(f"duplicate provider for stream {stream_id!r}")
            self._providers[stream_id] = provider

    def provider_for(self, stream_id: str) -> "ManualAcquisitionProvider":
        try:
            return self._providers[stream_id]
        except KeyError as exc:
            raise AcquisitionError("unregistered stream acquires nothing") from exc


class ManualAcquisitionProvider:
    """Capture only.  It cannot construct or append a canonical event."""
    strategy = "manual"

    def __init__(self, log: EventLog, streams: TelemetryStreamRegistry,
                 vault: EvidenceVault, stream_ids: Iterable[str]):
        self.log, self.streams, self.vault = log, streams, vault
        self.stream_ids = frozenset(stream_ids)
        if not self.stream_ids:
            raise AcquisitionError("manual provider needs at least one stream")
        for stream_id in self.stream_ids:
            stream = streams.streams.get(stream_id)
            if stream is None or stream.channel != self.strategy:
                raise AcquisitionError("manual provider only serves declared manual streams")

    @staticmethod
    def _validate_payload(payload: dict[str, Any]) -> None:
        if not isinstance(payload, dict) or not isinstance(payload.get("observations"), list):
            raise AcquisitionError("manual evidence must contain an observations list")
        if not payload["observations"] or len(payload["observations"]) > 100:
            raise AcquisitionError("manual evidence observation count is invalid")
        encoded = _stable(payload).encode("utf-8")
        if len(encoded) > MAX_EVIDENCE_BYTES:
            raise AcquisitionError("manual evidence exceeds the size limit")
        if contains_credential(payload):
            raise AcquisitionError("credentials are forbidden in evidence")

    def capture(self, stream_id: str, payload: dict[str, Any], *, received_at: float,
                actor: str, source_identity: str, external_ref: str | None = None,
                evidence_grade: str = "declared") -> TelemetryEnvelope:
        stream = self.streams.streams.get(stream_id)
        if stream is None or stream_id not in self.stream_ids:
            raise AcquisitionError("stream is not served by this manual provider")
        if source_identity != stream.source_identity:
            raise AcquisitionError("source identity does not match stream declaration")
        if evidence_grade != "declared":
            raise AcquisitionError("manual capture has declared evidence grade")
        _timestamp(received_at, "received_at")
        if external_ref is not None:
            _identifier(external_ref, "external reference")
        self._validate_payload(payload)
        raw = _stable(payload).encode("utf-8")
        payload_hash, payload_ref = self.vault.put(raw, actor)
        envelopes = EnvelopeProjection(self.log)
        duplicate = envelopes.duplicate(stream_id, external_ref, payload_hash)
        if duplicate is not None:
            return duplicate
        envelope_id = "envelope-" + _digest([stream_id, external_ref, payload_hash])[:24]
        event = self.log.append("core.telemetry_envelope.declared", {
            "id": envelope_id, "stream_id": stream_id, "channel": self.strategy,
            "source_identity": source_identity, "received_at": float(received_at),
            "payload_hash": payload_hash, "payload_ref": payload_ref,
            "payload_media_type": "application/json", "external_ref": external_ref,
            "evidence_grade": evidence_grade,
        }, actor=actor)
        return TelemetryEnvelope(envelope_id, stream_id, self.strategy, source_identity,
                                 float(received_at), payload_hash, payload_ref,
                                 "application/json", external_ref, evidence_grade, event["ts"])


@dataclass(frozen=True)
class IdentityResolution:
    external_ref: ExternalRef
    outcome: str
    subject_id: str | None = None
    basis: str = ""
    candidates: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        result = {"external_ref": self.external_ref.as_dict(), "outcome": self.outcome,
                  "basis": self.basis}
        if self.subject_id is not None:
            result["subject_id"] = self.subject_id
        if self.candidates:
            result["candidates"] = list(self.candidates)
        return result


class IdentityIndex:
    """Confirmed aliases only; projections never learn from a proposal."""
    def __init__(self, log: EventLog):
        self.log = log
        self.aliases: dict[tuple[str, str, str], set[str]] = {}
        self.rebuild()

    def rebuild(self) -> None:
        self.aliases = {}
        for event in self.log.events():
            if event["kind"] != "core.identity_alias.declared":
                continue
            payload = event["payload"]
            try:
                ref = ExternalRef.from_value(payload["external_ref"])
                household, subject = payload["household_id"], payload["subject_id"]
                _identifier(household, "household id")
                _identifier(subject, "subject id")
            except (KeyError, AcquisitionError):
                continue
            self.aliases.setdefault((household, ref.namespace, ref.value), set()).add(subject)

    def declare(self, household_id: str, external_ref: ExternalRef, subject_id: str,
                proposal_id: str, actor: str) -> dict:
        _identifier(household_id, "household id")
        _identifier(subject_id, "subject id")
        return self.log.append("core.identity_alias.declared", {
            "household_id": household_id, "external_ref": external_ref.as_dict(),
            "subject_id": subject_id, "provenance": {"proposal_id": proposal_id},
        }, actor=actor)


class ResolutionService:
    """Read-only exact resolution and semantic duplicate detection."""
    def __init__(self, index: IdentityIndex, registry: AssetRegistry, inbox: "ProposalInbox | None" = None):
        self.index, self.registry, self.inbox = index, registry, inbox

    def resolve(self, household_id: str, external_ref: ExternalRef) -> IdentityResolution:
        indexed = self.index.aliases.get((household_id, external_ref.namespace, external_ref.value), set())
        registered = {record.subject_id for record in self.registry.registrations.values()
                      if record.household_id == household_id and external_ref in record.external_refs}
        candidates = tuple(sorted(indexed | registered))
        if len(candidates) == 1:
            return IdentityResolution(external_ref, "resolved", candidates[0], "exact_identity_index")
        if len(candidates) > 1:
            return IdentityResolution(external_ref, "ambiguous", basis="multiple_exact_matches",
                                      candidates=candidates)
        return IdentityResolution(external_ref, "unresolved", basis="no_exact_match")

    def semantic_duplicate(self, stream_id: str, subject_id: str | None, observation_kind: str,
                           valid_at: float, external_document_ref: str | None) -> str | None:
        if self.inbox is None:
            raise AcquisitionError("semantic duplicate protection is unavailable")
        if subject_id is None:
            return None
        for proposal in self.inbox.proposals.values():
            if proposal.state != "confirmed":
                continue
            for observation in proposal.observations:
                if (observation.get("stream_id"), observation.get("subject_id"),
                    observation.get("kind"), observation.get("valid_at"),
                    observation.get("external_document_ref")) == (
                        stream_id, subject_id, observation_kind, valid_at, external_document_ref):
                    return proposal.id
        return None


@dataclass(frozen=True)
class Proposal:
    id: str
    evidence_id: str
    envelope_id: str
    household_id: str
    interpreter_id: str
    interpreter_version: str
    interpreter_class: str
    stream_id: str
    draft_events: tuple[dict[str, Any], ...]
    observations: tuple[dict[str, Any], ...]
    resolutions: tuple[dict[str, Any], ...]
    evidence_grade: str
    notes: str = ""
    state: str = "pending"
    resolution_reason: str | None = None


class ProposalInbox:
    def __init__(self, log: EventLog):
        self.log = log
        self.proposals: dict[str, Proposal] = {}
        self.rebuild()

    def rebuild(self) -> None:
        raw: dict[str, dict[str, Any]] = {}
        states: dict[str, tuple[str, str | None]] = {}
        for event in self.log.events():
            payload = event["payload"]
            if event["kind"] == "core.observation_proposal.declared":
                raw.setdefault(payload.get("id", ""), payload)
            elif event["kind"] == "core.observation_proposal.updated":
                state = payload.get("resolution")
                if state in _PROPOSAL_STATES:
                    states[payload.get("entity_id", "")] = (state, payload.get("reason"))
        self.proposals = {}
        for proposal_id, payload in raw.items():
            try:
                state, reason = states.get(proposal_id, ("pending", None))
                proposal = Proposal(
                    id=proposal_id, evidence_id=payload["evidence_id"], envelope_id=payload["envelope_id"],
                    household_id=payload["household_id"], interpreter_id=payload["interpreter_id"],
                    interpreter_version=payload["interpreter_version"], interpreter_class=payload["interpreter_class"],
                    stream_id=payload["stream_id"], draft_events=tuple(payload["draft_events"]),
                    observations=tuple(payload["observations"]), resolutions=tuple(payload["resolutions"]),
                    evidence_grade=payload["evidence_grade"], notes=payload.get("notes", ""),
                    state=state, resolution_reason=reason)
            except (KeyError, TypeError):
                continue
            self.proposals[proposal.id] = proposal

    def resolve(self, proposal_id: str, resolution: str, reason: str, actor: str) -> dict:
        proposal = self.proposals.get(proposal_id)
        if proposal is None or proposal.state != "pending":
            raise AcquisitionError("only a pending proposal can be resolved")
        if resolution not in {"confirmed", "rejected", "superseded"}:
            raise AcquisitionError("invalid proposal resolution")
        _identifier(reason, "proposal resolution reason")
        event = self.log.append("core.observation_proposal.updated", {
            "entity_id": proposal_id, "resolution": resolution, "reason": reason,
            "resolved_by": actor,
        }, actor=actor)
        self.rebuild()
        return event


class ManualInterpreter:
    """A deterministic, versioned JSON interpreter for manually captured facts."""
    def __init__(self, vault: EvidenceVault, envelopes: EnvelopeProjection,
                 streams: TelemetryStreamRegistry, resolver: ResolutionService,
                 draft_contract: DomainDraftContract):
        self.vault, self.envelopes, self.streams, self.resolver = vault, envelopes, streams, resolver
        self.draft_contract = draft_contract
        self.interpreter_id = draft_contract.interpreter_id
        self.interpreter_version = draft_contract.interpreter_version
        self.interpreter_class = draft_contract.interpreter_class

    def _observation(self, fact: dict[str, Any], stream: TelemetryStream,
                     external_document_ref: str | None) -> tuple[dict[str, Any], dict[str, Any]]:
        required = {"kind", "subject_id", "valid_at", "canonical_event"}
        if not isinstance(fact, dict) or not required <= set(fact):
            raise AcquisitionError("manual observation has an unsupported shape")
        kind, subject_id = fact["kind"], fact["subject_id"]
        _identifier(kind, "observation kind")
        _identifier(subject_id, "subject id")
        valid_at = _timestamp(fact["valid_at"], "valid_at")
        observed_at = _timestamp(fact.get("observed_at", valid_at), "observed_at")
        event = fact["canonical_event"]
        if not isinstance(event, dict) or set(event) != {"kind", "payload"}:
            raise AcquisitionError("unsupported canonical draft event")
        if not isinstance(event["payload"], dict) or "recorded_at" in event["payload"]:
            raise AcquisitionError("draft event payload is invalid")
        observation = {"stream_id": stream.id, "subject_id": subject_id, "kind": kind,
                       "valid_at": valid_at, "observed_at": observed_at,
                       "external_document_ref": external_document_ref}
        if "value" in fact:
            if not isinstance(fact["value"], (int, float)) or isinstance(fact["value"], bool):
                raise AcquisitionError("observation value must be numeric")
            observation["value"] = float(fact["value"])
        if "unit" in fact:
            observation["unit"] = _identifier(fact["unit"], "observation unit")
        draft = {"kind": event["kind"], "payload": dict(event["payload"])}
        self.draft_contract.validate_interpretation(draft)
        return observation, draft

    def interpret(self, envelope_id: str, actor: str) -> Proposal:
        envelope = self.envelopes.envelopes.get(envelope_id)
        if envelope is None:
            raise AcquisitionError("interpreter requires a captured envelope")
        if envelope.payload_media_type not in _SAFE_MEDIA_TYPES:
            raise AcquisitionError("unsupported evidence media type")
        stream = self.streams.streams.get(envelope.stream_id)
        if stream is None:
            raise AcquisitionError("envelope references an unknown stream")
        try:
            payload = json.loads(self.vault.get(envelope.payload_hash, actor).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, EvidenceUnavailable) as exc:
            raise AcquisitionError("malformed immutable evidence") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("observations"), list):
            raise AcquisitionError("unsupported manual evidence")
        inbox = self.resolver.inbox
        if inbox is None:
            raise AcquisitionError("semantic duplicate protection is unavailable")
        proposal_id = "proposal-" + _digest([envelope.id, self.interpreter_id, self.interpreter_version])[:24]
        if proposal_id in inbox.proposals:
            return inbox.proposals[proposal_id]
        observations, drafts, resolutions = [], [], []
        for fact in payload["observations"]:
            observation, draft = self._observation(fact, stream, envelope.external_ref)
            external = fact.get("external_ref")
            if external is not None:
                resolution = self.resolver.resolve(stream.household_id, ExternalRef.from_value(external))
                observation["external_ref"] = resolution.external_ref.as_dict()
                observation["resolution"] = resolution.outcome
                subject_id = resolution.subject_id or observation["subject_id"]
                duplicate = self.resolver.semantic_duplicate(
                    stream.id, subject_id, observation["kind"], observation["valid_at"], envelope.external_ref)
                resolution_dict = resolution.as_dict()
                if duplicate is not None:
                    resolution_dict["duplicate_of"] = duplicate
                resolutions.append(resolution_dict)
            observations.append(observation)
            drafts.append(draft)
        proposal_payload = {
            "id": proposal_id, "evidence_id": envelope.payload_hash, "envelope_id": envelope.id,
            "household_id": stream.household_id, "interpreter_id": self.interpreter_id,
            "interpreter_version": self.interpreter_version, "interpreter_class": self.interpreter_class,
            "stream_id": stream.id, "draft_events": drafts, "observations": observations,
            "resolutions": resolutions, "evidence_grade": envelope.evidence_grade,
            "notes": "deterministic manual interpretation",
        }
        self.envelopes.log.append("core.observation_proposal.declared", proposal_payload, actor=actor)
        inbox.rebuild()
        return inbox.proposals[proposal_id]


class ConfirmationGate:
    """The sole acquisition path allowed to append canonical domain events."""
    def __init__(self, log: EventLog, inbox: ProposalInbox, streams: TelemetryStreamRegistry,
                 identities: IdentityIndex, registry: AssetRegistry | None = None,
                 draft_contract: DomainDraftContract | None = None):
        self.log, self.inbox, self.streams, self.identities = log, inbox, streams, identities
        self.registry = registry
        self.draft_contract = draft_contract

    def _validate_draft(self, draft: dict[str, Any], observation: dict[str, Any]) -> None:
        if not isinstance(draft, dict) or set(draft) != {"kind", "payload"}:
            raise AcquisitionError("proposal draft was tampered with")
        if (not isinstance(draft["kind"], str) or not draft["kind"] or
                not isinstance(draft["payload"], dict)):
            raise AcquisitionError("only a validated domain draft may be confirmed")
        if "recorded_at" in draft["payload"] or "recorded_at" in observation:
            raise AcquisitionError("recorded_at is substrate-owned")
        _timestamp(observation.get("valid_at"), "valid_at")
        _timestamp(observation.get("observed_at"), "observed_at")
        if self.draft_contract is None:
            raise AcquisitionError("domain draft validation is unavailable")
        self.draft_contract.validate_confirmation(draft, observation)

    def _proposal_and_stream(self, proposal_id: str) -> tuple[Proposal, TelemetryStream]:
        proposal = self.inbox.proposals.get(proposal_id)
        if proposal is None or proposal.state != "pending":
            raise AcquisitionError("proposal is not pending")
        stream = self.streams.streams.get(proposal.stream_id)
        if stream is None or stream.household_id != proposal.household_id:
            raise AcquisitionError("proposal stream is unknown or cross-household")
        return proposal, stream

    def confirm(self, proposal_id: str, *, actor: str,
                reason: str = "confirmed after review") -> tuple[dict, ...]:
        proposal, stream = self._proposal_and_stream(proposal_id)
        if stream.confirmation_policy != "review_each":
            raise AcquisitionError("stream confirmation policy does not permit individual confirmation")
        return self._confirm(proposal, stream, actor=actor, reason=reason)

    def confirm_batch(self, proposal_ids: Iterable[str], *, actor: str,
                      reason: str = "confirmed as review batch") -> tuple[dict, ...]:
        items = [self._proposal_and_stream(proposal_id) for proposal_id in proposal_ids]
        if not items or any(stream.confirmation_policy != "review_batch" for _, stream in items):
            raise AcquisitionError("review batch requires pending review_batch proposals")
        if len({proposal.id for proposal, _ in items}) != len(items):
            raise AcquisitionError("review batch contains a duplicate proposal")
        return tuple(event for proposal, stream in items
                     for event in self._confirm(proposal, stream, actor=actor, reason=reason))

    def apply_confirmation_policy(self, proposal_id: str, *, actor: str) -> tuple[dict, ...]:
        """Apply only a stream's declared automatic policy through the gate."""
        proposal, stream = self._proposal_and_stream(proposal_id)
        if stream.confirmation_policy != "auto_commit":
            return ()
        if proposal.interpreter_class != "deterministic" or proposal.evidence_grade not in {"authoritative", "declared"}:
            raise AcquisitionError("auto-commit requires deterministic authoritative or declared evidence")
        return self._confirm(proposal, stream, actor=actor,
                             reason="confirmed by declared auto_commit policy")

    def _confirm(self, proposal: Proposal, stream: TelemetryStream, *, actor: str,
                 reason: str) -> tuple[dict, ...]:
        if proposal.interpreter_class != "deterministic":
            raise AcquisitionError("model-class proposals require a dedicated review workflow")
        if (self.draft_contract is None or
                (proposal.interpreter_id, proposal.interpreter_version, proposal.interpreter_class) !=
                (self.draft_contract.interpreter_id, self.draft_contract.interpreter_version,
                 self.draft_contract.interpreter_class)):
            raise AcquisitionError("proposal interpreter contract is unavailable or unsupported")
        for resolution in proposal.resolutions:
            if resolution.get("outcome") == "ambiguous":
                raise AcquisitionError("ambiguous identity blocks confirmation")
            if resolution.get("duplicate_of"):
                raise AcquisitionError("semantic duplicate requires explicit rejection or reconciliation")
            if resolution.get("outcome") == "unresolved":
                ref = resolution.get("external_ref")
                matching = [
                    (draft, observation) for draft, observation in zip(
                        proposal.draft_events, proposal.observations)
                    if observation.get("external_ref") == ref
                ]
                if not matching or not any(
                        draft["kind"].endswith(".declared") and
                        draft["payload"].get("entity_id") == observation["subject_id"]
                        for draft, observation in matching):
                    raise AcquisitionError("unresolved identity requires an explicit new-subject draft")
        if len(proposal.draft_events) != len(proposal.observations):
            raise AcquisitionError("proposal draft and observation counts differ")
        for draft, observation in zip(proposal.draft_events, proposal.observations):
            self._validate_draft(draft, observation)
            if self.registry is not None:
                registered = self.registry.registrations.get(observation["subject_id"])
                if registered is not None and registered.household_id != proposal.household_id:
                    raise AcquisitionError("cross-household observation is forbidden")
        confirmed: list[dict] = []
        for draft, observation in zip(proposal.draft_events, proposal.observations):
            payload = dict(draft["payload"])
            payload["provenance"] = {"evidence_id": proposal.evidence_id,
                                     "proposal_id": proposal.id,
                                     "interpreter_id": proposal.interpreter_id,
                                     "interpreter_version": proposal.interpreter_version,
                                     "confirmed_by": actor}
            payload["observation"] = {**observation, "evidence_grade": proposal.evidence_grade}
            confirmed.append(self.log.append(draft["kind"], payload, actor=actor))
        for resolution in proposal.resolutions:
            external = resolution.get("external_ref")
            if external is None:
                continue
            observation = next((item for item in proposal.observations
                                if item.get("external_ref") == external), None)
            if observation is None:
                raise AcquisitionError("identity resolution does not match a proposal observation")
            target = resolution.get("subject_id") or observation["subject_id"]
            self.identities.declare(proposal.household_id, ExternalRef.from_value(external),
                                    target, proposal.id, actor)
        self.inbox.resolve(proposal.id, "confirmed", reason, actor)
        return tuple(confirmed)

    def reject(self, proposal_id: str, *, actor: str, reason: str) -> dict:
        return self.inbox.resolve(proposal_id, "rejected", reason, actor)


class ProvenanceService:
    """Rebuild the complete, immutable evidence-to-canonical explanation."""

    def __init__(self, log: EventLog):
        self.log = log

    def explain(self, canonical_event_id: str) -> dict[str, dict[str, Any]]:
        canonical = self.log.get(canonical_event_id)
        if canonical is None or not isinstance(canonical.get("payload"), dict):
            raise AcquisitionError("canonical event is unavailable")
        provenance = canonical["payload"].get("provenance")
        if not isinstance(provenance, dict):
            raise AcquisitionError("canonical event has no acquisition provenance")
        proposal_id, evidence_id = provenance.get("proposal_id"), provenance.get("evidence_id")
        if not isinstance(proposal_id, str) or not isinstance(evidence_id, str):
            raise AcquisitionError("canonical event provenance is incomplete")
        proposal = ProposalInbox(self.log).proposals.get(proposal_id)
        envelope = next((item for item in EnvelopeProjection(self.log).envelopes.values()
                         if item.id == (proposal.envelope_id if proposal else None)), None)
        confirmation = next((event for event in self.log.events()
                             if event["kind"] == "core.observation_proposal.updated" and
                             event["payload"].get("entity_id") == proposal_id and
                             event["payload"].get("resolution") == "confirmed"), None)
        if (proposal is None or envelope is None or envelope.payload_hash != evidence_id or
                confirmation is None):
            raise AcquisitionError("acquisition provenance chain is incomplete")
        if ((provenance.get("interpreter_id"), provenance.get("interpreter_version")) !=
                (proposal.interpreter_id, proposal.interpreter_version)):
            raise AcquisitionError("canonical interpreter provenance does not match proposal")
        return {
            "evidence": {"id": evidence_id, "envelope_id": envelope.id,
                         "source_identity": envelope.source_identity},
            "proposal": {"id": proposal.id},
            "interpreter": {"id": proposal.interpreter_id, "version": proposal.interpreter_version,
                            "class": proposal.interpreter_class},
            "confirmation": {"event_id": confirmation["id"], "actor": confirmation["payload"].get("resolved_by"),
                             "reason": confirmation["payload"].get("reason")},
            "canonical_event": {"id": canonical["id"], "kind": canonical["kind"],
                                "recorded_at": canonical["ts"]},
        }


@dataclass(frozen=True)
class CanonicalObservation:
    subject_id: str
    kind: str
    value: float | None
    unit: str | None
    valid_at: float
    observed_at: float
    received_at: float
    recorded_at: float
    evidence_grade: str
    stream_id: str
    provenance: dict[str, str]
    event_id: str


class CanonicalObservationProjection:
    """A bitemporal fold of confirmed domain observations only."""
    def __init__(self, log: EventLog, envelopes: EnvelopeProjection):
        self.log, self.envelopes = log, envelopes

    def observations(self, subject_id: str, *, valid_at: float, known_at: float) -> tuple[CanonicalObservation, ...]:
        result = []
        for event in self.log.events():
            if event["ts"] > known_at:
                continue
            payload, raw = event["payload"], event["payload"].get("observation")
            if not isinstance(raw, dict) or raw.get("subject_id") != subject_id:
                continue
            provenance = payload.get("provenance")
            if not isinstance(provenance, dict) or "proposal_id" not in provenance:
                continue
            proposal_evidence = provenance.get("evidence_id", "")
            received_at = next((item.received_at for item in self.envelopes.envelopes.values()
                                if item.payload_hash == proposal_evidence), event["ts"])
            try:
                observation = CanonicalObservation(
                    subject_id=raw["subject_id"], kind=raw["kind"], value=raw.get("value"),
                    unit=raw.get("unit"), valid_at=float(raw["valid_at"]),
                    observed_at=float(raw["observed_at"]), received_at=received_at,
                    recorded_at=float(event["ts"]), evidence_grade=raw["evidence_grade"],
                    stream_id=raw["stream_id"], provenance=dict(provenance), event_id=event["id"])
            except (KeyError, TypeError, ValueError):
                continue
            if observation.valid_at <= valid_at:
                result.append(observation)
        return tuple(sorted(result, key=lambda item: (item.valid_at, item.recorded_at, item.event_id)))

    def latest(self, subject_id: str, kind: str, *, valid_at: float, known_at: float) -> CanonicalObservation | None:
        values = [item for item in self.observations(subject_id, valid_at=valid_at, known_at=known_at)
                  if item.kind == kind]
        return values[-1] if values else None


@dataclass(frozen=True)
class Reconciliation:
    subject_id: str
    derived_total: float | None
    supplied_total: float | None
    difference: float | None
    provenance: tuple[str, ...]
    confidence: str


class ValuationLenses:
    """Pure derived market/accessibility/mission lenses; nothing here writes."""
    def __init__(self, registry: AssetRegistry, streams: TelemetryStreamRegistry,
                 observations: CanonicalObservationProjection):
        self.registry, self.streams, self.observations = registry, streams, observations

    def _holding_market(self, subject_id: str, valid_at: float, known_at: float) -> tuple[float | None, tuple[CanonicalObservation, ...]]:
        units = self.observations.latest(subject_id, "units", valid_at=valid_at, known_at=known_at)
        price = self.observations.latest(subject_id, "price", valid_at=valid_at, known_at=known_at)
        if units is None or price is None or units.value is None or price.value is None:
            return None, tuple(item for item in (units, price) if item is not None)
        return units.value * price.value, (units, price)

    def market_value(self, subject_id: str, *, valid_at: float, known_at: float) -> dict[str, Any]:
        children = self.registry.children_of(subject_id)
        if children:
            parts = [self.market_value(child, valid_at=valid_at, known_at=known_at) for child in children]
            values = [part["value"] for part in parts]
            observations = tuple(item for part in parts for item in part["inputs"])
        else:
            value, observations = self._holding_market(subject_id, valid_at, known_at)
            values = [value]
        grades = [item.evidence_grade for item in observations]
        value = None if any(item is None for item in values) else sum(values)
        return {"value": value, "inputs": observations,
                "confidence": confidence_cap(grades) if value is not None and grades else "Insufficient",
                "basis": "market"}

    def reconciliation(self, container_id: str, *, valid_at: float, known_at: float) -> Reconciliation:
        market = self.market_value(container_id, valid_at=valid_at, known_at=known_at)
        supplied = self.observations.latest(container_id, "statement_total", valid_at=valid_at, known_at=known_at)
        supplied_total = supplied.value if supplied else None
        difference = (market["value"] - supplied_total
                      if market["value"] is not None and supplied_total is not None else None)
        inputs = market["inputs"] + ((supplied,) if supplied else ())
        return Reconciliation(container_id, market["value"], supplied_total, difference,
                              tuple(item.event_id for item in inputs),
                              confidence_cap([item.evidence_grade for item in inputs])
                              if market["value"] is not None and supplied is not None else "Insufficient")

    def stream_freshness(self, stream_id: str, *, as_of: float, known_at: float) -> str:
        stream = self.streams.streams.get(stream_id)
        if stream is None:
            return "unavailable"
        if stream.refresh_policy in {"static", "on_event"}:
            return "available"
        values = self.observations.observations(stream.subject_id, valid_at=as_of, known_at=known_at)
        values = [value for value in values if value.stream_id == stream_id]
        if not values:
            return "unavailable"
        latest = max(values, key=lambda value: value.received_at)
        return "stale" if as_of - latest.received_at > _CADENCE_SECONDS[stream.refresh_policy] else "available"

    def accessibility_value(self, subject_id: str, *, valid_at: float, known_at: float,
                            profile: dict[str, Any], conditions: dict[str, dict[str, Any]],
                            horizon: float | None = None) -> dict[str, Any]:
        market = self.market_value(subject_id, valid_at=valid_at, known_at=known_at)
        fraction = 0.0
        for component in profile.get("components", []):
            condition = component.get("condition")
            if condition not in vocab.ACCESSIBILITY_CONDITION:
                raise AcquisitionError("unknown accessibility condition")
            if condition == "none":
                fraction += float(component.get("portion", 0))
                continue
            state = conditions.get(component.get("condition_ref"), {}).get("state", "pending")
            earliest = component.get("earliest_at")
            eligible = state == "satisfied" or (horizon is not None and earliest is not None and earliest <= horizon)
            if eligible:
                fraction += float(component.get("portion", 0))
        value = (market["value"] * min(1.0, fraction)
                 if market["value"] is not None else None)
        return {"value": value, "basis": "accessibility",
                "confidence": market["confidence"], "inputs": market["inputs"]}

    def mission_value(self, subject_id: str, *, valid_at: float, known_at: float,
                      profile: dict[str, Any], conditions: dict[str, dict[str, Any]],
                      horizon: float | None, policy: Callable[[float, str], float]) -> dict[str, Any]:
        accessible = self.accessibility_value(subject_id, valid_at=valid_at, known_at=known_at,
                                              profile=profile, conditions=conditions, horizon=horizon)
        value = (policy(accessible["value"], accessible["confidence"])
                 if accessible["value"] is not None else None)
        return {**accessible, "value": value,
                "basis": "mission"}

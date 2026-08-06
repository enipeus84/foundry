"""RFC-015 Phase 2: replayable, failure-isolated target bootstrap."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import NAMESPACE_URL, uuid5

from foundry.core.acquisition import AcquisitionError, AssetRegistration, AssetRegistry, TelemetryStream, TelemetryStreamRegistry
from foundry.core.entities import EntityProjection
from foundry.eventlog import EventLog
from foundry.finance.capture_targets import FinanceCaptureTargetResolver
from foundry.finance.entities import FinanceEntityProjection
from foundry.finance.mortgage_evidence import MortgageEvidenceProjection


@dataclass(frozen=True)
class BootstrapDiagnostic:
    entity: str
    validation: str
    reason: str


@dataclass(frozen=True)
class CaptureTargetBootstrapResult:
    entities_examined: int = 0
    asset_registrations_created: int = 0
    telemetry_streams_created: int = 0
    existing_declarations_retained: int = 0
    ineligible_entities_skipped: int = 0
    ambiguous_entities_rejected: int = 0
    conflicts_detected: int = 0
    diagnostics: tuple[BootstrapDiagnostic, ...] = ()


def stream_identity(household_id: str, subject_id: str, property_name: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"foundry:rfc-015:{household_id}:{subject_id}:{property_name}"))


@dataclass(frozen=True)
class _Declaration:
    registration: AssetRegistration | None
    stream: TelemetryStream | None


class FinanceCaptureTargetBootstrap:
    """Discover canonical targets; one bad entity must not stop the others."""

    def __init__(self, log: EventLog, household_id: str, *, actor: str = "runtime_bootstrap"):
        self.log, self.household_id, self.actor = log, household_id, actor
        self.diagnostics: list[BootstrapDiagnostic] = []
        self._primary_residence_id: str | None = None
        self._primary_residence_checked = False
        self.core = self._tolerant_projection(EntityProjection)
        self.finance = self._tolerant_projection(FinanceEntityProjection)
        self.resolver = FinanceCaptureTargetResolver(self.finance)
        self.assets = AssetRegistry(log, entity_exists=lambda subject: self.resolver.resolve(subject) is not None)
        self.streams = TelemetryStreamRegistry(log)

    def _tolerant_projection(self, projection_type):
        """Fold each canonical event independently.

        A malformed ordinary event is not made authoritative merely because it
        reached history.  The rest of the projection remains usable and the
        bad event is recorded as a bootstrap diagnostic below.
        """
        projection = projection_type.empty(self.log)
        for event in self.log.events():
            try:
                projection.apply(event)
            except (KeyError, TypeError, ValueError) as exc:
                payload = event.get("payload", {})
                entity = payload.get("entity_id") if isinstance(payload, dict) else None
                self.diagnostics.append(BootstrapDiagnostic(
                    entity if isinstance(entity, str) and entity else event.get("id", "unknown"),
                    "canonical projection", str(exc) or exc.__class__.__name__))
        return projection

    def _members(self) -> set[str]:
        household = self.core.parties.get(self.household_id)
        if household is None or household.party_type != "household" or household.status != "active":
            self.diagnostics.append(BootstrapDiagnostic(
                self.household_id, "household", "not an active canonical household"))
            return set()
        return {member.id for member in self.core.members_of(self.household_id) if member.status == "active"}

    @staticmethod
    def _owned(entity, members: set[str]) -> bool:
        owners = {link.target for link in entity.ownership if link.relation in {"owner", "co_owner", "beneficial_owner"}}
        return bool(owners) and owners <= members

    def _primary_residence(self, members: set[str]) -> str | None:
        if self._primary_residence_checked:
            return self._primary_residence_id
        self._primary_residence_checked = True
        evidence, candidates = MortgageEvidenceProjection(self.log), set()
        as_of = max((event["ts"] for event in self.log.events()), default=0.0) + 1
        for mortgage in self.finance.obligations.values():
            borrowers = {link.target for link in mortgage.ownership if link.relation == "owes"}
            secured = {link.target for link in mortgage.ownership if link.relation == "secures"}
            if (mortgage.status != "active" or mortgage.liability_category != "mortgage" or not borrowers
                    or not borrowers <= members or len(secured) != 1):
                continue
            asset = self.finance.assets.get(next(iter(secured)))
            role = evidence.latest(mortgage.id, "property_role", as_of)
            if (asset and asset.status == "active" and asset.asset_category == "property"
                    and self._owned(asset, members) and role and role.value == "primary_residence"):
                candidates.add(asset.id)
        if len(candidates) > 1:
            self.diagnostics.append(BootstrapDiagnostic(
                self.household_id, "primary residence", "multiple canonical primary residences"))
            return None
        self._primary_residence_id = next(iter(candidates), None)
        return self._primary_residence_id

    def _expected_stream(self, subject_id: str, property_name: str, currency: str) -> TelemetryStream:
        return TelemetryStream(stream_identity(self.household_id, subject_id, property_name), subject_id, property_name,
                               "manual", "annual", "review_each", "runtime_bootstrap", currency, "numeric",
                               self.household_id, "annual")

    def _validate_target(self, subject_id: str, property_name: str, currency: str, result: dict[str, int]) -> _Declaration:
        expected_registration = AssetRegistration(subject_id, "finance", self.household_id)
        registration = self.assets.registrations.get(subject_id)
        if registration is not None and (registration.domain != "finance" or registration.household_id != self.household_id
                                         or registration.lifecycle_state != "active"):
            raise AcquisitionError("conflicting household or lifecycle")
        expected_stream = self._expected_stream(subject_id, property_name, currency)
        identified = self.streams.streams.get(expected_stream.id)
        if identified is not None and identified != expected_stream:
            raise AcquisitionError("deterministic stream identity collision")
        same = [stream for stream in self.streams.streams.values()
                if (stream.household_id, stream.subject_id, stream.property) ==
                (self.household_id, subject_id, property_name)]
        fields = ("subject_id", "property", "channel", "refresh_policy", "confirmation_policy",
                  "unit_or_currency", "validation_contract", "household_id", "expected_cadence")
        if len(same) > 1 or (same and any(getattr(same[0], field) != getattr(expected_stream, field) for field in fields)):
            raise AcquisitionError("conflicting active capture target")
        result["existing_declarations_retained"] += int(registration is not None) + int(bool(same))
        return _Declaration(None if registration else expected_registration, None if same else expected_stream)

    def plan(self) -> tuple[tuple[_Declaration, ...], CaptureTargetBootstrapResult]:
        members, result, declarations = self._members(), {name: 0 for name in CaptureTargetBootstrapResult.__dataclass_fields__ if name != "diagnostics"}, []
        if not members:
            return (), CaptureTargetBootstrapResult(**result, diagnostics=tuple(self.diagnostics))
        result["entities_examined"] = len(self.finance.accounts) + len(self.finance.assets)
        # Eligibility is a resolver-owned canonical type/property table, not
        # a display-name or seed-data convention.
        entities = tuple(self.finance.accounts.values()) + tuple(self.finance.assets.values())
        for entity in entities:
            descriptor = self.resolver.resolve(entity.id)
            if descriptor is None or entity.status != "active" or not self._owned(entity, members):
                result["ineligible_entities_skipped"] += 1
                continue
            properties = self.resolver.bootstrap_properties(descriptor)
            if descriptor.entity_type == "asset:property" and entity.id != self._primary_residence(members):
                properties = ()
            if not properties:
                result["ineligible_entities_skipped"] += 1
                continue
            for property_name in properties:
                try:
                    declarations.append(self._validate_target(entity.id, property_name, entity.currency, result))
                except AcquisitionError as exc:
                    result["conflicts_detected"] += 1
                    self.diagnostics.append(BootstrapDiagnostic(entity.id, "capture target", str(exc)))
        return tuple(declarations), CaptureTargetBootstrapResult(**result, diagnostics=tuple(self.diagnostics))

    def _append_diagnostics(self, diagnostics: tuple[BootstrapDiagnostic, ...]) -> None:
        existing = {
            (event["payload"].get("household_id"), event["payload"].get("entity"),
             event["payload"].get("validation"), event["payload"].get("reason"))
            for event in self.log.events()
            if event["kind"] == "core.capture_target_bootstrap.diagnostic"
        }
        for diagnostic in diagnostics:
            payload = {"household_id": self.household_id, "entity": diagnostic.entity,
                       "validation": diagnostic.validation, "reason": diagnostic.reason}
            if tuple(payload[key] for key in ("household_id", "entity", "validation", "reason")) not in existing:
                self.log.append("core.capture_target_bootstrap.diagnostic", payload, actor=self.actor)

    def run(self) -> CaptureTargetBootstrapResult:
        declarations, result = self.plan()
        self._append_diagnostics(result.diagnostics)
        for declaration in declarations:
            if declaration.registration:
                self.assets.register(declaration.registration, actor=self.actor)
            if declaration.stream:
                # Registration is already present or was appended in the prior loop iteration.
                TelemetryStreamRegistry(self.log).declare(declaration.stream, actor=self.actor)
        return CaptureTargetBootstrapResult(
            **{**result.__dict__,
               "asset_registrations_created": sum(item.registration is not None for item in declarations),
               "telemetry_streams_created": sum(item.stream is not None for item in declarations)})


def bootstrap_finance_capture_targets(log: EventLog, household_id: str, *, actor: str = "runtime_bootstrap") -> CaptureTargetBootstrapResult:
    return FinanceCaptureTargetBootstrap(log, household_id, actor=actor).run()

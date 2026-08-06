"""RFC-015 Phase 2A: validated, failure-isolated runtime target bootstrap."""

from __future__ import annotations

from dataclasses import dataclass, field
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


class CaptureTargetBootstrapError(AcquisitionError):
    def __init__(self, entity: str, validation: str, reason: str):
        super().__init__(reason)
        self.diagnostic = BootstrapDiagnostic(entity, validation, reason)


def stream_identity(household_id: str, subject_id: str, property_name: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"foundry:rfc-015:{household_id}:{subject_id}:{property_name}"))


@dataclass(frozen=True)
class _Declaration:
    registration: AssetRegistration | None
    stream: TelemetryStream | None


class FinanceCaptureTargetBootstrap:
    """Plan every declaration before appending any of them."""

    def __init__(self, log: EventLog, household_id: str, *, actor: str = "runtime_bootstrap"):
        self.log, self.household_id, self.actor = log, household_id, actor
        self.core, self.finance = EntityProjection(log), FinanceEntityProjection(log)
        self.resolver = FinanceCaptureTargetResolver(self.finance)
        self.assets = AssetRegistry(log, entity_exists=lambda subject: self.resolver.resolve(subject) is not None)
        self.streams = TelemetryStreamRegistry(log)

    def _members(self) -> set[str]:
        household = self.core.parties.get(self.household_id)
        if household is None or household.party_type != "household" or household.status != "active":
            raise CaptureTargetBootstrapError(self.household_id, "household", "not an active canonical household")
        return {member.id for member in self.core.members_of(self.household_id) if member.status == "active"}

    @staticmethod
    def _owned(entity, members: set[str]) -> bool:
        owners = {link.target for link in entity.ownership if link.relation in {"owner", "co_owner", "beneficial_owner"}}
        return bool(owners) and owners <= members

    def _primary_residence(self, members: set[str]) -> str | None:
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
            raise CaptureTargetBootstrapError("primary residence", "uniqueness", "multiple canonical primary residences")
        return next(iter(candidates), None)

    def _expected_stream(self, subject_id: str, property_name: str, currency: str) -> TelemetryStream:
        return TelemetryStream(stream_identity(self.household_id, subject_id, property_name), subject_id, property_name,
                               "manual", "annual", "review_each", "runtime_bootstrap", currency, "numeric",
                               self.household_id, "annual")

    def _validate_target(self, subject_id: str, property_name: str, currency: str, result: dict[str, int]) -> _Declaration:
        expected_registration = AssetRegistration(subject_id, "finance", self.household_id)
        registration = self.assets.registrations.get(subject_id)
        if registration is not None and (registration.domain != "finance" or registration.household_id != self.household_id
                                         or registration.lifecycle_state != "active"):
            result["conflicts_detected"] += 1
            raise CaptureTargetBootstrapError(subject_id, "asset registration", "conflicting household or lifecycle")
        expected_stream = self._expected_stream(subject_id, property_name, currency)
        same = [stream for stream in self.streams.streams.values()
                if (stream.household_id, stream.subject_id, stream.property) ==
                (self.household_id, subject_id, property_name)]
        fields = ("subject_id", "property", "channel", "refresh_policy", "confirmation_policy",
                  "unit_or_currency", "validation_contract", "household_id", "expected_cadence")
        if len(same) > 1 or (same and any(getattr(same[0], field) != getattr(expected_stream, field) for field in fields)):
            result["conflicts_detected"] += 1
            raise CaptureTargetBootstrapError(subject_id, "telemetry declaration", "conflicting active capture target")
        result["existing_declarations_retained"] += int(registration is not None) + int(bool(same))
        return _Declaration(None if registration else expected_registration, None if same else expected_stream)

    def plan(self) -> tuple[tuple[_Declaration, ...], CaptureTargetBootstrapResult]:
        members, result, declarations = self._members(), {name: 0 for name in CaptureTargetBootstrapResult.__dataclass_fields__ if name != "diagnostics"}, []
        result["entities_examined"] = len(self.finance.accounts) + len(self.finance.assets)
        for account in self.finance.accounts.values():
            if account.status != "active" or not self._owned(account, members):
                result["ineligible_entities_skipped"] += 1
            elif account.account_type == "pension":
                declarations.append(self._validate_target(account.id, "pension_balance", account.currency, result))
            elif account.account_type in {"checking", "savings"}:
                declarations.append(self._validate_target(account.id, "cash_balance", account.currency, result))
            else:
                result["ineligible_entities_skipped"] += 1
        primary = self._primary_residence(members)
        if primary is None:
            result["ineligible_entities_skipped"] += 1
        else:
            asset = self.finance.assets[primary]
            declarations.append(self._validate_target(asset.id, "property_valuation", asset.currency, result))
        return tuple(declarations), CaptureTargetBootstrapResult(**result)

    def run(self) -> CaptureTargetBootstrapResult:
        declarations, result = self.plan()  # A3: this completes before the first append.
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

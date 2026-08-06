"""RFC-015 Phase 2 runtime declarations for already-canonical Finance entities."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import NAMESPACE_URL, uuid5

from foundry.core.acquisition import AcquisitionError, AssetRegistration, TelemetryStream
from foundry.core.capture_targets import CaptureTargetRegistry
from foundry.core.entities import EntityProjection
from foundry.eventlog import EventLog
from foundry.finance.capture_targets import FinanceCaptureTargetResolver
from foundry.finance.entities import FinanceEntityProjection
from foundry.finance.mortgage_evidence import MortgageEvidenceProjection


@dataclass(frozen=True)
class CaptureTargetBootstrapResult:
    entities_examined: int = 0
    asset_registrations_created: int = 0
    telemetry_streams_created: int = 0
    existing_declarations_retained: int = 0
    ineligible_entities_skipped: int = 0
    ambiguous_entities_rejected: int = 0
    conflicts_detected: int = 0


class CaptureTargetBootstrapError(AcquisitionError):
    """Canonical runtime state cannot safely be made captureable."""


def stream_identity(household_id: str, subject_id: str, property_name: str) -> str:
    """Stable, household-scoped identity; names and process state never participate."""
    return str(uuid5(NAMESPACE_URL, f"foundry:rfc-015:{household_id}:{subject_id}:{property_name}"))


class FinanceCaptureTargetBootstrap:
    """Resolve household Finance state, then append only missing Core declarations."""

    def __init__(self, log: EventLog, household_id: str, *, actor: str = "runtime_bootstrap"):
        self.log, self.household_id, self.actor = log, household_id, actor
        self.core = EntityProjection(log)
        self.finance = FinanceEntityProjection(log)
        self.resolver = FinanceCaptureTargetResolver(self.finance)
        self.targets = CaptureTargetRegistry(log, self.resolver)

    def _member_ids(self) -> set[str]:
        household = self.core.parties.get(self.household_id)
        if household is None or household.party_type != "household" or household.status != "active":
            raise CaptureTargetBootstrapError("bootstrap household is not an active canonical household")
        return {member.id for member in self.core.members_of(self.household_id) if member.status == "active"}

    @staticmethod
    def _owned_by_members(entity, members: set[str]) -> bool:
        owners = {link.target for link in entity.ownership
                  if link.relation in {"owner", "co_owner", "beneficial_owner"}}
        return bool(owners) and owners <= members

    def _primary_residence(self, members: set[str]) -> tuple[str | None, bool]:
        evidence = MortgageEvidenceProjection(self.log)
        as_of = max((event["ts"] for event in self.log.events()), default=0.0) + 1.0
        candidates: set[str] = set()
        for obligation in self.finance.obligations.values():
            if obligation.status != "active" or obligation.liability_category != "mortgage":
                continue
            borrowers = {link.target for link in obligation.ownership if link.relation == "owes"}
            secured = {link.target for link in obligation.ownership if link.relation == "secures"}
            if not borrowers or not borrowers <= members or len(secured) != 1:
                continue
            asset = self.finance.assets.get(next(iter(secured)))
            role = evidence.latest(obligation.id, "property_role", as_of)
            if (asset is not None and asset.status == "active" and asset.asset_category == "property"
                    and self._owned_by_members(asset, members) and role is not None
                    and role.value == "primary_residence"):
                candidates.add(asset.id)
        if len(candidates) != 1:
            return None, bool(candidates)
        return next(iter(candidates)), False

    @staticmethod
    def _stream(subject_id: str, household_id: str, property_name: str, currency: str) -> TelemetryStream:
        return TelemetryStream(
            id=stream_identity(household_id, subject_id, property_name), subject_id=subject_id,
            property=property_name, channel="manual", refresh_policy="annual",
            confirmation_policy="review_each", source_identity="runtime_bootstrap",
            unit_or_currency=currency, validation_contract="numeric", household_id=household_id,
            expected_cadence="annual",
        )

    def _ensure(self, subject_id: str, property_name: str, currency: str, result: dict[str, int]) -> None:
        registration = self.targets.assets.registrations.get(subject_id)
        expected_registration = AssetRegistration(subject_id, "finance", self.household_id)
        if registration is None:
            self.targets.assets.register(expected_registration, actor=self.actor)
            result["asset_registrations_created"] += 1
            self.targets.rebuild()
        elif (registration.domain != expected_registration.domain
              or registration.household_id != expected_registration.household_id
              or registration.lifecycle_state != expected_registration.lifecycle_state):
            result["conflicts_detected"] += 1
            raise CaptureTargetBootstrapError(f"conflicting asset registration for {subject_id}")
        else:
            result["existing_declarations_retained"] += 1
        expected_stream = self._stream(subject_id, self.household_id, property_name, currency)
        same_target = [stream for stream in self.targets.streams.streams.values()
                       if (stream.household_id, stream.subject_id, stream.property) ==
                       (self.household_id, subject_id, property_name)]
        if not same_target:
            self.targets.declare(expected_stream, actor=self.actor)
            result["telemetry_streams_created"] += 1
        elif len(same_target) != 1 or any(
                getattr(same_target[0], field) != getattr(expected_stream, field)
                for field in ("subject_id", "property", "channel", "refresh_policy",
                              "confirmation_policy", "unit_or_currency", "validation_contract",
                              "household_id", "expected_cadence")):
            result["conflicts_detected"] += 1
            raise CaptureTargetBootstrapError(f"conflicting telemetry declaration for {subject_id}:{property_name}")
        else:
            result["existing_declarations_retained"] += 1

    def run(self) -> CaptureTargetBootstrapResult:
        members = self._member_ids()
        result = {field: 0 for field in CaptureTargetBootstrapResult.__dataclass_fields__}
        accounts = tuple(self.finance.accounts.values())
        assets = tuple(self.finance.assets.values())
        result["entities_examined"] = len(accounts) + len(assets)
        for account in accounts:
            if account.status != "active" or not self._owned_by_members(account, members):
                result["ineligible_entities_skipped"] += 1
                continue
            if account.account_type == "pension":
                self._ensure(account.id, "pension_balance", account.currency, result)
            elif account.account_type in {"checking", "savings"}:
                self._ensure(account.id, "cash_balance", account.currency, result)
            else:
                result["ineligible_entities_skipped"] += 1
        primary_residence, ambiguous = self._primary_residence(members)
        if ambiguous:
            result["ambiguous_entities_rejected"] += 1
            raise CaptureTargetBootstrapError("primary residence is ambiguous in canonical Finance state")
        if primary_residence is None:
            result["ineligible_entities_skipped"] += 1
        else:
            asset = self.finance.assets[primary_residence]
            self._ensure(asset.id, "property_valuation", asset.currency, result)
        return CaptureTargetBootstrapResult(**result)


def bootstrap_finance_capture_targets(log: EventLog, household_id: str, *, actor: str = "runtime_bootstrap") -> CaptureTargetBootstrapResult:
    return FinanceCaptureTargetBootstrap(log, household_id, actor=actor).run()

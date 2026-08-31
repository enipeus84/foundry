"""Household-scoped financial-resource queries for trusted adapters."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import json
from typing import Any
from zoneinfo import ZoneInfo

from foundry.capture_contracts import CaptureContractRegistry, capture_contract_registry
from foundry.core.acquisition import AssetRegistry, AssetRegistration, AcquisitionError
from foundry.core.capture_targets import CaptureTargetRegistry
from foundry.core import grammar
from foundry.core.entities import EntityProjection
from foundry.core.principal_authority import PrincipalHouseholdAuthority
from foundry.eventlog import EventLog
from foundry.finance.capture_targets import FinanceCaptureTargetResolver, finance_asset_registry
from foundry.finance import entities as finance_entities
from foundry.finance import vocab as finance_vocab
from foundry.finance.entities import Account, Asset, Obligation, FinanceEntityProjection
from foundry.finance.runtime_bootstrap import bootstrap_finance_capture_targets


class ResourceNotFound(LookupError):
    """The subject is absent or outside the authorised household."""


class ResourceCommandDenied(PermissionError):
    """A resource command failed its household or domain authority checks."""


_RESOURCE_TYPES = {
    "cash": ("account", "checking", "none"), "checking": ("account", "checking", "none"),
    "savings": ("account", "savings", "none"), "isa": ("account", "brokerage", "isa"),
    "brokerage": ("account", "brokerage", "none"), "pension": ("account", "pension", "pension_wrapper"),
    "credit_card": ("account", "credit_card", "none"), "loan": ("account", "loan", "none"),
    "mortgage": ("obligation", "mortgage", None), "other": ("account", "other", "none"),
    "property": ("asset", "property", None), "vehicle": ("asset", "vehicle", None),
    "collectible": ("asset", "collectible", None),
}

_LONDON = ZoneInfo("Europe/London")
_CURRENCY_SYMBOLS = {"GBP": "£", "EUR": "€", "USD": "$"}


def _command_digest(values: dict[str, Any]) -> str:
    return sha256(json.dumps(values, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _resource_update_state_digest(resource: dict[str, Any]) -> str:
    """Digest the canonical resource state relevant to a governed amendment.

    Valuations deliberately do not participate: a metadata amendment must not
    become a valuation write, and an intervening valuation does not change the
    resource classification being reviewed. Resource history, lifecycle,
    ownership and the mutable fields do participate, so an intervening resource
    amendment cannot silently satisfy an earlier proposal.
    """
    return _command_digest({
        "id": resource["id"],
        "resource_kind": resource["resource_kind"],
        "resource_type": resource["resource_type"],
        "name": resource["name"],
        "liquidity_classification": resource["liquidity_classification"],
        "status": resource["status"],
        "ownership": sorted(resource["ownership"], key=lambda value: (
            value["relation"], value["subject_id"], value.get("share", -1))),
        "history_event_ids": resource["provenance"]["history_event_ids"],
    })


def financial_resource_update_command_digest(
        household_id: str, resource_id: str, name: str | None,
        liquidity_classification: str | None, reason: str,
        principal: str | None) -> str:
    """Stable idempotency key material, deliberately excluding state.

    The state digest belongs to the proposal receipt. Including it here would
    make a successful replay appear different after the update itself changed
    the resource history.
    """
    return _command_digest({
        "operation": "update_financial_resource", "household_id": household_id,
        "resource_id": resource_id, "name": name,
        "liquidity_classification": liquidity_classification,
        "reason": reason, "principal": principal,
    })


class FinancialResourceCommandService:
    """Canonical application commands shared by web and MCP adapters."""

    def __init__(self, log: EventLog):
        self.log = log

    def _members(self, household_id: str):
        core = EntityProjection(self.log)
        household = core.parties.get(household_id)
        if household is None or household.party_type != "household" or household.status != "active":
            raise ResourceCommandDenied("household is unavailable")
        return tuple(member for member in core.members_of(household_id) if member.status == "active")

    def _owner_ids(self, household_id: str, owner: str | None,
                   owners: list[str] | None) -> list[str]:
        members = self._members(household_id)
        requested = owners or ([owner] if owner is not None else [])
        if not requested:
            raise ResourceCommandDenied("an explicit household member owner is required")
        resolved: list[str] = []
        for value in requested:
            matches = [member for member in members if value == member.id or value.casefold() in {
                str(member.attributes.get("name", "")).casefold(),
                str(member.attributes.get("display_name", "")).casefold(),
            }]
            if len(matches) != 1:
                raise ResourceCommandDenied("owner must resolve to exactly one active household member")
            resolved.append(matches[0].id)
        if len(set(resolved)) != len(resolved):
            raise ResourceCommandDenied("owners must be distinct")
        return resolved

    def _authorise(self, principal: str | None, household_id: str, required: bool) -> None:
        if required and (not principal or not PrincipalHouseholdAuthority(self.log).permits_write(principal, household_id)):
            raise ResourceCommandDenied("principal is not authorised to mutate this household")

    def _audit_replay(self, command_id: str, digest: str, household_id: str) -> dict[str, Any] | None:
        for event in self.log.events():
            if event["kind"] != "application.mcp_command.executed":
                continue
            payload = event["payload"]
            if payload.get("household_id") != household_id:
                continue
            if payload.get("command_id") != command_id:
                continue
            if payload.get("request_digest") != digest:
                raise ResourceCommandDenied("command id was already used for a different request")
            return self.get_financial_resource(household_id, payload["resource_id"])
        return None

    def create_financial_resource(self, *, household_id: str, resource_type: str,
                                  currency: str, name: str | None = None,
                                  provider: str | None = None, owner: str | None = None,
                                  owners: list[str] | None = None,
                                  liquidity_classification: str | None = None,
                                  projection_authority: str | None = None,
                                  secured_property_id: str | None = None,
                                  actor: str, principal: str | None = None,
                                  command_id: str | None = None,
                                  client: str | None = None, witness_model: str | None = None,
                                  require_authority: bool = True) -> dict[str, Any]:
        values = {"household_id": household_id, "resource_type": resource_type,
                  "currency": currency, "name": name, "provider": provider,
                  "owner": owner, "owners": owners,
                  "liquidity_classification": liquidity_classification,
                  "projection_authority": projection_authority,
                  "secured_property_id": secured_property_id}
        digest = _command_digest(values)
        self._authorise(principal, household_id, require_authority)
        if command_id:
            replay = self._audit_replay(command_id, digest, household_id)
            if replay is not None:
                return replay
        if resource_type not in _RESOURCE_TYPES:
            raise ResourceCommandDenied("unsupported financial resource type")
        if not isinstance(currency, str) or len(currency) != 3 or not currency.isalpha():
            raise ResourceCommandDenied("currency must be a three-letter code")
        display_name = (name or provider or "").strip()
        if not display_name:
            raise ResourceCommandDenied("name or provider is required")
        owner_ids = self._owner_ids(household_id, owner, owners)
        entity_kind, finance_type, tax_wrapper = _RESOURCE_TYPES[resource_type]
        if resource_type == "mortgage":
            if not secured_property_id:
                raise ResourceCommandDenied("an active household property is required to secure a mortgage")
            try:
                property_resource = self.get_financial_resource(household_id, secured_property_id)
            except ResourceNotFound as exc:
                raise ResourceCommandDenied("secured property is unavailable") from exc
            if (property_resource["resource_kind"] != "asset"
                    or property_resource["resource_type"] != "property"
                    or property_resource["status"] != "active"):
                raise ResourceCommandDenied("secured property must be an active property asset")
            if property_resource["currency"] != currency.upper():
                raise ResourceCommandDenied("secured property currency must match the mortgage currency")
            property_owners = {
                link["subject_id"] for link in property_resource["ownership"]
                if link["relation"] in {"owner", "co_owner"}
            }
            if not property_owners or not property_owners <= set(owner_ids):
                raise ResourceCommandDenied("secured property owners must be mortgage borrowers")
        elif secured_property_id is not None:
            raise ResourceCommandDenied("secured property applies only to mortgage resources")
        if projection_authority is not None and finance_type != "pension":
            raise ResourceCommandDenied("projection authority applies only to pension resources")
        try:
            resource = (finance_entities.declare_account(
                self.log, finance_type, currency.upper(), name=display_name,
                tax_wrapper=tax_wrapper or "none", liquidity_classification=liquidity_classification,
                    projection_authority=projection_authority,
                provider_name=(provider.strip() or None) if provider else None,
                actor=actor) if entity_kind == "account" else finance_entities.declare_asset(
                    self.log, finance_type, currency.upper(), name=display_name,
                    liquidity_classification=liquidity_classification, actor=actor)
                if entity_kind == "asset" else finance_entities.declare_obligation(
                    self.log, finance_type, currency.upper(), actor=actor))
            relation = ("owes" if entity_kind == "obligation" else
                        "owner" if len(owner_ids) == 1 else "co_owner")
            share = None if relation in {"owner", "owes"} else 100.0 / len(owner_ids)
            for owner_id in owner_ids:
                finance_entities.link_ownership(self.log, entity_kind, resource.id, relation,
                                                owner_id, share=share, actor=actor)
            if entity_kind == "obligation":
                finance_entities.link_ownership(
                    self.log, "obligation", resource.id, "secures", secured_property_id, actor=actor)
            finance_asset_registry(self.log).register(
                AssetRegistration(resource.id, "finance", household_id), actor=actor)
            bootstrap_finance_capture_targets(self.log, household_id, actor=actor)
        except (AcquisitionError, TypeError, ValueError) as exc:
            raise ResourceCommandDenied(str(exc)) from exc
        if command_id:
            self.log.append("application.mcp_command.executed", {
                "operation": "create_financial_resource", "command_id": command_id,
                "request_digest": digest, "household_id": household_id,
                "resource_id": resource.id, "principal": principal,
                "client": client, "witness_model": witness_model,
            }, actor=actor)
        return self.get_financial_resource(household_id, resource.id)

    def prepare_financial_resource_update(
            self, *, household_id: str, resource_id: str, name: str | None,
            liquidity_classification: str | None, reason: str,
            principal: str | None = None, require_authority: bool = True) -> dict[str, Any]:
        """Validate an admissible resource amendment against fresh state.

        This is intentionally shared by proposal and execution. The returned
        request includes a state digest, making a proposal a receipt for one
        particular canonical resource state rather than merely for a set of
        caller-supplied strings.
        """
        self._authorise(principal, household_id, require_authority)
        resource = self.get_financial_resource(household_id, resource_id)
        if resource["resource_kind"] == "obligation":
            raise ResourceCommandDenied("obligation metadata cannot be updated as a financial resource")
        if resource["status"] != "active":
            raise ResourceCommandDenied("an inactive resource cannot be updated")
        if not isinstance(reason, str) or not reason.strip():
            raise ResourceCommandDenied("a reason is required for a resource update")

        changes: dict[str, str] = {}
        if name is not None:
            if not isinstance(name, str) or not name.strip():
                raise ResourceCommandDenied("display name cannot be empty")
            changes["name"] = name.strip()
        if liquidity_classification is not None:
            if (not isinstance(liquidity_classification, str)
                    or liquidity_classification not in finance_vocab.LIQUIDITY_CLASSIFICATION):
                raise ResourceCommandDenied("invalid liquidity_classification")
            changes["liquidity_classification"] = liquidity_classification
        if not changes:
            raise ResourceCommandDenied("a resource update requires a supported change")
        if all(resource[field] == value for field, value in changes.items()):
            raise ResourceCommandDenied("resource update is already current")

        return {
            "operation": "update_financial_resource", "household_id": household_id,
            "resource_id": resource_id, "name": changes.get("name"),
            "liquidity_classification": changes.get("liquidity_classification"),
            "reason": reason.strip(), "principal": principal,
            "state_digest": _resource_update_state_digest(resource),
        }

    def update_financial_resource(self, *, household_id: str, resource_id: str,
                                  name: str | None = None,
                                  liquidity_classification: str | None = None,
                                  reason: str, actor: str,
                                  principal: str | None = None, command_id: str | None = None,
                                  client: str | None = None, witness_model: str | None = None,
                                  require_authority: bool = True,
                                  expected_state_digest: str | None = None) -> dict[str, Any]:
        if not isinstance(command_id, str) or not command_id.strip():
            raise ResourceCommandDenied("command_id is required for idempotent execution")
        self._authorise(principal, household_id, require_authority)
        digest = financial_resource_update_command_digest(
            household_id, resource_id, name, liquidity_classification, reason, principal)
        replay = self._audit_replay(command_id, digest, household_id)
        if replay is not None:
            return replay
        request = self.prepare_financial_resource_update(
            household_id=household_id, resource_id=resource_id, name=name,
            liquidity_classification=liquidity_classification, reason=reason,
            principal=principal, require_authority=False)
        if (not isinstance(expected_state_digest, str)
                or request["state_digest"] != expected_state_digest):
            raise ResourceCommandDenied("resource update proposal is stale against canonical state")
        changes = {field: request[field] for field in ("name", "liquidity_classification")
                   if request[field] is not None}
        grammar.update(self.log, "finance", self.get_financial_resource(
            household_id, resource_id)["resource_kind"], resource_id,
            changes, request["reason"], actor=actor)
        self.log.append("application.mcp_command.executed", {
            "operation": "update_financial_resource", "command_id": command_id,
            "request_digest": digest, "household_id": household_id,
            "resource_id": resource_id, "principal": principal,
            "client": client, "witness_model": witness_model,
        }, actor=actor)
        return self.get_financial_resource(household_id, resource_id)

    def declare_pension_projection_authority(self, *, household_id: str, resource_id: str,
                                             projection_authority: str, reason: str, actor: str,
                                             provider_name: str | None = None,
                                             principal: str | None = None,
                                             command_id: str | None = None,
                                             client: str | None = None,
                                             witness_model: str | None = None,
                                             require_authority: bool = True) -> dict[str, Any]:
        """Declare, once and explicitly, which authority may forecast a
        pension.

        This is the only governed path by which an existing pension —
        the Aviva resource included — becomes provider-managed. It
        asserts nothing about the provider's numbers: the declaration
        stands on its own, which is precisely what lets Foundry refuse
        an Expected Outcome while the illustration is missing."""
        self._authorise(principal, household_id, require_authority)
        resource = self.get_financial_resource(household_id, resource_id)
        if resource["resource_kind"] != "account" or resource["resource_type"] != "pension":
            raise ResourceCommandDenied("projection authority applies only to pension resources")
        if resource["status"] != "active":
            raise ResourceCommandDenied("a closed resource cannot be reclassified")
        if not isinstance(reason, str) or not reason.strip():
            raise ResourceCommandDenied("a reason is required to reclassify a pension")
        digest = _command_digest({"operation": "declare_pension_projection_authority",
                                  "household_id": household_id, "resource_id": resource_id,
                                  "projection_authority": projection_authority,
                                  "provider_name": provider_name, "reason": reason})
        if command_id:
            replay = self._audit_replay(command_id, digest, household_id)
            if replay is not None:
                return replay
        try:
            finance_entities.declare_pension_projection_authority(
                self.log, resource_id, projection_authority=projection_authority,
                reason=reason, provider_name=provider_name, actor=actor)
        except (TypeError, ValueError) as exc:
            raise ResourceCommandDenied(str(exc)) from exc
        if command_id:
            self.log.append("application.mcp_command.executed", {
                "operation": "declare_pension_projection_authority", "command_id": command_id,
                "request_digest": digest, "household_id": household_id,
                "resource_id": resource_id, "principal": principal,
                "client": client, "witness_model": witness_model,
            }, actor=actor)
        return self.get_financial_resource(household_id, resource_id)

    def close_financial_resource(self, *, household_id: str, resource_id: str,
                                 reason: str, actor: str, principal: str | None = None,
                                 command_id: str | None = None, client: str | None = None,
                                 witness_model: str | None = None, require_authority: bool = True) -> dict[str, Any]:
        self._authorise(principal, household_id, require_authority)
        self.get_financial_resource(household_id, resource_id)
        digest = _command_digest({"operation": "close_financial_resource", "household_id": household_id,
                                  "resource_id": resource_id, "reason": reason})
        if command_id:
            replay = self._audit_replay(command_id, digest, household_id)
            if replay is not None:
                return replay
        resource = self.get_financial_resource(household_id, resource_id)
        if resource["resource_kind"] == "account":
            finance_entities.close_account(self.log, resource_id, reason, actor=actor)
        elif resource["resource_kind"] == "obligation":
            finance_entities.close_obligation(self.log, resource_id, reason, actor=actor)
        else:
            finance_entities.close_asset(self.log, resource_id, reason, actor=actor)
        if command_id:
            self.log.append("application.mcp_command.executed", {
                "operation": "close_financial_resource", "command_id": command_id,
                "request_digest": digest, "household_id": household_id,
                "resource_id": resource_id, "principal": principal,
                "client": client, "witness_model": witness_model,
            }, actor=actor)
        return self.get_financial_resource(household_id, resource_id)

    def get_financial_resource(self, household_id: str, resource_id: str) -> dict[str, Any]:
        return FinancialResourceQuery(self.log, household_id).get_financial_resource(resource_id)


@dataclass(frozen=True)
class FinancialResourceQuery:
    """Deliberately small read model; it never exposes event-log records."""

    log: EventLog
    household_id: str
    contracts: CaptureContractRegistry

    def __init__(self, log: EventLog, household_id: str,
                 contracts: CaptureContractRegistry | None = None):
        object.__setattr__(self, "log", log)
        object.__setattr__(self, "household_id", household_id)
        object.__setattr__(self, "contracts", contracts or capture_contract_registry())

    def list_financial_resources(self) -> list[dict[str, Any]]:
        registry, projection = self._state()
        resources = []
        for subject_id, registration in registry.registrations.items():
            if registration.household_id != self.household_id or registration.domain != "finance":
                continue
            resource = (projection.accounts.get(subject_id) or projection.assets.get(subject_id)
                        or projection.obligations.get(subject_id))
            if resource is not None:
                resources.append(self._summary(resource))
        return sorted(resources, key=lambda resource: resource["id"])

    def get_financial_resource(self, resource_id: str) -> dict[str, Any]:
        if not isinstance(resource_id, str) or not resource_id:
            raise ResourceNotFound(resource_id)
        registry, projection = self._state()
        registration = registry.registrations.get(resource_id)
        if (registration is None or registration.household_id != self.household_id
                or registration.domain != "finance"):
            raise ResourceNotFound(resource_id)
        resource = (projection.accounts.get(resource_id) or projection.assets.get(resource_id)
                    or projection.obligations.get(resource_id))
        if resource is None:
            raise ResourceNotFound(resource_id)
        result = self._summary(resource)
        result["provenance"] = {"event_ids": list(resource.provenance),
                                "history_event_ids": list(resource.history)}
        return result

    def capture_availability(self, resource_id: str) -> dict[str, Any]:
        self.get_financial_resource(resource_id)  # preserves household authority before capability read
        targets = CaptureTargetRegistry(
            self.log, FinanceCaptureTargetResolver(FinanceEntityProjection(self.log)))
        supported = []
        for contract in self.contracts.discover():
            for target in targets.for_contract(self.household_id, contract):
                if target.subject_id == resource_id:
                    supported.append({"contract_id": contract.identifier,
                                      "contract_version": contract.version,
                                      "target_id": target.id,
                                      "input_schema": [{"name": field.name,
                                                        "required": field.required,
                                                        "help_text": field.help_text,
                                                        "default": field.default}
                                                       for field in contract.schema]})
        return {"resource_id": resource_id, "supported_capture_operations": supported}

    def get_financial_resource_valuation(self, resource: str) -> dict[str, Any]:
        """Return a human-facing canonical valuation read for one resource.

        The reference is deliberately an exact resource name or canonical id.
        This keeps MCP useful to a person without turning it into an
        unbounded, cross-household search surface.
        """
        resource_id = self._resolve_resource_reference(resource)
        registry, projection = self._state()
        registration = registry.registrations[resource_id]
        if registration.household_id != self.household_id or registration.domain != "finance":
            raise ResourceNotFound(resource)
        subject = (projection.accounts.get(resource_id) or projection.assets.get(resource_id)
                   or projection.obligations.get(resource_id))
        if subject is None:
            raise ResourceNotFound(resource)
        valuations = self._valuation_history(subject, projection)
        current = valuations[0] if valuations else None
        return {
            "resource": self._display_name(subject),
            "current_valuation": current,
            "valuation_history": valuations,
            "canonical_resource": {"canonical_id": subject.id,
                                   "resource_kind": self._summary(subject)["resource_kind"],
                                   "currency": subject.currency},
            "owners": self._owners(subject),
        }

    def _resolve_resource_reference(self, reference: str) -> str:
        if not isinstance(reference, str) or not reference.strip():
            raise ResourceNotFound(reference)
        value = reference.strip()
        registry, projection = self._state()
        candidates = []
        for resource_id, registration in registry.registrations.items():
            if registration.household_id != self.household_id or registration.domain != "finance":
                continue
            subject = (projection.accounts.get(resource_id) or projection.assets.get(resource_id)
                       or projection.obligations.get(resource_id))
            if subject is not None and (value == resource_id or value.casefold() in {
                    self._display_name(subject).casefold(), str(getattr(subject, "name", "")).casefold()}):
                candidates.append(resource_id)
        if len(candidates) != 1:
            raise ResourceNotFound(reference)
        return candidates[0]

    def _valuation_history(self, subject: Account | Asset | Obligation,
                           projection: FinanceEntityProjection) -> list[dict[str, Any]]:
        events = {event["id"]: (index, event) for index, event in enumerate(self.log.events())}
        records = []
        for valuation in projection.valuations_of(subject.id):
            event_id = valuation.provenance[-1] if valuation.provenance else None
            indexed = events.get(event_id)
            if indexed is None:
                continue
            index, event = indexed
            records.append((valuation.as_of, index, self._valuation_record(valuation, event)))
        return [record for _, _, record in sorted(records, key=lambda item: item[:2], reverse=True)]

    def _valuation_record(self, valuation, event: dict[str, Any]) -> dict[str, Any]:
        payload = event["payload"]
        observation = payload.get("observation") if isinstance(payload.get("observation"), dict) else {}
        evidence_reference = observation.get("external_document_ref")
        source = evidence_reference or valuation.source
        record = {
            "summary": f"{self._money(valuation.amount, valuation.currency)} | "
                       f"{self._when(valuation.as_of)}" + (f" | {source}" if source else ""),
            "amount": valuation.amount,
            "currency": valuation.currency,
            "as_of": self._when(valuation.as_of),
            "valuation_basis": valuation.valuation_basis,
            "evidence": ({"description": evidence_reference,
                          "kind": "external evidence reference"} if evidence_reference else
                         {"description": valuation.source, "kind": "declared source"}
                         if valuation.source else None),
            "canonical_valuation": {
                "canonical_id": valuation.id,
                "event": {"description": "Finance valuation declared",
                          "canonical_id": event["id"], "kind": event["kind"]},
                "asserted_by": event["actor"],
            },
        }
        provenance = payload.get("provenance")
        if isinstance(provenance, dict):
            record["canonical_valuation"]["acquisition"] = {
                "description": "Confirmed manual observation",
                **({"proposal_canonical_id": provenance["proposal_id"]}
                   if isinstance(provenance.get("proposal_id"), str) else {}),
                **({"evidence_canonical_id": provenance["evidence_id"]}
                   if isinstance(provenance.get("evidence_id"), str) else {}),
            }
        return record

    def _owners(self, resource: Account | Asset | Obligation) -> list[dict[str, str]]:
        people = EntityProjection(self.log).parties
        return [{"person": self._party_name(people.get(link.target)), "relation": link.relation,
                 "canonical_id": link.target}
                for link in resource.ownership]

    @staticmethod
    def _party_name(party) -> str:
        if party is None:
            return "Unknown person"
        return str(party.attributes.get("display_name") or party.attributes.get("name")
                   or "Household member")

    @staticmethod
    def _money(amount: float, currency: str) -> str:
        return f"{_CURRENCY_SYMBOLS.get(currency, currency + ' ')}{amount:,.2f}"

    @staticmethod
    def _when(timestamp: float) -> str:
        value = datetime.fromtimestamp(timestamp, tz=_LONDON)
        return f"{value.day} {value.strftime('%b %Y %H:%M')}"

    @staticmethod
    def _display_name(resource: Account | Asset | Obligation) -> str:
        summary = FinancialResourceQuery._summary(resource)
        labels = {"isa": "Cash ISA", "checking": "Cash account", "savings": "Savings account",
                  "pension": "Pension", "property": "Property"}
        label = labels.get(summary["resource_type"], str(summary["resource_type"]).replace("_", " ").title())
        name = getattr(resource, "name", None)
        if not name:
            return label
        return name if name.casefold().startswith(f"{label} —".casefold()) else f"{label} — {name}"

    def _state(self) -> tuple[AssetRegistry, FinanceEntityProjection]:
        return finance_asset_registry(self.log), FinanceEntityProjection(self.log)

    @staticmethod
    def _summary(resource: Account | Asset | Obligation) -> dict[str, Any]:
        is_account = isinstance(resource, Account)
        is_obligation = isinstance(resource, Obligation)
        return {
            "id": resource.id,
            "resource_kind": "obligation" if is_obligation else "account" if is_account else "asset",
            "resource_type": ("isa" if is_account and resource.account_type == "brokerage"
                              and resource.tax_wrapper == "isa"
                              else resource.account_type if is_account else
                              resource.liability_category if is_obligation else resource.asset_category),
            "name": getattr(resource, "name", None),
            "currency": resource.currency,
            "status": resource.status,
            "liquidity_classification": getattr(resource, "liquidity_classification", None),
            # Pension-only: projection authority answers "does this
            # resource require provider projection evidence?", which is
            # meaningless for a current account and would otherwise add
            # a null to every resource in the read surface.
            **({"projection_authority": resource.projection_authority,
                "provider_name": resource.provider_name}
               if is_account and resource.account_type == "pension" else {}),
            "ownership": [{"relation": link.relation, "subject_id": link.target,
                           **({"share": link.share} if link.share is not None else {})}
                          for link in resource.ownership],
        }

"""Household-scoped financial-resource queries for trusted adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from foundry.capture_contracts import CaptureContractRegistry, capture_contract_registry
from foundry.core.acquisition import AssetRegistry
from foundry.core.capture_targets import CaptureTargetRegistry
from foundry.eventlog import EventLog
from foundry.finance.capture_targets import FinanceCaptureTargetResolver, finance_asset_registry
from foundry.finance.entities import Account, Asset, FinanceEntityProjection


class ResourceNotFound(LookupError):
    """The subject is absent or outside the authorised household."""


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
            resource = projection.accounts.get(subject_id) or projection.assets.get(subject_id)
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
        resource = projection.accounts.get(resource_id) or projection.assets.get(resource_id)
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
                                      "target_id": target.id})
        return {"resource_id": resource_id, "supported_capture_operations": supported}

    def _state(self) -> tuple[AssetRegistry, FinanceEntityProjection]:
        return finance_asset_registry(self.log), FinanceEntityProjection(self.log)

    @staticmethod
    def _summary(resource: Account | Asset) -> dict[str, Any]:
        is_account = isinstance(resource, Account)
        return {
            "id": resource.id,
            "resource_kind": "account" if is_account else "asset",
            "resource_type": resource.account_type if is_account else resource.asset_category,
            "name": resource.name,
            "currency": resource.currency,
            "status": resource.status,
            "liquidity_classification": resource.liquidity_classification,
            "ownership": [{"relation": link.relation, "subject_id": link.target,
                           **({"share": link.share} if link.share is not None else {})}
                          for link in resource.ownership],
        }

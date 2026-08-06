"""Finance's RFC-015 descriptor provider for Core's target projection."""

from __future__ import annotations

from foundry.core.acquisition import AssetRegistry
from foundry.core.capture_targets import CaptureTargetEntity
from foundry.eventlog import EventLog
from foundry.finance.entities import FinanceEntityProjection


_SUPPORTED_PROPERTIES = {
    "pension_balance": {"account:pension"},
    "cash_balance": {"account:checking", "account:savings"},
    "property_valuation": {"asset:property"},
}


class FinanceCaptureTargetResolver:
    """Resolves Finance entities and owns the frozen §5.2 compatibility table."""

    def __init__(self, finance: FinanceEntityProjection):
        self.finance = finance

    def resolve(self, subject_id: str) -> CaptureTargetEntity | None:
        account = self.finance.accounts.get(subject_id)
        if account is not None:
            return CaptureTargetEntity(account.id, account.name, f"account:{account.account_type}", account.status)
        asset = self.finance.assets.get(subject_id)
        if asset is not None:
            return CaptureTargetEntity(asset.id, asset.name, f"asset:{asset.asset_category}", asset.status)
        return None

    def supports(self, entity: CaptureTargetEntity, property_name: str) -> bool:
        return entity.entity_type in _SUPPORTED_PROPERTIES.get(property_name, set())

    def bootstrap_properties(self, entity: CaptureTargetEntity) -> tuple[str, ...]:
        """Canonical type decides which manual properties may be bootstrapped.

        Property assets have an additional canonical primary-residence proof,
        applied by the bootstrapper; the resolver owns type compatibility.
        """
        return tuple(sorted(property_name for property_name, entity_types in _SUPPORTED_PROPERTIES.items()
                            if entity.entity_type in entity_types))


def finance_asset_registry(log: EventLog) -> AssetRegistry:
    """Build the only production Finance-aware asset registry."""
    resolver = FinanceCaptureTargetResolver(FinanceEntityProjection(log))
    return AssetRegistry(log, entity_exists=lambda subject_id: resolver.resolve(subject_id) is not None)

"""Finance's RFC-016 Mission Target metric descriptors."""

from foundry.core.mission_targets import MetricDescriptor


class FinanceTargetMetricResolver:
    """The domain-owned, closed descriptor table for locked Finance missions."""

    _DESCRIPTORS = {
        "finance.liquidity_runway": MetricDescriptor("finance.liquidity_runway", "duration_months", "months", "higher_is_better"),
        "finance.mortgage_payment_runway": MetricDescriptor("finance.mortgage_payment_runway", "duration_months", "months", "higher_is_better"),
        "finance.accessible_assets": MetricDescriptor("finance.accessible_assets", "currency", "GBP", "higher_is_better"),
        "finance.pension_wealth": MetricDescriptor("finance.pension_wealth", "currency", "GBP", "higher_is_better"),
        "finance.mortgage_balance": MetricDescriptor("finance.mortgage_balance", "currency", "GBP", "lower_is_better"),
    }

    _HORIZON_KINDS = {
        "finance.liquidity_runway": "none",
        "finance.mortgage_payment_runway": "none",
        "finance.accessible_assets": "by_date",
        "finance.pension_wealth": "derived",
        "finance.mortgage_balance": "by_date",
    }

    def describe(self, metric_id: str) -> MetricDescriptor | None:
        return self._DESCRIPTORS.get(metric_id)

    def horizon_kind(self, metric_id: str) -> str | None:
        """Return the RFC-016 horizon semantics for a locked Finance metric."""
        return self._HORIZON_KINDS.get(metric_id)

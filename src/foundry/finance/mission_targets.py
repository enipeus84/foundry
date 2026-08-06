"""Finance's RFC-016 Mission Target metric descriptors."""

from foundry.core.mission_targets import MetricDescriptor


class FinanceTargetMetricResolver:
    """The domain-owned, closed descriptor table for locked Finance missions."""

    _DESCRIPTORS = {
        "finance.liquidity_runway": MetricDescriptor("finance.liquidity_runway", "duration_months", "months", "higher_is_better"),
        "finance.accessible_assets": MetricDescriptor("finance.accessible_assets", "currency", "GBP", "higher_is_better"),
        "finance.pension_wealth": MetricDescriptor("finance.pension_wealth", "currency", "GBP", "higher_is_better"),
        "finance.mortgage_balance": MetricDescriptor("finance.mortgage_balance", "currency", "GBP", "lower_is_better"),
    }

    def describe(self, metric_id: str) -> MetricDescriptor | None:
        return self._DESCRIPTORS.get(metric_id)

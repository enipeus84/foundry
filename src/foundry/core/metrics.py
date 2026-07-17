"""
Metric Provider contract — 000-core-domain-model.md §13.

A contract, now made concrete as code: `MetricRequest` and
`MetricResult` are the shapes; `MetricProvider` is the interface a
domain implements conceptually (a `Protocol` — no base class a domain
is forced to subclass); `MetricRegistry` is pure routing between them.

The registry is operational wiring, not event-sourced data — the same
category as `Kernel`'s constructor-injected `ModelAdapter`. It is
rebuilt fresh from each domain's explicit `register()` call every time
the system starts; it needs no persistence and introduces no new
source of truth about what's true, only about which domain to ask
(000 §13.5). Registering it here, in Core, keeps Core the only place
that ever dispatches a metric request — no product-layer code imports
a domain's calculation function directly.

Nothing here calls a `ModelAdapter`, and nothing here can: nowhere in
this module is `foundry.models` imported, and `MetricProvider.calculate`
is a plain, synchronous, deterministic call. "AI may explain, but
cannot determine" (000 §8) is enforced by *absence* — there is no path
from a `MetricRequest` to a model.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from . import vocab
from .scope import Subject
from ..errors import DuplicateMetricError, VocabularyError


@dataclass(frozen=True)
class MetricRequest:
    metric_id: str
    scope: Subject
    as_of: float
    horizon: tuple[float, float] | None = None
    assumption_set_id: str | None = None
    scenario_id: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    requested_calculation_version: str | None = None


@dataclass(frozen=True)
class MetricResult:
    metric_id: str
    value: float | None
    unit_or_currency: str | None
    scope: Subject
    as_of: float
    status: str
    calculation_version: str
    input_references: tuple[str, ...] = ()
    evidence_references: tuple[str, ...] = ()
    assumption_references: tuple[str, ...] = ()
    generated_at: float = field(default_factory=time.time)
    confidence_or_quality: Any = None
    limitations: tuple[str, ...] = ()
    projection_series_reference: str | None = None
    drill_down_target: str | None = None

    def __post_init__(self) -> None:
        if self.status not in vocab.METRIC_STATUS:
            raise VocabularyError(f"{self.status!r} is not a valid metric_status")


def unsupported(request: MetricRequest, reason: str) -> MetricResult:
    """The honest alternative to inventing a value (000 §13.3).
    `calculation_version=""` here specifically means "no calculation
    happened" — never confuse it with a real provider's version string,
    which should never legitimately be empty; a provider returning
    `status: unsupported` should propagate its own `calculation_version`
    if one is meaningful (e.g. "this version doesn't support that
    scenario"), and only omit it when no version applies at all."""
    return MetricResult(
        metric_id=request.metric_id, value=None, unit_or_currency=None,
        scope=request.scope, as_of=request.as_of, status="unsupported",
        calculation_version="", limitations=(reason,),
    )


@runtime_checkable
class MetricProvider(Protocol):
    """The interface a domain implements conceptually — no base class,
    no plugin framework (000 §13.4)."""

    def owned_metric_ids(self) -> frozenset[str]:
        """Which metric identifiers this provider owns."""
        ...

    def calculate(self, request: MetricRequest) -> MetricResult:
        """Deterministic. No model call may ever be part of this."""
        ...


class MetricRegistry:
    """`metric_id -> exactly one provider`. No business calculation
    logic lives here — routing only (000 §13.5)."""

    def __init__(self) -> None:
        self._providers: dict[str, MetricProvider] = {}

    def register(self, provider: MetricProvider) -> None:
        """Explicit registration; no implicit discovery. Duplicate
        ownership fails closed — the second registration of an
        already-owned `metric_id` is rejected outright, never resolved
        by registration order."""
        owned = provider.owned_metric_ids()
        for metric_id in owned:
            existing = self._providers.get(metric_id)
            if existing is not None and existing is not provider:
                raise DuplicateMetricError(
                    f"{metric_id!r} is already registered to {existing!r}; "
                    f"{provider!r} cannot also claim it")
        for metric_id in owned:
            self._providers[metric_id] = provider

    def owned_metric_ids(self) -> frozenset[str]:
        return frozenset(self._providers)

    def provider_for(self, metric_id: str) -> MetricProvider | None:
        return self._providers.get(metric_id)

    def dispatch(self, request: MetricRequest) -> MetricResult:
        """Every metric request flows through here. Core never imports
        or calls a domain's calculation function directly — this is
        the only call site that reaches one, and only via the
        registered `MetricProvider`, never a concrete domain class."""
        provider = self._providers.get(request.metric_id)
        if provider is None:
            return unsupported(request, "no provider registered for this metric_id")
        return provider.calculate(request)

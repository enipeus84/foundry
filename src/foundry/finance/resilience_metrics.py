"""Published Finance metrics for Financial Resilience (RFC-008).

The four metrics are deterministic calculators over existing projections and
the resilience evidence envelope. The existing ``finance.liquidity_runway``
provider remains the sole owner of that metric and its ``v1`` calculation is
unchanged. This provider deliberately reuses its denominator and liquid-value
helpers so the two published views cannot drift onto different bases.
"""

from __future__ import annotations

from dataclasses import replace
import math
from numbers import Real

from foundry.core.entities import EntityProjection
from foundry.core.metrics import MetricRequest, MetricResult

from . import vocab
from .entities import AssumptionSet, FinanceEntityProjection
from .metrics import (
    ESSENTIAL_COMMITTED_CATEGORIES,
    FinanceMetricProvider,
    _LIQUID,
)
from .resilience_evidence import (
    ResilienceEvidence,
    ResilienceEvidenceProjection,
)


CALCULATION_VERSION = "resilience-metrics-v1"
METRIC_IDS = frozenset({
    "finance.essential_outflow_monthly",
    "finance.emergency_reserve_target",
    "finance.emergency_reserve_gap",
    "finance.deployable_surplus",
})

DAY = 86_400.0
MONTH = 365.2425 * DAY / 12.0


class FinanceResilienceMetricProvider:
    """Finance-owned provider for the four RFC-008 resilience metrics."""

    def __init__(
        self,
        finance: FinanceEntityProjection,
        core: EntityProjection,
        evidence: ResilienceEvidenceProjection,
    ):
        self.finance = finance
        self.core = core
        self.evidence = evidence
        self.basis = FinanceMetricProvider(finance, core)
        self._metric_cache: dict[tuple[object, ...], MetricResult] = {}
        self._holdings_cache: dict[
            tuple[object, ...],
            tuple[float, tuple[str, ...], tuple[str, ...], bool] | None,
        ] = {}

    def owned_metric_ids(self) -> frozenset[str]:
        return METRIC_IDS

    def calculate(self, request: MetricRequest) -> MetricResult:
        if request.metric_id not in METRIC_IDS:
            return self._unsupported(
                request,
                "not owned by FinanceResilienceMetricProvider",
            )
        if request.horizon is not None or request.scenario_id is not None:
            return self._unsupported(
                request,
                "resilience metrics do not support horizon or scenario "
                "requests",
            )
        if request.parameters:
            return self._unsupported(
                request,
                "resilience metrics do not accept parameters",
            )
        if request.requested_calculation_version not in (
            None, CALCULATION_VERSION
        ):
            return self._unsupported(
                request,
                f"calculation_version "
                f"{request.requested_calculation_version!r} cannot be "
                f"reproduced (current: {CALCULATION_VERSION!r})",
            )
        assumption_set = self._assumption_set(request)
        if assumption_set is None:
            return self._unavailable(
                request,
                "active resilience Assumption Set not found",
            )
        return self._calculate_owned(
            request, assumption_set, request.metric_id)

    def _calculate_owned(
        self,
        request: MetricRequest,
        assumption_set: AssumptionSet,
        metric_id: str,
    ) -> MetricResult:
        nested_request = (
            request if request.metric_id == metric_id
            else replace(request, metric_id=metric_id)
        )
        key = (
            metric_id,
            nested_request.scope.kind,
            nested_request.scope.id,
            nested_request.as_of,
            nested_request.assumption_set_id,
        )
        cached = self._metric_cache.get(key)
        if cached is not None:
            return cached
        handler = {
            "finance.essential_outflow_monthly": self._essential_outflow,
            "finance.emergency_reserve_target": self._reserve_target,
            "finance.emergency_reserve_gap": self._reserve_gap,
            "finance.deployable_surplus": self._deployable_surplus,
        }[metric_id]
        result = handler(nested_request, assumption_set)
        self._metric_cache[key] = result
        return result

    def _essential_outflow(
        self,
        request: MetricRequest,
        assumption_set: AssumptionSet,
    ) -> MetricResult:
        values, reason = self._assumptions(
            assumption_set,
            {
                "evidence_stale_after_days",
                "outflow_crosscheck_tolerance",
            },
        )
        if values is None:
            return self._unavailable(request, reason)
        stale_days = values["evidence_stale_after_days"]
        tolerance = values["outflow_crosscheck_tolerance"]
        if stale_days <= 0:
            return self._unavailable(
                request,
                "evidence_stale_after_days must be positive",
            )
        if not 0 <= tolerance <= 1:
            return self._unavailable(
                request,
                "outflow_crosscheck_tolerance must be between zero and one",
            )

        scope = self._scope(request)
        if scope is None:
            return self._unsupported(
                request,
                "finance.essential_outflow_monthly requires a party scope",
            )
        person_ids, attribute_to, currency = scope
        monthly, refs = self.basis._average_essential_outflow(
            person_ids,
            attribute_to,
            currency,
            request.as_of,
        )
        if monthly is None or monthly <= 0:
            return self._unavailable(
                request,
                "no net essential or committed monthly outflow observed",
                assumption_refs=tuple(assumption_set.provenance),
            )

        latest_at = self._latest_essential_transaction_at(
            person_ids,
            attribute_to,
            currency,
            request.as_of,
        )
        status = (
            "stale"
            if latest_at is None
            or request.as_of - latest_at > stale_days * DAY
            else "available"
        )
        limitations = []
        evidence_refs = []
        crosscheck = self.evidence.latest(
            request.scope.id,
            "essential_outflow_monthly",
            request.as_of,
        )
        if crosscheck is not None:
            evidence_refs.append(crosscheck.event_id)
            declared = self._numeric_evidence(crosscheck)
            if declared is not None:
                divergence = abs(declared - monthly) / monthly
                if divergence > tolerance:
                    limitations.append(
                        f"Declared essential-outflow cross-check differs "
                        f"from the transaction-derived basis by "
                        f"{divergence * 100:.1f}%, above the declared "
                        f"{tolerance * 100:.1f}% tolerance.")
        if status == "stale":
            limitations.append(
                "Essential-outflow transaction evidence is stale.")
        return self._result(
            request,
            monthly,
            currency,
            status,
            tuple(refs),
            tuple(evidence_refs),
            tuple(assumption_set.provenance),
            tuple(limitations),
        )

    def _reserve_target(
        self,
        request: MetricRequest,
        assumption_set: AssumptionSet,
    ) -> MetricResult:
        values, reason = self._assumptions(
            assumption_set,
            {
                "reserve_target_months",
                "evidence_stale_after_days",
                "outflow_crosscheck_tolerance",
            },
        )
        if values is None:
            return self._unavailable(request, reason)
        if values["reserve_target_months"] != 18.0:
            return self._unavailable(
                request,
                "reserve_target_months must equal the approved "
                "18-month destination",
            )
        outflow = self._calculate_owned(
            request,
            assumption_set,
            "finance.essential_outflow_monthly",
        )
        if outflow.status not in ("available", "stale") \
                or outflow.value is None:
            return self._from_dependency(
                request,
                outflow,
                "essential-outflow basis is unavailable",
            )
        return self._result(
            request,
            outflow.value * values["reserve_target_months"],
            outflow.unit_or_currency,
            outflow.status,
            outflow.input_references,
            outflow.evidence_references,
            tuple(sorted({
                *outflow.assumption_references,
                *assumption_set.provenance,
            })),
            outflow.limitations,
        )

    def _reserve_gap(
        self,
        request: MetricRequest,
        assumption_set: AssumptionSet,
    ) -> MetricResult:
        target = self._calculate_owned(
            request,
            assumption_set,
            "finance.emergency_reserve_target",
        )
        if target.status not in ("available", "stale") \
                or target.value is None:
            return self._from_dependency(
                request,
                target,
                "emergency reserve target is unavailable",
            )
        holdings = self._liquid_holdings(request)
        if holdings is None:
            return self._unavailable(
                request,
                "no liquid-holdings evidence observed",
                assumption_refs=target.assumption_references,
                extra_limitations=target.limitations,
            )
        value, refs, limitations, stale = holdings
        status = "stale" if target.status == "stale" or stale else "available"
        return self._result(
            request,
            target.value - value,
            target.unit_or_currency,
            status,
            tuple(sorted({*target.input_references, *refs})),
            target.evidence_references,
            target.assumption_references,
            tuple((*target.limitations, *limitations)),
        )

    def _deployable_surplus(
        self,
        request: MetricRequest,
        assumption_set: AssumptionSet,
    ) -> MetricResult:
        values, reason = self._assumptions(
            assumption_set,
            {
                "reserve_target_months",
                "commitment_horizon_months",
                "evidence_stale_after_days",
                "outflow_crosscheck_tolerance",
            },
        )
        if values is None:
            return self._unavailable(request, reason)
        if values["reserve_target_months"] != 18.0:
            return self._unavailable(
                request,
                "reserve_target_months must equal the approved "
                "18-month destination",
            )
        if values["commitment_horizon_months"] != 12.0:
            return self._unavailable(
                request,
                "commitment_horizon_months must equal the approved "
                "12-month horizon",
            )
        target = self._calculate_owned(
            request,
            assumption_set,
            "finance.emergency_reserve_target",
        )
        if target.status not in ("available", "stale") \
                or target.value is None:
            return self._from_dependency(
                request,
                target,
                "emergency reserve target is unavailable",
            )
        holdings = self._liquid_holdings(request)
        if holdings is None:
            return self._unavailable(
                request,
                "no liquid-holdings evidence observed",
                assumption_refs=target.assumption_references,
                extra_limitations=target.limitations,
            )
        liquid, holding_refs, holding_limits, holdings_stale = holdings
        all_commitments = self.evidence.for_party(
            request.scope.id,
            request.as_of,
            field="near_term_commitment",
        )
        horizon_end = (
            request.as_of + values["commitment_horizon_months"] * MONTH)
        commitments = tuple(
            record for record in all_commitments
            if record.due_at is not None
            and request.as_of <= record.due_at <= horizon_end
        )
        commitment_total = sum(
            float(record.value) for record in commitments
            if self._numeric_evidence(record) is not None
        )
        limitations = [*target.limitations, *holding_limits]
        if not commitments:
            if all_commitments:
                limitations.append(
                    "No declared commitment falls within the approved "
                    "12-month horizon; recognised near-term commitments "
                    "are treated as £0 with this explicit limitation.")
            else:
                limitations.append(
                    "No near-term commitment evidence is recorded; "
                    "recognised near-term commitments are treated as £0 "
                    "with this explicit limitation.")
        for record in commitments:
            if record.description:
                limitations.append(
                    f"Recognised near-term commitment: "
                    f"{record.description}.")
        evidence_refs = tuple(sorted({
            *target.evidence_references,
            *(record.event_id for record in commitments),
        }))
        stale_days = values["evidence_stale_after_days"]
        commitments_stale = any(
            request.as_of - record.effective_at > stale_days * DAY
            for record in commitments
        )
        status = (
            "stale"
            if target.status == "stale"
            or holdings_stale
            or commitments_stale
            else "available"
        )
        # Frozen definition: this is a stock above the full 18-month target.
        value = max(0.0, liquid - target.value - commitment_total)
        return self._result(
            request,
            value,
            target.unit_or_currency,
            status,
            tuple(sorted({*target.input_references, *holding_refs})),
            evidence_refs,
            tuple(sorted({
                *target.assumption_references,
                *assumption_set.provenance,
            })),
            tuple(limitations),
        )

    def _scope(
        self,
        request: MetricRequest,
    ) -> tuple[set[str], str | None, str] | None:
        person_ids = self.basis._scope_persons(request.scope)
        if person_ids is None:
            return None
        if not person_ids:
            return None
        person_set = set(person_ids)
        currency = self.basis._target_currency(
            person_set | {request.scope.id})
        return person_set, self.basis._attribute_to(request.scope), currency

    def _liquid_holdings(
        self,
        request: MetricRequest,
    ) -> tuple[float, tuple[str, ...], tuple[str, ...], bool] | None:
        cache_key = (
            request.scope.kind,
            request.scope.id,
            request.as_of,
            request.assumption_set_id,
        )
        if cache_key in self._holdings_cache:
            return self._holdings_cache[cache_key]
        scope = self._scope(request)
        if scope is None:
            self._holdings_cache[cache_key] = None
            return None
        person_ids, attribute_to, currency = scope
        if attribute_to is None:
            accounts, r1, l1 = self.basis._store_total(
                self.finance.accounts,
                person_ids,
                currency,
                request.as_of,
                filter_liquidity=_LIQUID,
            )
            assets, r2, l2 = self.basis._store_total(
                self.finance.assets,
                person_ids,
                currency,
                request.as_of,
                filter_liquidity=_LIQUID,
            )
        else:
            accounts, r1, l1 = self.basis._attributed_value(
                attribute_to,
                self.finance.accounts,
                currency,
                request.as_of,
                filter_liquidity=_LIQUID,
            )
            assets, r2, l2 = self.basis._attributed_value(
                attribute_to,
                self.finance.assets,
                currency,
                request.as_of,
                filter_liquidity=_LIQUID,
            )
        refs = tuple((*r1, *r2))
        if not refs:
            return None
        stale = self._holdings_are_stale(
            person_ids,
            attribute_to,
            request.as_of,
            self._stale_days_for_request(request),
        )
        result = (
            accounts + assets,
            refs,
            tuple((*l1, *l2)),
            stale,
        )
        self._holdings_cache[cache_key] = result
        return result

    def _latest_essential_transaction_at(
        self,
        person_ids: set[str],
        attribute_to: str | None,
        currency: str,
        as_of: float,
    ) -> float | None:
        latest = None
        owned = self.basis._owned_entities(
            person_ids,
            self.finance.accounts,
            vocab.VALUE_OWNERSHIP_RELATIONS,
        )
        for account_id in owned:
            account = self.finance.accounts[account_id]
            if self.basis._flow_weight(account, attribute_to) <= 0:
                continue
            for transaction in self.finance.transactions_in(account_id):
                if transaction.ts > as_of \
                        or transaction.transaction_category \
                        not in ESSENTIAL_COMMITTED_CATEGORIES:
                    continue
                converted, _ = self.basis._convert(
                    -transaction.amount,
                    transaction.currency,
                    currency,
                    as_of,
                )
                if converted is None:
                    continue
                latest = (
                    transaction.ts
                    if latest is None else max(latest, transaction.ts))
        return latest

    def _holdings_are_stale(
        self,
        person_ids: set[str],
        attribute_to: str | None,
        as_of: float,
        stale_days: float,
    ) -> bool:
        if stale_days <= 0:
            return True
        dated = []
        for store in (self.finance.accounts, self.finance.assets):
            owned = self.basis._owned_entities(
                person_ids,
                store,
                vocab.VALUE_OWNERSHIP_RELATIONS,
            )
            for entity_id in owned:
                entity = store[entity_id]
                if entity.liquidity_classification not in _LIQUID:
                    continue
                if attribute_to is not None \
                        and self.basis._flow_weight(entity, attribute_to) <= 0:
                    continue
                if store is self.finance.accounts:
                    applicable = [
                        item.ts for item in
                        self.finance.transactions_in(entity_id)
                        if item.ts <= as_of
                    ]
                else:
                    applicable = [
                        item.as_of for item in
                        self.finance.valuations_of(entity_id)
                        if item.as_of <= as_of
                    ]
                if applicable:
                    dated.append(max(applicable))
        return bool(dated) and any(
            as_of - observed_at > stale_days * DAY
            for observed_at in dated
        )

    def _stale_days_for_request(self, request: MetricRequest) -> float:
        assumption_set = self._assumption_set(request)
        if assumption_set is None:
            return 0.0
        value = assumption_set.assumptions.get("evidence_stale_after_days")
        if isinstance(value, bool) or not isinstance(value, Real) \
                or not math.isfinite(float(value)):
            return 0.0
        return float(value)

    def _assumption_set(
        self,
        request: MetricRequest,
    ) -> AssumptionSet | None:
        assumption_set = self.finance.assumption_sets.get(
            request.assumption_set_id or "")
        if assumption_set is None or assumption_set.status != "active":
            return None
        return assumption_set

    @staticmethod
    def _assumptions(
        assumption_set: AssumptionSet,
        required: set[str],
    ) -> tuple[dict[str, float] | None, str]:
        missing = sorted(required - assumption_set.assumptions.keys())
        if missing:
            return None, f"Assumption Set missing: {', '.join(missing)}"
        values = {}
        for key in sorted(required):
            value = assumption_set.assumptions[key]
            if isinstance(value, bool) or not isinstance(value, Real) \
                    or not math.isfinite(float(value)):
                return None, (
                    f"Assumption Set {key} must be a finite number")
            values[key] = float(value)
        return values, ""

    @staticmethod
    def _numeric_evidence(
        record: ResilienceEvidence,
    ) -> float | None:
        value = record.value
        if isinstance(value, bool) or not isinstance(value, Real) \
                or not math.isfinite(float(value)):
            return None
        return float(value)

    def _from_dependency(
        self,
        request: MetricRequest,
        dependency: MetricResult,
        reason: str,
    ) -> MetricResult:
        return self._unavailable(
            request,
            reason,
            assumption_refs=dependency.assumption_references,
            extra_limitations=dependency.limitations,
        )

    @staticmethod
    def _result(
        request: MetricRequest,
        value: float,
        unit: str | None,
        status: str,
        input_refs: tuple[str, ...],
        evidence_refs: tuple[str, ...],
        assumption_refs: tuple[str, ...],
        limitations: tuple[str, ...],
    ) -> MetricResult:
        return MetricResult(
            metric_id=request.metric_id,
            value=value,
            unit_or_currency=unit,
            scope=request.scope,
            as_of=request.as_of,
            status=status,
            calculation_version=CALCULATION_VERSION,
            input_references=input_refs,
            evidence_references=evidence_refs,
            assumption_references=assumption_refs,
            generated_at=request.as_of,
            confidence_or_quality="derived",
            limitations=limitations,
        )

    @staticmethod
    def _unavailable(
        request: MetricRequest,
        reason: str,
        *,
        assumption_refs: tuple[str, ...] = (),
        extra_limitations: tuple[str, ...] = (),
    ) -> MetricResult:
        return MetricResult(
            metric_id=request.metric_id,
            value=None,
            unit_or_currency=None,
            scope=request.scope,
            as_of=request.as_of,
            status="unavailable",
            calculation_version=CALCULATION_VERSION,
            assumption_references=assumption_refs,
            generated_at=request.as_of,
            limitations=(reason, *extra_limitations),
        )

    @staticmethod
    def _unsupported(
        request: MetricRequest,
        reason: str,
    ) -> MetricResult:
        return MetricResult(
            metric_id=request.metric_id,
            value=None,
            unit_or_currency=None,
            scope=request.scope,
            as_of=request.as_of,
            status="unsupported",
            calculation_version=CALCULATION_VERSION,
            generated_at=request.as_of,
            limitations=(reason,),
        )

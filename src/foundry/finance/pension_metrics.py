"""Published Finance pension metrics for RFC-009.

P1-P7 are deterministic observations or declared targets. Forecast values do
not enter this registry: they remain mission-assessment outputs under one
declared Pension Independence policy.
"""

from __future__ import annotations

from dataclasses import replace
import math
from numbers import Real

from foundry.core.entities import EntityProjection
from foundry.core.metrics import MetricRequest, MetricResult

from . import vocab
from .aggregation import FinanceAggregationService
from .entities import AssumptionSet, FinanceEntityProjection
from .pension_evidence import (
    AGE_FIELDS,
    PAYMENT_FIELDS,
    RATE_FIELDS,
    PensionEvidence,
    PensionEvidenceProjection,
)


CALCULATION_VERSION = "pension-metrics-v1"
METRIC_IDS = frozenset({
    "finance.pension_wealth",
    "finance.pension_contributions_annual",
    "finance.state_pension_income_annual",
    "finance.defined_benefit_income_annual",
    "finance.retirement_income_required",
    "finance.retirement_wealth_required",
    "finance.pension_contributions_tax_year",
})
DAY = 86_400.0


class FinancePensionMetricProvider:
    """Finance-owned provider for the seven frozen RFC-009 metrics."""

    def __init__(
        self,
        finance: FinanceEntityProjection,
        core: EntityProjection,
        evidence: PensionEvidenceProjection,
    ):
        self.finance = finance
        self.core = core
        self.evidence = evidence
        self.basis = FinanceAggregationService(finance, core)
        self._cache: dict[tuple[object, ...], MetricResult] = {}

    def owned_metric_ids(self) -> frozenset[str]:
        return METRIC_IDS

    def calculate(self, request: MetricRequest) -> MetricResult:
        if request.metric_id not in METRIC_IDS:
            return self._unsupported(request, "metric is not owned here")
        if request.horizon is not None or request.scenario_id is not None:
            return self._unsupported(
                request,
                "pension metrics do not support horizon or scenario requests",
            )
        if request.parameters:
            return self._unsupported(
                request, "pension metrics do not accept parameters")
        if request.requested_calculation_version not in (
            None, CALCULATION_VERSION
        ):
            return self._unsupported(
                request,
                "requested pension calculation version cannot be reproduced",
            )
        assumption_set = self._assumption_set(request)
        key = (
            request.metric_id,
            request.scope.kind,
            request.scope.id,
            request.as_of,
            request.assumption_set_id,
        )
        if key in self._cache:
            return self._cache[key]
        handler = {
            "finance.pension_wealth": self._pension_wealth,
            "finance.pension_contributions_annual": self._annual_contributions,
            "finance.state_pension_income_annual": self._state_pension,
            "finance.defined_benefit_income_annual": self._defined_benefit,
            "finance.retirement_income_required": self._required_income,
            "finance.retirement_wealth_required": self._required_wealth,
            "finance.pension_contributions_tax_year":
                self._tax_year_contributions,
        }[request.metric_id]
        result = handler(request, assumption_set)
        self._cache[key] = result
        return result

    def _pension_wealth(
        self,
        request: MetricRequest,
        assumption_set: AssumptionSet | None,
    ) -> MetricResult:
        scope = self._scope(request)
        if scope is None:
            return self._unsupported(
                request, "finance.pension_wealth requires a party scope")
        if assumption_set is None:
            return self._unavailable(
                request, "active pension Assumption Set not found")
        stale_days = self._assumption(
            assumption_set, "valuation_stale_after_days")
        if stale_days is None or stale_days <= 0:
            return self._unavailable(
                request, "valuation_stale_after_days must be positive",
                assumption_refs=tuple(assumption_set.provenance),
            )
        person_ids, attribute_to = scope
        accounts = self._pension_accounts(person_ids)
        total = 0.0
        refs = []
        limitations = []
        observed_dates = []
        included = 0
        for account_id, links in accounts.items():
            if self._has_db_evidence(account_id, request.as_of) \
                    and self._valuations(account_id, request.as_of):
                limitations.append(
                    "A pension account declares both a pot "
                    "valuation and DB entitlement; the account is excluded.")
                continue
            valuations = self._valuations(account_id, request.as_of)
            if not valuations:
                if self.finance.valuations_of(account_id):
                    limitations.append(
                        "A pension account is valued only after "
                        "the assessment date; excluded.")
                continue
            latest = max(
                enumerate(valuations),
                key=lambda item: (item[1].as_of, item[0]),
            )[1]
            converted, conversion_ref = self.basis.convert(
                latest.amount, latest.currency, "GBP", request.as_of)
            if converted is None:
                limitations.append(
                    f"No exchange rate {latest.currency}->GBP is available "
                    "for a pension account; it is excluded.")
                continue
            weight = self._weight(links, attribute_to)
            if weight <= 0:
                continue
            total += converted * weight
            included += 1
            refs.extend(latest.provenance)
            if conversion_ref:
                refs.append(conversion_ref)
            observed_dates.append(latest.as_of)
        if included == 0:
            return self._unavailable(
                request,
                "no pension account with an applicable pot valuation",
                assumption_refs=tuple(assumption_set.provenance),
                extra_limitations=tuple(limitations),
            )
        stale = any(
            request.as_of - observed > stale_days * DAY
            for observed in observed_dates
        )
        if stale:
            limitations.append("One or more pension pot valuations are stale.")
        return self._result(
            request,
            total,
            "GBP",
            "stale" if stale else "available",
            tuple(sorted(set(refs))),
            (),
            (),
            tuple(limitations),
        )

    def _annual_contributions(
        self,
        request: MetricRequest,
        assumption_set: AssumptionSet | None,
    ) -> MetricResult:
        scope = self._scope(request)
        if scope is None:
            return self._unsupported(
                request,
                "finance.pension_contributions_annual requires a party scope",
            )
        person_ids, attribute_to = scope
        accounts = self._pension_accounts(person_ids)
        total = 0.0
        refs = []
        declarations = 0
        latest_effective = []
        for account_id, links in accounts.items():
            weight = self._weight(links, attribute_to)
            for field in sorted(RATE_FIELDS):
                record = self.evidence.latest(
                    account_id, field, request.as_of)
                if record is None:
                    continue
                total += float(record.value) * weight
                refs.append(record.event_id)
                latest_effective.append(record.effective_at)
                declarations += 1
        if declarations == 0:
            return self._unavailable(
                request, "no declared annual pension contribution rates")
        limitations = []
        stale = False
        if assumption_set is not None:
            stale_days = self._assumption(
                assumption_set, "contribution_stale_after_days")
            if stale_days is not None and stale_days > 0:
                stale = any(
                    request.as_of - effective > stale_days * DAY
                    for effective in latest_effective
                )
                if stale:
                    limitations.append(
                        "One or more pension contribution declarations "
                        "are stale.")
            tolerance = self._assumption(
                assumption_set, "evidence_crosscheck_tolerance")
            observed = self._observed_contributions(
                accounts, attribute_to, request.as_of)
            if tolerance is not None and 0 <= tolerance <= 1 \
                    and observed is not None and total > 0:
                divergence = abs(observed - total) / total
                if divergence > tolerance:
                    limitations.append(
                        f"Declared annual pension contributions differ from "
                        f"observed pension-contribution flow by "
                        f"{divergence * 100:.1f}%, above the declared "
                        f"{tolerance * 100:.1f}% tolerance.")
        return self._result(
            request,
            total,
            "GBP",
            "stale" if stale else "available",
            (),
            tuple(refs),
            (),
            tuple(limitations),
        )

    def _state_pension(
        self,
        request: MetricRequest,
        assumption_set: AssumptionSet | None,
    ) -> MetricResult:
        scope = self._scope(request)
        if scope is None:
            return self._unsupported(
                request,
                "finance.state_pension_income_annual requires a party scope",
            )
        person_ids, _ = scope
        total = 0.0
        refs = []
        missing = []
        limitations = []
        effective = []
        for person_id in sorted(person_ids):
            record = self.evidence.latest(
                person_id, "state_pension_annual", request.as_of)
            if record is None:
                missing.append(person_id)
                continue
            total += float(record.value)
            refs.append(record.event_id)
            effective.append(record.effective_at)
            basis = self.evidence.latest(
                person_id, "state_pension_basis", request.as_of)
            if basis is not None:
                refs.append(basis.event_id)
                if basis.value == "forecast_with_continuing_contributions":
                    limitations.append(
                        "A State Pension declaration for an active member "
                        "assumes continuing contributions.")
        if len(missing) == len(person_ids):
            return self._unavailable(
                request,
                "no State Pension income declaration is available",
            )
        if missing:
            limitations.append(
                "State Pension is not declared for "
                f"{len(missing)} active member(s).")
        stale = self._evidence_is_stale(
            effective, assumption_set, "contribution_stale_after_days",
            request.as_of)
        if stale:
            limitations.append("One or more State Pension declarations are stale.")
        return self._result(
            request,
            total,
            "GBP",
            "stale" if stale else "available",
            (),
            tuple(refs),
            (),
            tuple(limitations),
        )

    def _defined_benefit(
        self,
        request: MetricRequest,
        assumption_set: AssumptionSet | None,
    ) -> MetricResult:
        scope = self._scope(request)
        if scope is None:
            return self._unsupported(
                request,
                "finance.defined_benefit_income_annual requires a party scope",
            )
        person_ids, attribute_to = scope
        total = 0.0
        refs = []
        limitations = []
        effective = []
        count = 0
        for account_id, links in self._pension_accounts(person_ids).items():
            record = self.evidence.latest(
                account_id, "db_annual_income_accrued", request.as_of)
            if record is None:
                continue
            if self._valuations(account_id, request.as_of):
                limitations.append(
                    "A pension account declares both DB "
                    "entitlement and pot valuation; the account is excluded.")
                continue
            total += float(record.value) * self._weight(links, attribute_to)
            refs.append(record.event_id)
            effective.append(record.effective_at)
            count += 1
        if count == 0:
            return self._unavailable(
                request, "no defined-benefit entitlement declaration")
        stale = self._evidence_is_stale(
            effective, assumption_set, "contribution_stale_after_days",
            request.as_of)
        if stale:
            limitations.append("One or more DB entitlement declarations are stale.")
        return self._result(
            request,
            total,
            "GBP",
            "stale" if stale else "available",
            (),
            tuple(refs),
            (),
            tuple(limitations),
        )

    def _required_income(
        self,
        request: MetricRequest,
        assumption_set: AssumptionSet | None,
    ) -> MetricResult:
        if assumption_set is None:
            return self._unavailable(
                request, "active pension Assumption Set not found")
        value = self._assumption(
            assumption_set, "required_retirement_income_annual")
        if value is None or value < 0:
            return self._unavailable(
                request,
                "required_retirement_income_annual must be non-negative",
                assumption_refs=tuple(assumption_set.provenance),
            )
        return self._result(
            request,
            value,
            "GBP",
            "available",
            (),
            (),
            tuple(assumption_set.provenance),
            (),
        )

    def _required_wealth(
        self,
        request: MetricRequest,
        assumption_set: AssumptionSet | None,
    ) -> MetricResult:
        if assumption_set is None:
            return self._unavailable(
                request, "active pension Assumption Set not found")
        rate = self._assumption(
            assumption_set, "sustainable_withdrawal_rate")
        if rate is None or not 0 < rate <= 1:
            return self._unavailable(
                request,
                "sustainable_withdrawal_rate must be between zero and one",
                assumption_refs=tuple(assumption_set.provenance),
            )
        required = self._calculate_nested(
            request, "finance.retirement_income_required")
        if required.value is None:
            return self._from_dependency(
                request, required, "required retirement income is unavailable")
        state = self._calculate_nested(
            request, "finance.state_pension_income_annual")
        db = self._calculate_nested(
            request, "finance.defined_benefit_income_annual")
        state_value = float(state.value) if state.value is not None else 0.0
        db_value = float(db.value) if db.value is not None else 0.0
        limitations = [*required.limitations]
        if state.value is None:
            limitations.append(
                "State Pension is absent from the wealth requirement and "
                "treated as £0.")
        else:
            limitations.extend(state.limitations)
        if db.value is None:
            limitations.append(
                "Defined-benefit income is absent from the wealth "
                "requirement and treated as £0.")
        else:
            limitations.extend(db.limitations)
        value = max(
            0.0,
            (float(required.value) - state_value - db_value) / rate,
        )
        status = (
            "stale"
            if "stale" in (state.status, db.status) else "available"
        )
        return self._result(
            request,
            value,
            "GBP",
            status,
            (),
            tuple(sorted({
                *state.evidence_references,
                *db.evidence_references,
            })),
            tuple(assumption_set.provenance),
            tuple(limitations),
        )

    def _tax_year_contributions(
        self,
        request: MetricRequest,
        assumption_set: AssumptionSet | None,
    ) -> MetricResult:
        scope = self._scope(request)
        if scope is None:
            return self._unsupported(
                request,
                "finance.pension_contributions_tax_year requires a party scope",
            )
        person_ids, attribute_to = scope
        boundaries = self._tax_year_boundaries(person_ids, request.as_of)
        if boundaries is None:
            return self._unavailable(
                request,
                "Tax Jurisdiction Configuration is unavailable for the "
                "active household members.",
            )
        if boundaries == "conflict":
            return self._unsupported(
                request,
                "active household members have conflicting tax-year "
                "boundaries",
            )
        start, end, jurisdiction_refs = boundaries
        records = []
        total = 0.0
        for account_id, links in self._pension_accounts(person_ids).items():
            weight = self._weight(links, attribute_to)
            for record in self.evidence.payments(account_id, request.as_of):
                if start <= record.effective_at <= end:
                    total += float(record.value) * weight
                    records.append(record)
        if not records:
            return self._unavailable(
                request,
                "no dated pension contribution payments are declared in "
                "the current tax year",
                input_refs=jurisdiction_refs,
            )
        return self._result(
            request,
            total,
            "GBP",
            "available",
            jurisdiction_refs,
            tuple(record.event_id for record in records),
            (),
            (),
        )

    def _calculate_nested(
        self,
        request: MetricRequest,
        metric_id: str,
    ) -> MetricResult:
        return self.calculate(replace(request, metric_id=metric_id))

    def _scope(
        self,
        request: MetricRequest,
    ) -> tuple[set[str], str | None] | None:
        people = self.basis.persons_for_scope(request.scope)
        if not people:
            return None
        return set(people), self.basis.attribute_to(request.scope)

    def _pension_accounts(self, person_ids: set[str]):
        owned = self.basis.owned_entities(
            person_ids,
            self.finance.accounts,
            vocab.VALUE_OWNERSHIP_RELATIONS,
        )
        return {
            account_id: links for account_id, links in owned.items()
            if self.finance.accounts[account_id].account_type == "pension"
        }

    def _weight(self, links, attribute_to: str | None) -> float:
        if attribute_to is None:
            return 1.0
        return self.basis.shares(links).get(attribute_to, 0.0)

    def _valuations(self, account_id: str, as_of: float):
        return tuple(
            valuation for valuation in self.finance.valuations_of(account_id)
            if valuation.as_of <= as_of
        )

    def _has_db_evidence(self, account_id: str, as_of: float) -> bool:
        return any(
            self.evidence.latest(account_id, field, as_of) is not None
            for field in (
                "db_annual_income_accrued",
                "db_normal_pension_age",
            )
        )

    def _observed_contributions(
        self,
        accounts,
        attribute_to: str | None,
        as_of: float,
    ) -> float | None:
        total = 0.0
        found = False
        for account_id, links in accounts.items():
            weight = self._weight(links, attribute_to)
            for transaction in self.finance.transactions_in(account_id):
                if transaction.ts > as_of \
                        or transaction.ts < as_of - 365.2425 * DAY \
                        or transaction.transaction_category \
                        != "pension_contribution":
                    continue
                converted, _ = self.basis.convert(
                    transaction.amount,
                    transaction.currency,
                    "GBP",
                    as_of,
                )
                if converted is None:
                    continue
                total += converted * weight
                found = True
        return total if found else None

    def _tax_year_boundaries(self, person_ids: set[str], as_of: float):
        latest_links: dict[str, tuple[int, str, str]] = {}
        for index, event in enumerate(self.evidence.log.events()):
            if event.get("kind") != "core.party.linked":
                continue
            payload = event.get("payload", {})
            if payload.get("relation") != "tax_resident_in":
                continue
            person_id = payload.get("entity_id")
            target = payload.get("target")
            if person_id in person_ids and isinstance(target, str):
                latest_links[person_id] = (index, target, event["id"])
        if set(latest_links) != person_ids:
            return None
        values = []
        refs = []
        for person_id in sorted(person_ids):
            _, jurisdiction_id, link_ref = latest_links[person_id]
            jurisdiction = self.finance.tax_jurisdictions.get(jurisdiction_id)
            if jurisdiction is None:
                return None
            values.append((
                float(jurisdiction.tax_year_start),
                float(jurisdiction.tax_year_end),
            ))
            refs.extend((*jurisdiction.provenance, link_ref))
        if len(set(values)) != 1:
            return "conflict"
        start, end = values[0]
        if not start <= as_of <= end:
            return None
        return start, end, tuple(sorted(set(refs)))

    def _assumption_set(
        self,
        request: MetricRequest,
    ) -> AssumptionSet | None:
        result = self.finance.assumption_sets.get(
            request.assumption_set_id or "")
        if result is None or result.status != "active":
            return None
        return result

    @staticmethod
    def _assumption(
        assumption_set: AssumptionSet,
        key: str,
    ) -> float | None:
        value = assumption_set.assumptions.get(key)
        if isinstance(value, bool) or not isinstance(value, Real) \
                or not math.isfinite(float(value)):
            return None
        return float(value)

    def _evidence_is_stale(
        self,
        effective_dates,
        assumption_set: AssumptionSet | None,
        key: str,
        as_of: float,
    ) -> bool:
        if assumption_set is None:
            return False
        days = self._assumption(assumption_set, key)
        return days is not None and days > 0 and any(
            as_of - effective > days * DAY for effective in effective_dates)

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
        input_refs: tuple[str, ...] = (),
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
            input_references=input_refs,
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

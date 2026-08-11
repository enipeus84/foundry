"""Read-only RFC-017 provenance for Finance pension wealth."""

from __future__ import annotations

from dataclasses import dataclass

from foundry.core.entities import EntityProjection
from foundry.core.metrics import MetricRequest
from foundry.core.scope import Subject
from foundry.core.value_provenance import (
    Contribution,
    Exclusion,
    ProvenanceNode,
    ValueReference,
)

from .entities import FinanceEntityProjection
from .pension_evidence import PensionEvidenceProjection
from .pension_metrics import CALCULATION_VERSION, FinancePensionMetricProvider


PENSION_WEALTH = "finance.pension_wealth"
RAW_VALUATION = "finance.pension_account_raw_valuation"
TERMINAL_ATTRIBUTION = "finance.pension_account_attributed_contribution"
OWNERSHIP_CONTEXT = "finance.pension_account_ownership_context"


@dataclass(frozen=True)
class _KnownAtLog:
    """Read-only event view deliberately lacking an append operation."""

    events_at_coordinate: tuple[dict, ...]

    def events(self):
        return iter(self.events_at_coordinate)


class FinancePensionExplainer:
    """Explain the calculation the pension metric already makes.

    The provider delegates root arithmetic and eligibility to
    ``FinancePensionMetricProvider`` over a fresh, ``known_at``-bounded
    projection.  Its own account loop only renders the attributed terms that
    same provider uses, preserving its deliberately filtered ownership links.
    """

    def __init__(self, log, *, assumption_set_id: str | None = None,
                 allow_implicit_assumption_set: bool = True):
        self._log = log
        self._assumption_set_id = assumption_set_id
        self._allow_implicit_assumption_set = allow_implicit_assumption_set

    def explainable_value_ids(self) -> frozenset[str]:
        # The attribution and ownership-context identifiers are intentional
        # terminal references under GD-P2-B/C.  They must never be registered.
        return frozenset({PENSION_WEALTH, RAW_VALUATION})

    def explain(self, reference: ValueReference) -> ProvenanceNode | None:
        if reference.value_id == PENSION_WEALTH and reference.subject.kind == "party":
            return self._wealth(reference)
        if reference.value_id == RAW_VALUATION and reference.subject.kind == "resource":
            return self._raw_valuation(reference)
        return None

    def _replay(self, known_at: float):
        view = _KnownAtLog(tuple(
            event for event in self._log.events() if event["ts"] <= known_at))
        core = EntityProjection.empty(view)
        finance = FinanceEntityProjection.empty(view)
        evidence = PensionEvidenceProjection.empty(view)
        for event in view.events():
            core.apply(event)
            finance.apply(event)
            evidence.apply(event)
        return core, finance, evidence

    def _assumption_id(self, finance) -> str | None:
        if self._assumption_set_id is not None:
            return self._assumption_set_id
        if not self._allow_implicit_assumption_set:
            return None
        active = sorted(
            item.id for item in finance.assumption_sets.values()
            if item.status == "active")
        return active[0] if len(active) == 1 else None

    def _request(self, reference: ValueReference, finance) -> MetricRequest:
        return MetricRequest(PENSION_WEALTH, reference.subject, reference.as_of,
                             assumption_set_id=self._assumption_id(finance))

    def _wealth(self, reference: ValueReference) -> ProvenanceNode | None:
        core, finance, evidence = self._replay(reference.known_at)
        provider = FinancePensionMetricProvider(finance, core, evidence)
        request = self._request(reference, finance)
        result = provider.calculate(request)
        if result.value is None:
            anchors = tuple(result.assumption_references)
            if not anchors:
                return None
            return ProvenanceNode(reference, "derived", result.status, None, None,
                                  CALCULATION_VERSION, anchors, (), (), "Pension wealth")
        scope = provider._scope(request)
        if scope is None:
            return None
        person_ids, attribute_to = scope
        contributions: list[Contribution] = []
        exclusions: list[Exclusion] = []
        ownership_anchors: list[str] = []
        for account_id, links in sorted(provider._pension_accounts(person_ids).items()):
            subject = Subject("resource", account_id)
            valuations = provider._valuations(account_id, reference.as_of)
            if provider._has_db_evidence(account_id, reference.as_of) and valuations:
                exclusions.append(Exclusion(subject, "conflicting"))
                continue
            if not valuations:
                exclusions.append(Exclusion(
                    subject,
                    "out_of_period" if provider.finance.valuations_of(account_id) else "unobserved"))
                continue
            latest = max(enumerate(valuations), key=lambda item: (item[1].as_of, item[0]))[1]
            converted, _ = provider.basis.convert(
                latest.amount, latest.currency, "GBP", reference.as_of)
            if converted is None:
                exclusions.append(Exclusion(subject, "incommensurable"))
                continue
            # This exact weight is the metric's numerical oracle, including
            # OBS-PENSION-01's intentional filter-before-weight behaviour.
            attributed = converted * provider._weight(links, attribute_to)
            ownership_anchors.extend(link.event_id for link in links if link.event_id)
            contributions.extend((
                Contribution("increases", attributed, ValueReference(
                    subject, TERMINAL_ATTRIBUTION, reference.as_of, reference.known_at), False),
                Contribution("contextual", None, ValueReference(
                    subject, RAW_VALUATION, reference.as_of, reference.known_at), True),
                Contribution("contextual", None, ValueReference(
                    subject, OWNERSHIP_CONTEXT, reference.as_of, reference.known_at), False),
            ))
        anchors = tuple(sorted(set((*result.input_references, *ownership_anchors))))
        return ProvenanceNode(reference, "derived", result.status, float(result.value), "GBP",
                              CALCULATION_VERSION, anchors, tuple(contributions),
                              tuple(exclusions), "Pension wealth")

    def _raw_valuation(self, reference: ValueReference) -> ProvenanceNode | None:
        _, finance, _ = self._replay(reference.known_at)
        account = finance.accounts.get(reference.subject.id)
        if account is None or account.account_type != "pension":
            return None
        valuations = tuple(item for item in finance.valuations_of(account.id)
                           if item.as_of <= reference.as_of)
        if not valuations:
            return None
        latest = max(enumerate(valuations), key=lambda item: (item[1].as_of, item[0]))[1]
        return ProvenanceNode(reference, "observed", "available", float(latest.amount),
                              latest.currency, CALCULATION_VERSION,
                              tuple(latest.provenance), (), (), "Raw pension valuation")

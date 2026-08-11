"""RFC-017 Value Provenance: deterministic explanation verification.

This module routes domain-owned explainers and verifies the structure they
return.  It neither calculates a value nor persists an explanation.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import math
from numbers import Real
from typing import Protocol

from ..errors import DuplicateValueExplainerError, VocabularyError
from . import vocab
from .scope import Subject
from .subject_authority import SubjectAuthority


class ValueProvenanceError(ValueError):
    """An explanation is structurally inconsistent and cannot be trusted."""


# SAFE-017-01.  The statuses authorised to carry a usable magnitude and a
# coverage claim, stated positively.  `METRIC_STATUS` is an extensible
# vocabulary, so naming the failure statuses instead would let any status a
# domain adds later inherit a fail-open default: an errored calculation could
# present a confident `complete`.  Anything outside this set is normalised to
# absent quantity, completeness and residual.
MAGNITUDE_BEARING_STATUS = frozenset({"available", "stale"})


def _text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueProvenanceError(f"{field_name} must be a non-empty string")
    return value.strip()


def _finite(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(float(value)):
        raise ValueProvenanceError(f"{field_name} must be a finite number")
    return float(value)


@dataclass(frozen=True)
class ValueReference:
    subject: Subject
    value_id: str
    as_of: float
    known_at: float

    def __post_init__(self) -> None:
        if not isinstance(self.subject, Subject):
            raise ValueProvenanceError("reference subject must be a Subject")
        object.__setattr__(self, "value_id", _text(self.value_id, "value id"))
        object.__setattr__(self, "as_of", _finite(self.as_of, "as_of"))
        object.__setattr__(self, "known_at", _finite(self.known_at, "known_at"))


@dataclass(frozen=True)
class Contribution:
    role: str
    quantity: float | None
    contributor: ValueReference
    expandable: bool

    def __post_init__(self) -> None:
        if self.role not in vocab.CONTRIBUTION_ROLE:
            raise VocabularyError("unsupported contribution role")
        if not isinstance(self.contributor, ValueReference):
            raise ValueProvenanceError("contributor must be a ValueReference")
        if not isinstance(self.expandable, bool):
            raise ValueProvenanceError("expandable must be boolean")
        if self.role == "contextual":
            if self.quantity is not None:
                raise ValueProvenanceError("contextual contributions carry no quantity")
        elif self.quantity is None:
            raise ValueProvenanceError("additive contributions require a quantity")
        else:
            quantity = _finite(self.quantity, "contribution quantity")
            if quantity < 0:
                raise ValueProvenanceError("contribution quantities must not be negative")
            object.__setattr__(self, "quantity", quantity)


@dataclass(frozen=True)
class Exclusion:
    subject: Subject
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.subject, Subject):
            raise ValueProvenanceError("exclusion subject must be a Subject")
        if self.reason not in vocab.EXCLUSION_REASON:
            raise VocabularyError("unsupported exclusion reason")


@dataclass(frozen=True)
class ProvenanceNode:
    reference: ValueReference
    kind: str
    status: str
    quantity: float | None
    unit_or_currency: str | None
    calculation_version: str
    anchors: tuple[str, ...]
    contributions: tuple[Contribution, ...]
    exclusions: tuple[Exclusion, ...]
    label: str
    completeness: str | None = field(init=False, default=None)
    residual: float | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        if not isinstance(self.reference, ValueReference):
            raise ValueProvenanceError("node reference must be a ValueReference")
        if self.kind not in vocab.PROVENANCE_NODE_KIND:
            raise VocabularyError("unsupported provenance node kind")
        if self.status not in vocab.METRIC_STATUS:
            raise VocabularyError("unsupported provenance node status")
        if self.quantity is not None:
            object.__setattr__(self, "quantity", _finite(self.quantity, "node quantity"))
        if self.unit_or_currency is not None:
            object.__setattr__(self, "unit_or_currency", _text(self.unit_or_currency, "node unit"))
        object.__setattr__(self, "calculation_version", _text(
            self.calculation_version, "calculation version"))
        object.__setattr__(self, "label", _text(self.label, "node label"))
        if not isinstance(self.anchors, tuple) or not all(isinstance(anchor, str) and anchor for anchor in self.anchors):
            raise ValueProvenanceError("anchors must be a tuple of non-empty event ids")
        if not isinstance(self.contributions, tuple) or not all(isinstance(item, Contribution) for item in self.contributions):
            raise ValueProvenanceError("contributions must be a tuple of Contribution")
        if not isinstance(self.exclusions, tuple) or not all(isinstance(item, Exclusion) for item in self.exclusions):
            raise ValueProvenanceError("exclusions must be a tuple of Exclusion")

    def with_derived_completeness(self, completeness: str | None,
                                  residual: float | None) -> ProvenanceNode:
        """Return a candidate node; the resolver always replaces these fields."""
        return _resolved_node(self, completeness, residual)

@dataclass(frozen=True)
class ExplanationDescriptor:
    value_id: str
    unit_or_currency: str
    tolerance: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "value_id", _text(self.value_id, "descriptor value id"))
        object.__setattr__(self, "unit_or_currency", _text(self.unit_or_currency, "descriptor unit"))
        if self.tolerance is not None:
            tolerance = _finite(self.tolerance, "descriptor tolerance")
            if tolerance < 0:
                raise ValueProvenanceError("descriptor tolerance must not be negative")
            object.__setattr__(self, "tolerance", tolerance)


class ValueExplainer(Protocol):
    def explainable_value_ids(self) -> frozenset[str]: ...

    def explain(self, reference: ValueReference) -> ProvenanceNode | None: ...


class ProvenanceResolver:
    """Explicit resolver registry plus bounded, lazy structural verification."""

    def __init__(self, descriptors: tuple[ExplanationDescriptor, ...] = (), *,
                 authority: SubjectAuthority | None = None) -> None:
        self._explainers: dict[str, ValueExplainer] = {}
        self._descriptors: dict[str, ExplanationDescriptor] = {}
        self._authority = authority
        for descriptor in descriptors:
            if descriptor.value_id in self._descriptors:
                raise DuplicateValueExplainerError(f"duplicate descriptor for {descriptor.value_id!r}")
            self._descriptors[descriptor.value_id] = descriptor

    def register(self, explainer: ValueExplainer) -> None:
        declared = explainer.explainable_value_ids()
        if not isinstance(declared, frozenset):
            raise ValueProvenanceError("explainer value ids must be a frozenset")
        # SAFE-017-03.  Normalise once, from the single ownership declaration,
        # before duplicate validation and before registration.  `ValueReference`
        # normalises its own `value_id`, so registering a raw key would let two
        # explainers own ids that differ only by surrounding whitespace: the
        # duplicate guard would not fire and one owner would be unreachable.
        value_ids = frozenset(_text(value_id, "explainer value id") for value_id in declared)
        for value_id in value_ids:
            existing = self._explainers.get(value_id)
            if existing is not None and existing is not explainer:
                raise DuplicateValueExplainerError(f"{value_id!r} is already registered")
        for value_id in value_ids:
            self._explainers[value_id] = explainer

    def explain(self, reference: ValueReference, *, max_depth: int) -> ProvenanceNode | None:
        if isinstance(max_depth, bool) or not isinstance(max_depth, int) or max_depth < 0:
            raise ValueProvenanceError("max_depth must be a non-negative integer")
        if self._authority is None:
            raise ValueProvenanceError("subject authority is required")
        household = self._authority.household_for(reference.subject)
        if not isinstance(household, str) or not household:
            raise ValueProvenanceError("root subject has no unambiguous household authority")
        return self._resolve(reference, max_depth=max_depth, depth=0, path=(),
                             household=household, cache={})

    def _resolve(self, reference: ValueReference, *, max_depth: int, depth: int,
                 path: tuple[ValueReference, ...], household: str,
                 cache: dict[ValueReference, ProvenanceNode]) -> ProvenanceNode | None:
        if reference in path:
            return None
        self._verify_subject_authority(reference.subject, household)
        resolved = cache.get(reference)
        if resolved is None:
            explainer = self._explainers.get(reference.value_id)
            if explainer is None:
                return None
            node = explainer.explain(reference)
            if node is None:
                return None
            self._verify_envelope(node, reference)
            self._verify_structure(node)
            resolved = self._with_completeness(node)
            cache[reference] = resolved
        self._verify_emitted_references(resolved, household)
        if depth == max_depth:
            return resolved
        for contribution in resolved.contributions:
            child_explainer = self._explainers.get(contribution.contributor.value_id)
            if contribution.expandable != (child_explainer is not None):
                raise ValueProvenanceError("contribution expandable flag disagrees with registered explainer")
            if not contribution.expandable:
                continue
            if contribution.contributor in path + (reference,):
                return self._unavailable(resolved)
            child = self._resolve(contribution.contributor, max_depth=max_depth,
                                  depth=depth + 1, path=path + (reference,),
                                  household=household, cache=cache)
            if child is None:
                raise ValueProvenanceError("expandable contributor produced no provenance")
            if child.status == "unavailable":
                return self._unavailable(resolved)
            if contribution.role != "contextual":
                if not self._verify_expanded_contribution(resolved, contribution, child):
                    return self._unavailable(resolved)
        return resolved

    @staticmethod
    def _verify_envelope(node: ProvenanceNode, reference: ValueReference) -> None:
        if node.reference != reference:
            raise ValueProvenanceError("explainer returned a node for another reference")

    @staticmethod
    def _verify_child_coordinates(parent: ValueReference, child: ValueReference) -> None:
        if child.as_of != parent.as_of or child.known_at != parent.known_at:
            raise ValueProvenanceError(
                "recursive contributor must preserve as_of and known_at")

    def _verify_subject_authority(self, subject: Subject, household: str) -> None:
        if self._authority is None or self._authority.household_for(subject) != household:
            raise ValueProvenanceError("subject is outside the authorising household")

    def _verify_emitted_references(self, node: ProvenanceNode, household: str) -> None:
        """SAFE-017-02.  Every reference Core emits carries the node's own
        coordinates, whether or not it is ever expanded.

        Verification used to run only immediately before a recursive dispatch,
        so a contributor that was not expanded — because no explainer owned it,
        or because the depth bound was reached — was returned to the caller
        unchecked.  A node could therefore present a foreign `Subject` or a
        `known_at` outside the requested frame inside an otherwise complete
        explanation.  An exclusion carries no temporal coordinates, so only its
        subject is checkable."""
        for contribution in node.contributions:
            self._verify_child_coordinates(node.reference, contribution.contributor)
            self._verify_subject_authority(contribution.contributor.subject, household)
        for exclusion in node.exclusions:
            self._verify_subject_authority(exclusion.subject, household)

    @staticmethod
    def _verify_structure(node: ProvenanceNode) -> None:
        if node.kind == "observed":
            if not node.anchors or node.contributions:
                raise ValueProvenanceError("observed nodes require anchors and terminate")
            return
        if not node.calculation_version:
            raise ValueProvenanceError("derived nodes require a calculation version")
        if not node.anchors and not node.contributions:
            raise ValueProvenanceError("derived nodes require an anchor or contribution")
        if node.quantity is not None and node.unit_or_currency is None:
            raise ValueProvenanceError("quantified nodes require a unit")
        additive = [item for item in node.contributions if item.role != "contextual"]
        seen: set[ValueReference] = set()
        for item in additive:
            if item.contributor in seen:
                raise ValueProvenanceError("repeated additive contributor")
            seen.add(item.contributor)

    def _with_completeness(self, node: ProvenanceNode) -> ProvenanceNode:
        if node.status not in MAGNITUDE_BEARING_STATUS:
            return _resolved_node(replace(node, quantity=None), None, None)
        descriptor = self._descriptors.get(node.reference.value_id)
        if (descriptor is not None and node.quantity is not None
                and node.unit_or_currency != descriptor.unit_or_currency):
            raise ValueProvenanceError("node unit differs from its descriptor")
        if node.kind == "observed" or node.quantity is None:
            return _resolved_node(node, None, None)
        if node.contributions and all(item.role == "contextual" for item in node.contributions):
            if node.unit_or_currency is None:
                raise ValueProvenanceError("quantified nodes require a unit")
            return _resolved_node(node, "indivisible", None)
        if node.unit_or_currency is None:
            raise ValueProvenanceError("quantified nodes require a unit")
        attributed = sum(item.quantity for item in node.contributions if item.role == "increases")
        attributed -= sum(item.quantity for item in node.contributions if item.role == "decreases")
        residual = node.quantity - attributed
        tolerance = descriptor.tolerance if descriptor else None
        balanced = residual == 0 if tolerance is None else abs(residual) <= tolerance
        completeness = "complete" if balanced and not node.exclusions else "partial"
        return _resolved_node(node, completeness, residual)

    @staticmethod
    def _unavailable(node: ProvenanceNode) -> ProvenanceNode:
        return _resolved_node(replace(node, status="unavailable", quantity=None), None, None)

    def _verify_expanded_contribution(self, parent: ProvenanceNode, contribution: Contribution,
                                      child: ProvenanceNode) -> bool:
        if child.status == "unavailable" or child.quantity is None:
            raise ValueProvenanceError("expanded additive contributor is unavailable")
        if child.unit_or_currency != parent.unit_or_currency:
            raise ValueProvenanceError("expanded additive contributor unit differs from parent")
        descriptor = self._descriptors.get(parent.reference.value_id)
        tolerance = descriptor.tolerance if descriptor else None
        agrees = child.quantity == contribution.quantity if tolerance is None else abs(child.quantity - contribution.quantity) <= tolerance
        return agrees


def _resolved_node(node: ProvenanceNode, completeness: str | None,
                   residual: float | None) -> ProvenanceNode:
    """Populate resolver-owned fields on a fresh node, never provider output."""
    resolved = replace(node)
    object.__setattr__(resolved, "completeness", completeness)
    object.__setattr__(resolved, "residual", residual)
    return resolved

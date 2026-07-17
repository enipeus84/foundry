"""
Scope attribution & drill-down — 000-core-domain-model.md §10.

A `Subject` is anything an Insight, Recommendation, Decision, Decision
Outcome, or `MetricRequest` can be about: a Party, an Employer, a
Mission, or a domain-declared resource. Core only knows how to expand
one kind of group membership — a household-type Party's members — into
a drill-down scope, because `member_of` is a Core relationship (000
§9). A domain's own resource-ownership expansion (e.g. "which accounts
does this person hold") is that domain's to resolve; `resolve_scope`
accepts an already-resolved set of resource ids from the caller rather
than inventing a second, domain-aware resolution mechanism Core has no
business owning (000 §3).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Subject:
    """`kind` is `"party"`, `"employer"`, `"mission"`, or a
    domain-defined resource kind (e.g. Finance's `"account"`)."""
    kind: str
    id: str


def resolve_scope(requested: Subject, entities,
                   domain_resource_ids: frozenset[str] = frozenset()) -> set[Subject]:
    """Expand a requested scope into every subject considered
    'in scope' for drill-down filtering — i.e. "which Claims/Decisions
    should a tile for this scope surface." It answers a membership
    question, not a valuation question.

    - **Group view**: a household-type Party expands to itself plus
      every Person party linked to it via `member_of`.
    - **Individual/Resource view**: a Party that isn't a group, or any
      other subject, expands only to itself, plus whatever
      domain-resolved resource ids the caller supplies (a domain's own
      ownership expansion, e.g. "the accounts Chris holds").

    **Do not reuse this as household financial-aggregation logic.** The
    returned set is a plain union of member *subjects* — it says
    nothing about which *resources* are jointly held by more than one
    member. A domain computing a household total (net worth, for
    example) must apply its own union-by-entity-id rule over its own
    ownership relations (001 §9's rule, for Finance) so a jointly-owned
    resource is counted once, not once per co-owner; naively summing
    "each member's individually-attributed value" over the members this
    function returns double-counts anything jointly held. This function
    only deduplicates *claims about* subjects, via the `set` it
    returns — it has no opinion on money.
    """
    resolved = {requested}
    if requested.kind == "party":
        party = entities.parties.get(requested.id)
        if party is not None and party.party_type == "household":
            for member in entities.members_of(requested.id):
                resolved.add(Subject("party", member.id))
    for resource_id in domain_resource_ids:
        resolved.add(Subject("resource", resource_id))
    return resolved

# RFC-017 Phase 2 — Pension Provenance Implementation Report

**Status:** Complete — merged to `main` on 2026-08-11 through merge commit
`5664cfd20f6eac76e0cb7b368af82922f5812ebe`. **Authority:** Governor amendment
`6b35850eba8ecd3654143699f7ca186e5571ccd8` (GD-P2-A through GD-P2-I).

## Delivered boundary

`finance.pension_wealth` now has a Finance-owned RFC-017 explainer. It
replays canonical events into fresh Core, Finance and pension-evidence
projections limited to `event.ts <= ValueReference.known_at`, then delegates
the root value to `FinancePensionMetricProvider`. Finance provides a root
quantity, attributed account contributions, contextual references and typed
exclusions; Core derives completeness and residual.

The explainer registers through `web.py:_build_console()` with a
`CanonicalSubjectAuthority` built from the canonical Core party and asset
registration read views. It adds no route, API, Flight Deck, Operations or
Mission Assessment consumer.

SAFE-P2-01 is remediated in that same composition boundary. The active Pension
Independence mission supplies its declared assumption-set id to the explainer;
production composition disables the explainer's isolated-test convenience
fallback to a uniquely active set. It therefore fails closed if there is no
single authoritative mission selection. Before the authority snapshot is
constructed, composition adds an in-memory `AssetRegistry` binding only for an
active pension account whose canonical Finance value-ownership links resolve
through active Core people to exactly one active household. This is a read-only
projection binding, not an `AssetRegistry.register()` call or a new event.
An absent, foreign, or ambiguous ownership path remains unregistered and is
refused by unchanged `CanonicalSubjectAuthority`.

## Governor rulings applied

GD-P2-A adds the one authorised Core vocabulary value, `conflicting`.
GD-P2-B/C use the deliberately unregistered terminal value id
`finance.pension_account_attributed_contribution` for every attributed
additive account edge (`expandable=False`). The registered contextual raw
valuation id is `finance.pension_account_raw_valuation`; ownership context is
a same-resource terminal reference, with the retained canonical ownership-link
event ids anchored on the root.

GD-P2-D maps DB-entitlement/pot-valuation conflicts to `conflicting`, missing
qualifying valuations to `unobserved`, future-only valuations to
`out_of_period`, and unavailable currency conversion to `incommensurable`.
GD-P2-E is satisfied by replaying every canonical event known at the request
coordinate, including account declaration, update, link and closure events.

GD-P2-F governs the numerical rule: attributed contribution is calculated by
the same narrow provider helpers and filtered ownership links used by
`finance.pension_wealth`. RFC-017 Phase 2 does **not** correct pension
weighting semantics. OBS-PENSION-01 is reproduced as a regression: a retained
implicit person ownership link can receive full attribution when the existing
metric has filtered out a co-owner's link.

GD-P2-G/H/I add descriptor-scoped numeric reconciliation. Composition registers
`ExplanationDescriptor("finance.pension_wealth", "GBP", tolerance=1e-6)`.
The tolerance affects Core's root completeness reconciliation and
expandable additive-child quantity agreement for this value. It does not
change the metric root, per-account attributed quantities, exclusions, or the
literal residual. Phase 2 pension attribution edges are non-expandable, so the
widened expandable-child comparator is not reachable in this consumer. Thus
representation-level float drift may be `complete` while its non-zero residual
remains disclosed. A £0.01 mismatch remains `partial`, and values without this
descriptor retain exact comparison. This is not a Finance or Core reducer
change. GD-P2-F/P2-L and
OBS-PENSION-01 are unchanged; TELMU-P2-02 remains outside this burn.

TELMU-P2-01's root cause is retained, not hidden: Finance aggregates with
sequential `total += contribution`, while Core reconciles additive edges with
`sum()`. Identical economic quantities can therefore retain a
representation-level raw residual. The accepted remedy classifies that residual
through the authorised descriptor tolerance; it does not eliminate floating
point arithmetic. Python versions may expose different insignificant residual
bits, but must retain the same tolerance-aware completeness classification.

## Evidence not used

Employee contributions, employer contributions, tax relief, transfers,
withdrawals and fees are not read. Investment growth is not derived. Pension
wealth remains a valuation rollup, not a contribution-history explanation.

## Tests and probes

`tests/test_rfc_017_phase_2_pension_provenance.py` proves household,
fractional-person and OBS-PENSION-01 equivalence; contextual raw valuation and
ownership-link evidence; conflict/missing/out-of-period/incommensurable
distinctions; ownership and valuation `known_at` replay; terminal-id registry
consistency; SubjectAuthority refusal; deterministic read-only execution.

The numeric-reconciliation regressions exercise the production pension
descriptor and composition path: `0.1 + 0.2 + 0.3` is complete within the
authorised tolerance while retaining its raw residual; a £0.01 mismatch remains
partial; exclusions still force partial; another value id remains exact; and FX,
large and small pension values retain the same absolute `1e-6 GBP` boundary.
Raw residual bits may vary across Python versions, but the tolerance-aware
complete/partial classification is the acceptance contract.

The terminal-id probe deliberately registers an explainer for the terminal
identifier and confirms the existing resolver rejects its conflict with the
non-expandable edge when traversal is requested. No resolver rule is relaxed.

The production-composition regression uses the shipped synthetic dataset's
multiple active assumption sets. Its Pension Independence mission selects the
same set that produces the available £62,000 metric result, and provenance
reproduces that root. A different active set produces a different pension
result; provenance does not guess it. The regression also confirms that an
account with no canonical person/household ownership path remains refused, and
that console construction appends no event.

## Remaining limitations

`ValueReference` has no attribution dimension, so the attributed edge remains
terminal by design. Ownership context is anchored by the canonical link events
that the metric actually retains; provenance neither restores discarded links
nor decides whether Finance's filter-before-weight behaviour is desirable.
No contribution, growth, tax-relief, transfer, withdrawal or fee provenance is
provided by this phase.

SAFE-P2-01 is closed. SAFE-P2-02 is closed: the Governor authority and the
SAFE-reviewed candidate both reached `main` through normal merge topology.
SAFE-P2-03: GOVERNANCE WORDING CORRECTED, ADVISORY RETAINED. The
expandable-child comparator remains advisory debt for any future expandable
use of this value id; no Core change is authorised. TELMU-P2-02 remains
non-blocking debt; the resolver's max-depth terminal-registry behaviour is
unchanged. Existing accepted LOW observations remain retained.

## RFC-017 closeout

RFC-017 Phase 1 is merged. Its OBS-017-A conformance remediation is merged.
Phase 2 Pension Provenance is merged. RFC-017 is complete.

Phase 2 delivers `finance.pension_wealth` provenance with account-level
attributed contributions; valuation and ownership context; `conflicting` and
`unobserved` exclusions; `known_at`-aware replay; mission-selected assumption
context; canonical household authority binding; and the pension-only `1e-6 GBP`
reconciliation tolerance. It adds no new persistence or event contract and
changes no pension metric semantics.

No Mission Assessment, Flight Deck or UI provenance consumer is implemented.
RFC-017 supplies the provenance substrate and its first Finance explainer;
consumption belongs to subsequent governed work.

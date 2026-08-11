# RFC-017 — Pension Phase 2 Blocker: Governor Ruling

**Decision: two pre-implementation Phase 2 blockers resolved. Governor
rulings GD-P2-A through GD-P2-E recorded. RFC-017 amended.**
**Ruling date:** 2026-08-11
**Authority:** Governor, via CAPCOM
**Base `main` at ruling time:** `114e003ea86954631dab97fea37e78e4a81b24d6`

**Attribution.** This document records a **Governor act**. It is transcribed
by CAPCOM at the Governor's direction and is held separately from EECOM's
investigating artefacts so the decision is never mistaken for
self-certification (RFC-100 §1.2, §9.4). This burn changes documentation
only — no `src/` or `scripts/` file is touched.

---

## Mission state verified at ruling time

| | |
|---|---|
| RFC-017 Phase 1 (amended) merge | `114e003ea86954631dab97fea37e78e4a81b24d6` |
| Proposed first Phase 2 explainer | `finance.pension_wealth` |
| BOOSTER pre-implementation contract validation | `RETURN TO GOVERNOR` — no production files changed |
| EECOM blocker clarification | `READY FOR GOVERNOR RULING` |
| Phase 2 implementation authority before this ruling | `NONE` |
| Phase 2 implementation authority after this ruling | `NONE` — unchanged; this is a governance amendment burn only |

## Blockers resolved

### Blocker A — conflicting evidence has no honest exclusion reason

An account can carry both DB entitlement evidence and pot-valuation evidence
(`pension_metrics.py:129-134`); the metric excludes the account and continues
computing a valid total from the remaining accounts. None of the three
closed `EXCLUSION_REASON` values (`unobserved`, `out_of_period`,
`incommensurable`) truthfully describes "evidence exists but conflicts."

Options traced against the resolver, not assumed:

- **Contributor-becomes-`unavailable` (A2), rejected.** Traced directly:
  `if child.status == "unavailable": return self._unavailable(resolved)`
  (`value_provenance.py:236-237`) propagates `unavailable` to the parent
  unconditionally. This structurally cannot leave the root `partial` while
  one contributor fails, and a conflicting account has no trustworthy
  quantity to declare as an additive `Contribution` in the first place.
- **Reuse `unobserved` or `incommensurable` (A3), rejected.** Both require
  overloading a value to mean something it doesn't — a unit mismatch or
  absent evidence is not the same fact as two evidence sources disagreeing.
  Governor had already excluded `unobserved` before this ruling.
- **Root refusal (A4), rejected.** `_pension_wealth` itself does not refuse
  in this situation; a provenance-level refusal would present *no
  explanation* for a value the metric surface still shows correctly — a
  regression relative to today's flat reference bag.
- **New closed value `conflicting` (A1), accepted.** Purely additive to a
  closed Core vocabulary; zero resolver code change; generalises beyond
  pensions (two disagreeing valuations, two disagreeing ownership
  assertions, mutually exclusive classifications are the same shape).

### Blocker B — `ValueReference` cannot carry attribution context

`finance.pension_wealth` is scope-generic: the same account's raw £100,000
valuation contributes £100,000 at household scope (weight always 1.0 when
`attribute_to is None`, `aggregation.py:41-46`, `pension_metrics.py:532-535`)
and £50,000 at a 50%-owner's person scope. Recursively expanding a £50,000
additive contribution into the account's own node — whose true quantity is
£100,000 — would correctly trigger the additive-agreement rule ("Loop 2") and
refuse. That refusal is *correct behaviour*, not a bug to route around.

Options traced against the resolver, not assumed:

- **Independently-registered attributed value (B1), rejected.** Any fixed,
  non-dynamic `value_id` paired with `Subject = resource:account-N` collides
  across attribution contexts — the same `ValueReference` would have to mean
  both £50,000 (Person A) and £100,000 (household). Avoiding the collision
  requires encoding attribution into `Subject` (regresses OBS-017-A) or into
  a dynamic `value_id` (explicitly forbidden). B1 does not avoid B3's cost,
  it hides it.
- **Extend `ValueReference` with attribution context (B3), rejected as
  disproportionate.** Traced blast radius: the resolver's memoisation key,
  child-coordinate verification, the registry dispatch key, and RFC-017's own
  bitemporal invariant would all be touched. A Phase 1 Core contract change,
  not warranted when a smaller model closes the gap.
- **Relax additive agreement (B4), rejected outright.** This is exactly Loop
  2's threat model — a domain declaring a contribution its expansion doesn't
  support.
- **Non-expandable attributed edge + contextual siblings (B5/B2 hybrid),
  accepted.** `Contribution.expandable = False` already means, by existing
  §5.1 text, "no explainer is dispatched for this reference" — the resolver
  never resolves, never caches, and never quantity-checks a non-expandable
  contributor (`value_provenance.py:222-241`). Attaching the resource's raw
  value and its ownership/weighting fact as `contextual` siblings (exempt
  from the agreement rule by construction, `value_provenance.py:238`) closes
  the honesty gap with zero Core changes.

## Governor rulings

### GD-P2-A — `EXCLUSION_REASON += conflicting`: **ACCEPTED**

`conflicting` **MUST** be used only when the contributor is relevant,
canonical evidence exists, two or more canonical facts disagree, and the
domain cannot safely arbitrate between them. It **MUST NOT** be used where
evidence is absent (`unobserved`), outside the requested `as_of`/`known_at`
window (`out_of_period`), or expressed in an incompatible unit
(`incommensurable`) — those three retain their original, unamended meaning.
No further exclusion values are authorised by this ruling.

### GD-P2-B — attribution-weighted additive contributions: **ACCEPTED**

```text
Contribution(
    role       = "increases" | "decreases",
    quantity   = <exact attributed amount used by the parent calculation>,
    expandable = False,
)
```

The raw resource value and its ownership/weighting fact are represented as
separate `contextual` sibling contributions, each carrying the resource's own
`Subject`. Additive agreement (Loop 2) is not relaxed — it is not triggered,
because the attributed edge is never expanded. No field is added to
`ValueReference`. No attribution is encoded into `Subject`.

### GD-P2-C — deliberately unregistered leaf `value_id`: **ACCEPTED**

A stable `value_id` **MAY** identify an attribution-weighted, non-expandable
contribution without any explainer registered for it — this is an
intentional terminal calculation edge, not an unimplemented child. It
**MUST NOT** simultaneously have a registered explainer in the same
provenance registry; the existing `§6.2` consistency check (`expandable`
must equal "an explainer is registered for this `value_id`",
`value_provenance.py:224-226`) is unchanged and continues to enforce this.

### GD-P2-D — exclusion-reason acceptance mapping: **ACCEPTED, binding**

```text
DB/pot conflict   → conflicting
Missing valuation → unobserved
```

Binding as a Phase 2 acceptance criterion: the eventual test suite **MUST**
assert both mappings directly, so the one boundary an incorrect or
evidence-hiding implementation could blur is named and defended.

### GD-P2-E — bitemporal replay scope: **ACCEPTED, binding**

Any `known_at`-filtered replay built for a Pension Phase 2 explainer
**MUST** include, at minimum: `finance.account.declared`,
`finance.account.updated`, `finance.account.linked`,
`finance.account.closed`, valuation-declaration events, and any other event
actually required by the same pension calculation path. Ownership
corrections recorded after the requested `known_at` **MUST NOT** leak
backward into an earlier explanation. This amends no existing event
semantics — `finance.account.linked` already carries a `ts` stamped at
append (`eventlog.py`); this ruling only binds which already-existing events
a Phase 2 replay must consider.

## Loop 2 — explicitly preserved

**Loop 2 remains binding, unweakened.** Any expandable additive child
**MUST** still resolve to the same quantity declared by its parent's
`Contribution`. GD-P2-B does not relax or bypass this rule — it avoids ever
triggering it for an attribution-weighted edge, by requiring that edge to be
non-expandable. `_verify_expanded_contribution`
(`value_provenance.py:321-330`) is unmodified.

## Registry — explicitly not modified

The registry consistency invariant is restated, not changed:

```text
expandable = false  AND  a registered explainer exists for that value_id
    → INVALID (raises, value_provenance.py:224-226)
```

GD-P2-C does not authorise any change to `ProvenanceResolver.register` or to
`_resolve`'s dispatch logic. No dynamic per-resource registration is
authorised or implied.

## Preserved security properties

Re-verified against the amended contract, not assumed:

| Attack | Result |
|---|---|
| Foreign account disguised as attributed child | refuses — VP-SCOPE-3 verifies every emitted contributor's `Subject`, expandable or not (`_verify_emitted_references`, unconditional) |
| Same account, two attribution contexts, cache collision | cannot occur — each top-level `explain()` call has its own fresh cache, and a non-expandable contributor is never inserted into any cache |
| Raw £100,000 expanded under a declared £50,000 additive edge | refused by unmodified Loop 2 if ever attempted; avoided by design under GD-P2-B |
| Provider asserting a fake ownership context | no new surface — an attributed quantity is a domain-declared figure, the same trust boundary the resolver already accepts for any additive contribution (Core verifies structure, not domain arithmetic, §6.1) |
| `conflicting` used to mask missing evidence | Core cannot verify a domain's choice of reason (pre-existing, same class as W9); mitigated by GD-P2-D's binding acceptance test, not by architecture |

## RFC amendment discipline applied

Per RFC-100 §9.2 — original text retained, dated amendment recorded beside
it, responsible ruling identified, normative change distinguished from
clarification. Applied to RFC-017
(`docs/rfcs/RFC-017-value-provenance-framework.md`):

| Location | Classification | Verified against repository text |
|---|---|---|
| §4.4 exclusion reason table | **NORMATIVE AMENDMENT** | confirmed — `EXCLUSION_REASON` genuinely gains a fourth closed value; original three retained unamended |
| §4.7 (new) — attribution-weighted contributions | **CLARIFICATION** | confirmed — restates existing `expandable`/`contextual` mechanics (§4.3, §5.1) for a case not previously worked through; no field, rule, or vocabulary changes |
| §14.2 (new) — Governor decision register | **RECORD, not itself normative text** | mirrors §14.1's convention |

**No other frozen RFC requires amendment.** RFC-011 (event `ts` semantics)
and RFC-006 are read as evidence that the bitemporal replay obligation
(GD-P2-E) is achievable with existing event fields; neither is changed. Had
either required amendment, this burn would have stopped and returned to
Governor — it did not.

## Phase 1 impact

```text
Phase 1 Core code remediation: REQUIRED ONLY FOR EXCLUSION_REASON VOCABULARY ADDITION
```

No resolver, `ValueReference`, `Contribution`, registry, memoisation, or
`SubjectAuthority` change is authorised by this ruling. The vocabulary
addition is additive and neutral — a literal one-value edit to the frozen
set in `core/vocab.py`, no downstream code path change (`Exclusion`'s own
validation is a membership check against the vocabulary object, not a
hardcoded list).

## Pension-first — reaffirmed

Finding both blockers by tracing resolver semantics before writing
production code — rather than discovering them mid-implementation — is
exactly the value the pension-first sequencing decision (RFC-017 §11, "proves
the honesty machinery on a real gap") was chosen for. **No basis to revert to
property-first.**

## Bounded implementation scope this ruling prepares

Once Phase 2 implementation authority is separately granted, BOOSTER's scope
is: `FinancePensionExplainer`; the `known_at`-filtered replay (scoped per
GD-P2-E); registration at `web.py:_build_console()`; focused tests; and the
one authorised Core code change, `EXCLUSION_REASON += conflicting`
(`core/vocab.py:140-141`). No other resolver, `ValueReference`,
`Contribution`, registry, or `SubjectAuthority` change is in scope.

### Explicitly out of scope

UI; a second explainer; property provenance; new canonical events; new
persistence; any change to `ValueReference`, `Contribution`,
`ProvenanceNode`, `ProvenanceResolver`, the explainer registry, or
`SubjectAuthority` beyond the one named vocabulary addition; Phase 2
implementation authority itself, which this ruling does not grant.

## Stop conditions — assessed at ruling time, none met

| Condition | Assessment |
|---|---|
| Another frozen RFC needs normative amendment | **No** |
| A Phase 1 Core shape (`ValueReference`/`Contribution`/`ProvenanceNode`/resolver/registry/`SubjectAuthority`) requires change | **No** — verified by trace, both blockers close inside the existing shapes |
| Additive agreement (Loop 2) must be relaxed | **No** — avoided, not relaxed |
| A second or unbounded exclusion taxonomy is required | **No** — one value closes the identified gap |
| Remediation requires a canonical event | **No** |
| Remediation requires persistence | **No** |
| Remediation requires a general authorisation/capability subsystem | **No** |

## Documentation of record

- RFC-017 amended: `docs/rfcs/RFC-017-value-provenance-framework.md` (§4.4
  amendment block, §4.7 new, §14.2 new).
- This ruling record: `docs/reviews/RFC-017-GD-P2-ruling.md`.
- `docs/rfcs/index.md` updated to reference this ruling.

## Disposition

```text
EXCLUSION_REASON amendment:   RECORDED
Attribution clarification:    RECORDED
Loop 2:                       PRESERVED
Phase 2 BOOSTER authority:    NOT YET GRANTED — this ruling prepares, does not grant, bounded scope
Phase 2 implementation authority: NONE
```

No implementation is performed by this ruling. No production code is
changed. No merge is authorised by this document.

---

## Addendum — GD-P2-F, 2026-08-11: zero-weight acceptance conflict

**Recorded beside the original ruling above, which is retained unmodified.**
BOOSTER returned `RETURN TO GOVERNOR` during Phase 2 pre-implementation
validation: the acceptance-test framing then attached to P2-L (a person-scope
account at zero ownership weight must show `attributed contribution = £0`,
`raw account value = £100,000`) assumed a specific numeric outcome from
`finance.pension_wealth` that the metric does not necessarily produce.

**Finding, verified by trace, not accepted on report alone.**
`FinancePensionMetricProvider._pension_accounts` calls
`FinanceAggregationService.owned_entities(person_ids, ...)`
(`pension_metrics.py:521-530`) — for a `party:person` scope, `person_ids` is
the single requested person, so `owned_entities` (`aggregation.py:64-81`)
returns only *that person's own* `OwnershipLink`s; a co-owner's link is
filtered out before weighting runs at all. `_weight`
(`pension_metrics.py:532-535`) then calls
`FinanceAggregationService.shares` (`aggregation.py:83-96`) over that
already-filtered, single-link list. Where the surviving link carries no
explicit `share`, the implicit-split rule divides the unclaimed remainder
among the links *present in the filtered list* — one link, one implicit
owner, as far as this call can see — and returns `1.0`. **The tested
zero-weight case can therefore compute `weight = 1.0` and
`attributed contribution = £100,000`, not the `£0` the prior acceptance
framing assumed**, depending on how ownership is declared. Changing that
outcome would mean changing `owned_entities`/`shares`' filtering order — a
Finance/RFC-009 pension-calculation semantics change, which RFC-017 does not
authorise and this burn does not undertake.

### GD-P2-F — provenance follows existing weighting semantics: **ACCEPTED**

RFC-017 provenance **MUST** explain the existing canonical
`finance.pension_wealth` calculation. It **MUST NOT** alter pension
ownership selection or weighting — in `owned_entities`, `shares`, `_weight`,
or anywhere else in Finance's calculation path — to satisfy a provenance
expectation. **Supersedes** the prior zero-weight-specific framing of
acceptance criterion P2-L.

### Replacement P2-L

```text
P2-L

The provenance explanation MUST faithfully reproduce the ownership
attribution actually applied by finance.pension_wealth for the requested
Subject.

The explanation MUST expose the canonical ownership evidence relevant to
that attribution.

Provenance MUST NOT change, correct, infer, or reinterpret the metric's
weighting semantics.
```

Where the existing metric genuinely computes an attributed value of zero,
provenance **MUST** represent zero honestly. Where the existing metric
computes a full or fractional value, provenance **MUST** represent that
exact result. **The metric is the numerical oracle** — the acceptance
matrix's expected quantities are defined as direct equivalence
(`provenance attributed account quantity == quantity attributed by existing
finance.pension_wealth logic`) for household scope, person scope, joint
ownership, implicit ownership, explicit fractional ownership, and a genuine
zero-weight case if one is representable under current semantics — not as a
value chosen independently of what the metric computes.

**GD-P2-B is unchanged.** The non-expandable attributed additive edge, with
raw valuation and ownership/weighting evidence as contextual siblings,
remains the attribution architecture; this addendum only binds what number
the attributed edge's `quantity` must equal — whatever
`finance.pension_wealth` actually returns, never a value provenance derives
independently.

### OBS-PENSION-01 — recorded outside RFC-017

The person-scoped filter-before-weight behaviour identified above is
recorded as a Finance/RFC-009 observation, not an RFC-017 defect:
[`../rfc-009-technical-debt.md`](../rfc-009-technical-debt.md) ("RFC-017
Phase 2 pre-implementation observation"). **Disposition: OUTSIDE RFC-017
PHASE 2.** No Finance metric modification is authorised by this ruling or by
the observation itself. The current metric is **not** classified as
incorrect by this ruling — only as a behaviour RFC-017 provenance must
report faithfully rather than second-guess. Whether `owned_entities`/`shares`
should see full account ownership state before filtering to a requested
scope is left to a dedicated Finance architecture investigation, separate
from and after RFC-017 Phase 2, at the Governor's discretion.

### Contract impact — unchanged from the original ruling

No change to `ValueReference`, `Contribution`, `ProvenanceNode`,
`ProvenanceResolver`, the explainer registry, `SubjectAuthority`,
`MetricResult`, or RFC-006. No change to `FinanceAggregationService`,
`owned_entities`, or `shares` — this addendum explicitly forbids that
change, it does not defer it. The only authorised Core code change remains
the one already recorded above: `EXCLUSION_REASON += conflicting`.

### Addendum disposition

```text
GD-P2-F:                       RECORDED
P2-L:                          SUPERSEDED
Replacement P2-L:              RECORDED
OBS-PENSION-01:                RECORDED
Pension metric change authorised: NO
RFC-017 Core change:           NONE beyond already-authorised conflicting vocabulary
Phase 2 implementation authority: NONE
```

No implementation is performed by this addendum. No production code is
changed.

---

## Addendum — GD-P2-G through GD-P2-I, 2026-08-11: numeric reconciliation

**Recorded beside the prior rulings, which are retained unmodified.** TELMU
found that `finance.pension_wealth` can produce a sequential binary-float
total that differs from Core's reconciliation of the same economic
contributions. EECOM's finding was checked against the repository: the
descriptor seam already provides a value-specific absolute tolerance; Core,
not Finance, computes residual and completeness; absent a descriptor the
comparison is exact; exclusions force `partial`; and the literal residual is
retained. No new Core mechanism is required.

### GD-P2-G — descriptor-declared numeric reconciliation: **ACCEPTED**

Representation-level disagreement between an observed value and its additive
provenance **MAY** be reconciled only through the existing
`ExplanationDescriptor` absolute tolerance. The declaration is per
`value_id`; it changes only Core's balanced/completeness classification. It
does not alter the observed value, any contribution quantity, or the literal
residual, and it never overrides an exclusion. Without a declared tolerance,
reconciliation remains exact. This is neither a Core-global epsilon nor a new
Core mechanism.

### GD-P2-H — `finance.pension_wealth` tolerance: **ACCEPTED**

The Phase 2 composition may register exactly:

```python
ExplanationDescriptor("finance.pension_wealth", "GBP", tolerance=1e-6)
```

This is an absolute tolerance of `0.000001 GBP`, scoped only to
`finance.pension_wealth`. It is not a default or a general GBP tolerance.

### GD-P2-I — P2-B numeric fidelity: **ACCEPTED**

The prior P2-B wording is retained above as the historical attribution-edge
decision. Its exact-equality framing is superseded only for root
reconciliation by the following replacement; the non-expandable attributed
edge and its raw-valuation and ownership contextual siblings are unchanged.

> **P2-B — Numeric fidelity.** The explainer **MUST** reproduce the same
> canonical economic quantities used by `finance.pension_wealth`. Core
> reconciliation **MUST** fall within the value's authorised numeric tolerance
> where one is explicitly declared by its `ExplanationDescriptor`. Without a
> declared tolerance, reconciliation remains exact.

GD-P2-F and replacement P2-L remain binding: Finance remains the attribution
oracle. Tolerance reconciles the root against those already-authorised
quantities; it does not authorise Finance to round, alter, or independently
recalculate them.

### Binding discriminator and contract classification

For clean `0.1`, `0.2`, `0.3` pension accounts, an observed root of
`0.6000000000000001` and Core-attributed total `0.6` yield a literal residual
of approximately `1.11e-16`; it is `complete` under GD-P2-H when no exclusion
exists. A £100.00 root with £99.99 attributed remains `partial`: `0.01 GBP`
exceeds the authorised tolerance. A balanced arithmetic result with any
exclusion remains `partial`.

RFC-017 §4.5 and §6.2 already define this mechanism and its ownership. This
addendum is therefore a Governor ruling and Phase 2 acceptance clarification,
not a normative RFC-017 contract amendment. The RFC decision register records
it under RFC-100 §9.2; its existing contract text is not rewritten.

### Addendum disposition

```text
GD-P2-G:                       ACCEPTED
GD-P2-H:                       ACCEPTED — finance.pension_wealth only, 1e-6 GBP
GD-P2-I:                       ACCEPTED — P2-B numeric fidelity clarified
GD-P2-F / P2-L:                UNCHANGED
Finance reducer changed:       NO
Core reducer changed:          NO
Core implementation changed:   NO
RFC-017 contract amendment:    NO
TELMU-P2-01:                   ARCHITECTURALLY CLOSED
TELMU-P2-02:                   UNCHANGED
Phase 2 BOOSTER authority:     READY — bounded descriptor composition and validation only
```

No implementation is performed by this addendum. No production code is
changed. No consumer or merge is authorised.

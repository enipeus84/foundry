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

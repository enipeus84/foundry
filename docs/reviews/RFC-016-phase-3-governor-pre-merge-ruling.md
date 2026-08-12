# RFC-016 Phase 3 — Governor Pre-Merge Ruling

**PR:** [#47](https://github.com/enipeus84/foundry/pull/47)
**Ruling date:** 2026-08-12
**Authority:** Governor
**Disposition:** HOLD accepted; governance-only completion authorised. Actual
merge remains **not authorised**.

## Authorities and identity

| Authority | SHA / reference | Disposition |
|---|---|---|
| Canonical baseline | `b35328e3b8e5df5106cfa7abb68e89a0177f4726` | Baseline for CI comparison |
| Frozen architecture | `b7957d63524e49bedcf60273ff5634ebaf8861e3` | Unchanged authority |
| Reviewed production candidate | `b81517e74adcd3e116a52ef0b7f6c3fc235f8350` | TELMU and SAFE authority remains bound to this exact SHA |
| Governance publication | `6058a2b965fdaa3e90d6910c1c75b51c8dc34e7f` | Documentation-only; not a reviewed production candidate |

Subsequent governance-only commits may publish this ruling and correct durable
provenance, but do not replace the reviewed candidate or require another TELMU
or SAFE cycle. They must contain no production or test mutation.

## GD-P3-M1 — inherited Python 3.11 CI instability: accepted for this release

The strict floating-point assertion failure comparing `0.6000000000000001`
with `0.6` is accepted as pre-existing inherited CI instability, not an RFC-016
Phase 3 regression. It was independently reproduced on canonical baseline
`b35328e3` and on PR #47's initial Python 3.11 run; a fresh retry against the
same immutable candidate passed, as did Python 3.10, 3.12 and 3.13.

RFC-016 Phase 3 changes neither the failing RFC-017 test nor the relevant
provenance implementation. No production or test repair is authorised here.
The separate, non-blocking debt and its owner are recorded as
`DEBT-017-CI-01` in [`../rfc-017-technical-debt.md`](../rfc-017-technical-debt.md).

## GD-P3-M2 through GD-P3-M5 — provenance, topology and merge gate

The RFC index is corrected to identify PR #47 and its pre-merge state. PR #47
remains the authorised merge vehicle. The reviewed candidate remains unchanged
in ancestry; the synthetic merge is accepted only as topology evidence, not
Governor merge authority.

Before a Governor merge decision, GUIDO must verify that the PR head remains
governance-only after `b81517e`, required checks are green, SAFE/TELMU evidence
remains bound to `b81517e`, the PR remains mergeable, no blocking review thread
exists, and the RFC index remains accurate. No Phase 4 adoption, Mission
instantiation, candidate mutation, production change, test change or merge is
authorised by this ruling.

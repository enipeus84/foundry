# RFC-100 Amendment 1 — Mission Declaration (Layer 2)

**Proposed — awaiting Governor Review.** Documentation Amendment Burn: this
branch contains documentation exclusively — no production source, tests,
templates, CSS or runtime configuration are changed.

Amendment 1 is a **Layer 2** change under the §1.5 change control: the
Operations Manual is amended by a Documentation Burn under Governor Review.
**Layer 1 is untouched.**

## What changes

### 1. Mission Declaration becomes pre-flight Check 0

Every burn opens with a declaration of **Spacecraft · Fuel · Effort Level ·
Mission Type · Authority**. New §6.0 defines it and a new row 0 heads the §6
pre-flight table.

The declaration must appear in the CAPCOM brief before work begins, be verified
at pre-flight, and be restated in the completion report (§11 preamble). An
incomplete declaration is **NO-GO** — the burn stops and returns to CAPCOM, and
the executing role does not fill in the missing field.

§6.0 states three limits explicitly, because this is the shape of text that
later gets over-read:

- **A statement of fact, not a grant of authority.** Naming an Authority records
  which authority governs the burn; it confers nothing and never substitutes for
  a recorded Governor act (§9.4).
- **Not a classification.** The declared Mission Type is what the brief says.
  Classification and any change to it remain governed by **FR-015** — a burn
  still may not reclassify itself.
- **Not a model compliance requirement** (§12.0). Where the executing platform
  or model differs from the declaration, the report records the actual one.

### 2. Merge-head verification

New note in §9.3, referenced from the §10 Merge row. Before executing an
authorised merge:

```text
PR head SHA  =  SAFE-reviewed head  =  Governor-approved head
```

If they differ the merge is **NO-GO** until the reviewed commit is pushed and
CI reruns on the new head. Reviews now record the commit SHA they examined, so
the comparison has something to compare against.

**Provenance — precedent P10.** At RFC-100's own merge the SAFE-confirmed head
existed only locally; the PR head was one commit behind and did not contain the
S1–S5 remediation. Post-flight caught it from the Confirmation's Repository
State line, pushed, and re-ran CI before merging. Every gate had passed
correctly — the exposure was in the handoff between them. A reviewed artefact
and a mergeable head are different objects, and nothing had previously required
them to be the same.

## Why not FR-018

CAPCOM originally proposed Mission Declaration as a Flight Rule. The Governor
ruled it a Layer 2 amendment, and this burn implements that ruling: **FR-018
deliberately does not exist.**

The enforcement strength is identical — both a Flight Rule and a pre-flight
check produce NO-GO. The difference is amendment cost: a Flight Rule is Layer 1,
changeable only by an Architecture Burn with Governor approval and re-freeze.
Check 0 also passes the boundary test that distinguishes the two layers: it
creates no new obligation, only a check on obligations Layer 1 already carries —
Effort Level under §3.2, Mission Type under §3, Authority under §2, model
statement under §12.0.

## Layer verification

| Layer | Sections | Touched? |
|---|---|---|
| **1 — Constitution** | §1–§5 | Only the Amendment 1 record in the front matter. **No Flight Rule, role authority, burn classification or lifecycle stage changed.** All 17 rule statements byte-identical to the merged manual |
| **2 — Operations Manual** | §6–§10 | **Yes** — §6 table row 0, new §6.0, §9.3 merge-head note, §10 Merge row. This is the amendment |
| **3 — Templates** | §11–§12 | §11 preamble only: every report opens with the Mission Declaration. Additive; §11 permits a template to add headings |
| **Supporting record** | §13–§17, Appendix A | §13 gains precedent P10 |

## Self-review

[`docs/reviews/RFC-100-architecture-self-review.md`](reviews/RFC-100-architecture-self-review.md)
gains an Amendment 1 section — four challenges, **no amendments**, one accepted
residual. The challenges test for layer leakage (B1), authority creep in the
declaration (B2), Check 0 as a stalling mechanism (B3), and whether P10 is a
real precedent or self-congratulation (B4).

The accepted residual: Check 0 gives the executing role a NO-GO over a brief
written by CAPCOM. No duty-to-seek clause was added because a missing field is
visible on the face of the brief and needs no search to establish. If Check 0 is
ever used to stall rather than correct, that is a finding against the role.

## Files

- `docs/rfcs/RFC-100-flight-operations-manual.md` — §6.0, §6 table, §9.3, §10,
  §11 preamble, P10, Amendment 1 record
- `docs/reviews/RFC-100-architecture-self-review.md` — Amendment 1 self-review
- `docs/rfc-100-amendment-1-pr-description.md` — this document
- `docs/rfcs/index.md` — status row

## Explicit non-goals

No Flight Rule created, altered or renumbered. No Layer 1 change. No burn
classification redesigned. No Governor authority modified. No RFC-012 work. And
no touching the outstanding Release Closeout debt for RFC-005, RFC-010, RFC-011
and RFC-100 — that is a separate burn and remains open.

## Validation

Documentation-only; the suite is unaffected. Verified: all 17 Flight Rule
statements byte-identical to merged `3bb8965`; layer tags, precedence rules and
Governor ruling rows unchanged in count; every `§n.n` reference resolves to a
heading; every anchor and relative link resolves; security documentation
COMPLETE; `git diff --check` clean.

## Review path

**Governor Review → Layer 2 amendment approved → merge.** Merge-head
verification (§9.3) applies to this PR as it does to any other.

**Do not merge yet.** Ready for Governor Review.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

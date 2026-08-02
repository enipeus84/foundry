# RFC-012 Architecture — Post-Flight Report

```text
Mission Declaration (RFC-100 §6.0 / Amendment 1) — as run
Spacecraft:    Claude Code
Fuel:          Claude Opus
Effort Level:  LOW
Mission Type:  Post-Flight
Authority:     Governor
```

*Model statement (RFC-100 §12.0.2 — a report states which model filled which
role and does not justify it against the non-normative table): the RFC-012
Architecture Burn was authored under Claude Fable at HIGH effort; the
Governor Remediation Burn, the Architecture Freeze, the SAFE Architecture
Review and this Post-Flight were executed after the Flight Director set the
session model to `claude-opus-5`.*

Date: 2026-08-02. Role: GUIDO/TELMU post-flight (RFC-100 §10, report shape
§11.6).

## RFC-012 ARCHITECTURE MERGED AND GREEN

**Architecture status: FROZEN.** **Implementation status: HOLD — not
authorised.**

## Merge

Merge-head verification (§9.3) passed: all three SHAs are the same commit,
recorded here as the durable record.

| Item | Value |
|---|---|
| PR | [#30 — RFC-012: Telemetry Operations Console Architecture](https://github.com/enipeus84/foundry/pull/30) |
| Governor-approved head | `9dbf3f16a00d422ab052bf908912417a8fbb3c7f` |
| SAFE-reviewed head | `9dbf3f16a00d422ab052bf908912417a8fbb3c7f` |
| PR head at merge | `9dbf3f16a00d422ab052bf908912417a8fbb3c7f` |
| **Three-way equality** | **CONFIRMED** |
| Merge commit | `34e9864693aba5734e56637e14184f2ef4ccacd8` |
| Merge strategy | Merge commit, matching established repository practice (PRs #28, #29) |
| Merge timestamp | 2026-08-02T19:01:19Z |
| Merged by | Governor merge authority (`enipeus84`) |
| Base | `main` at `b12f315` |

**Governor decision:** merge authority GRANTED for head
`9dbf3f16a00d422ab052bf908912417a8fbb3c7f`, conditional on the SAFE report
being posted durably, exact merge-head equality, PR mergeability, and no
later commit. All four conditions were satisfied before merge.

**Diff — documentation exclusively:**

```text
docs/rfcs/RFC-012-telemetry-operations-console.md | 829 +++++++++
1 file changed, 829 insertions(+)
```

No production source, tests, templates, CSS, fixtures or runtime
configuration were changed by the merged PR (RFC-100 §3.1 rule 3).

## Post-Merge CI

**GREEN.** The first post-merge `main` workflow passed: `tests` run
[`30762432648`](https://github.com/enipeus84/foundry/actions/runs/30762432648),
conclusion `success`, 43s, started 2026-08-02T19:01:21Z. FR-016 is satisfied;
the burn is not reopened.

Pre-merge CI on the reviewed head was green across Python 3.10, 3.11, 3.12
and 3.13.

## Cleanup

| Item | Disposition |
|---|---|
| Local branch `rfc-012-telemetry-operations-console` | **Deleted** after confirming `9dbf3f1` is an ancestor of `main` (`git merge-base --is-ancestor`), using `git branch -d` so an unmerged branch would have been refused |
| Remote branch `origin/rfc-012-telemetry-operations-console` | **Deleted** |
| Remote-tracking references | **Pruned** (`git remote prune origin`) |
| Remaining RFC-012 architecture branches | **None** |
| Scratch artefacts in the repository | **None** — drafting artefacts were held outside the repository in the session scratchpad |

## Repository State

| Check | Result |
|---|---|
| Current branch | `main` |
| Local `main` = `origin/main` | Yes — both `34e9864693aba5734e56637e14184f2ef4ccacd8` |
| Working tree | Clean |
| `git diff --check` | Clean |
| RFC-012 present on `main` | Yes — `docs/rfcs/RFC-012-telemetry-operations-console.md`, introduced by `9dbf3f1` |
| RFC-012 implementation present | **None** — no console source, tests, templates, CSS, fixtures or configuration exist |
| Commits after the merge affecting this mission | None |

## Documentation Coherence

Per RFC-100 §10 and FR-017:

| Item | State |
|---|---|
| RFC index row | **Updated by this burn** — RFC-012 recorded under "Proposed architecture, not yet implemented" |
| `PROJECT_STATUS.md` | **Updated by this burn** — RFC-100 and RFC-012 added to the project-state summary; project-state facts only |
| CHANGELOG entry | **Absent — recorded as a gap.** Not created by this burn: RFC-012 is architecture only, and the CHANGELOG/version debt is the scheduled Release Closeout below |
| Version bump | **Absent — recorded as a gap.** `pyproject.toml` has read `1.7.0` since RFC-009 |

The CHANGELOG and version gap is not new to RFC-012 and is not repaired here.
It is the G6 obligation, scheduled below, and remains open.

## Advisory SAFE findings carried forward

The SAFE Architecture Review returned **SAFE: GO** with no remediation
required, and is posted durably at
[PR #30 comment](https://github.com/enipeus84/foundry/pull/30#issuecomment-5159867761),
bound to head `9dbf3f16a00d422ab052bf908912417a8fbb3c7f`.

Two advisory findings survive the merge and **must be included in the
eventual BOOSTER implementation brief**:

```text
SAFE-012-01
Every state-changing Operations Console route must require authenticated,
household-scoped access and signed, purpose-bound, body-only CSRF protection,
with regression coverage.

SAFE-012-02
Household membership currently acts as de-facto confirmation authority.
RFC-012 must not expand that authority model. The inherited risk belongs to
future delegation and authorisation architecture.
```

SAFE-012-01 is a low-severity explicitness gap, not a permitted-behaviour
defect: RFC-012 AC-4 already confines every console mutation to RFC-011's
existing provider and confirmation gate, which carry the controls today.
SAFE-012-02 describes inherited RFC-011 authorisation behaviour that RFC-012
neither introduces nor widens; RFC-012 §11 excludes any role or permission
system.

The SAFE review also recorded a declared independence residual: RFC-012 was
authored as EECOM and reviewed as SAFE in the same session. RFC-100 §12.2
permits this — different artefacts, different lifecycle stages, Governor
retaining approval — but independence is weaker than the rule contemplates. A
fresh-context SAFE pass against the same SHA remains available to the
Governor.

## Next Burn Recommendation

**No next burn is implicit.** The following is the recorded programme
sequence; only the Release Closeout burn is scheduled, and CAPCOM issues it.

```text
RFC-012 architecture post-flight        ← this report
→ Release Closeout burn
→ Governor closeout verification
→ RFC-012 bounded implementation burn
```

**Scheduled next mission — Release Closeout (RFC-012 ruling G6):**

| Item | Value |
|---|---|
| Scope | RFC-005, RFC-010, RFC-011, RFC-100 |
| Work | CHANGELOG entries, version bump decision, tag decision, index rows |
| Operational owner | GUIDO |
| Authority | Governor |
| Execution spacecraft | Claude Code |
| Validation | TELMU |

**Binding conditions, stated explicitly:**

- **Release Closeout must complete before the RFC-012 implementation
  merge.** Scheduling satisfied the pre-architecture-merge half of G6;
  completion satisfies the pre-implementation-merge half.
- **RFC-012 implementation is not yet authorised.** No BOOSTER burn may
  begin until the frozen architecture, the completed Release Closeout and a
  CAPCOM implementation brief are all in place. RFC-012 AC-12 forbids any
  console source before freeze and merge; freeze and merge are now done, but
  authorisation is a separate act that has not occurred.

**Also open, not scheduled by this burn:**

- **RFC-011 Phase 5 Governor gate** remains independently open (RFC-012 G3,
  MODIFIED — REMAINS SEPARATE). It must be discharged before any RSU, CSV,
  email, OCR, Open Banking, broker or pension-provider channel burn.
  RFC-012's visual gate does not satisfy it.
- **RFC-012 G5 visual gate** falls after the bounded reference
  implementation and before any expansion.
- **RFC-013 and RFC-014** exist only as provisional programme direction.
  Neither has approved architecture; each requires its own architecture burn
  and boundary challenge. Nothing in this report advances either.

## Mission Archive

All artefacts are in the repository or on the PR at durable paths:

| Artefact | Location |
|---|---|
| Frozen architecture | [`docs/rfcs/RFC-012-telemetry-operations-console.md`](rfcs/RFC-012-telemetry-operations-console.md) |
| Governor amendment record (A1–A6) | RFC-012 § "Revision 2 — Governor Remediation" |
| Governor rulings G1–G6 | RFC-012 §13 |
| Acceptance criteria AC-1…AC-13 | RFC-012 §14 |
| PR description, incl. G6 scheduling record | [PR #30](https://github.com/enipeus84/foundry/pull/30) |
| SAFE Architecture Review | [PR #30 comment](https://github.com/enipeus84/foundry/pull/30#issuecomment-5159867761) |
| This Post-Flight Report | `docs/rfc-012-architecture-post-flight-report.md` |
| Index row | [`docs/rfcs/index.md`](rfcs/index.md) |

No dedicated technical-debt register is created: an Architecture Burn
produces no implementation debt, and the two advisory SAFE findings plus the
G6 obligation are recorded above and in the RFC index.

## Verdict

```text
MISSION COMPLETE WITH FOLLOW-UP
```

The RFC-012 architecture mission is operationally closed: merged with
three-way head equality, post-merge CI green, branches cleaned, repository
verified, documentation coherent. The follow-up qualifier is carried by three
open obligations that are recorded, owned and sequenced rather than resolved
— the G6 Release Closeout, the two advisory SAFE findings destined for the
implementation brief, and the separately-open RFC-011 Phase 5 gate.

Architecture frozen. Implementation on HOLD.

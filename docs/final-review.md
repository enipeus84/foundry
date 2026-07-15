# Foundry V1.0 — Final Engineering Review

Reviewer stance: what would a sceptical senior engineer, cloning this
cold, actually think? Scores reflect that standard, not effort.

## Scores

| Area | /10 | Justification |
|---|---|---|
| Architecture | 9 | One storage primitive, deterministic projection, provenance everywhere, regression oracle enforcing incremental == rebuilt. Loses a point for the truncation gap in integrity (documented, unanchored). |
| Code quality | 8 | ~750 lines of core, no dead code, no clever abstractions, error taxonomy earns each type. Loses points: retrieval scoring lives inside the kernel rather than as a named projection; two near-duplicate keyword utilities. |
| Documentation | 8 | Every module answers *why it exists* and states trade-offs; architecture doc lists constitutional invariants; roadmap includes a "never" list. Loses points: no API reference generation, no docstring examples in canon/kernel. |
| Testing | 8 | 34 tests, each named for the claim it defends; regression oracle for the one real optimisation; tamper and insertion detection tested. Loses points: real adapters untested against live APIs in CI (requires keys); no property-based fuzzing of the parser. |
| Developer experience | 8 | Clone -> `./validate.sh` -> transcript in well under five minutes; copy-paste examples verified working; zero-dependency core installs anywhere. Loses points: CLI is thin; no `--help` argparse polish. |
| Maintainability | 9 | Stdlib-only core, src layout, pinned optional extras, one file per concept, ~200 line ceiling per module. The 10-year bet is credible precisely because there is so little here. |
| Extensibility | 8 | Adapters (~15 lines/provider) and ingestors are clean seams; projections are additive by construction. Loses points: no formal projection interface — the embedding index will define it when it arrives, which is deliberate but still a gap. |
| Open-source readiness | 8 | License, contributing guide with hard invariants, changelog, versioning, honest limitations section. Loses points: no CI config, no code of conduct, no issue templates. |
| Commercial readiness | 4 | Honest number. This is a validated substrate, not a product: no multi-user story, no UI, no deployment path, confidence values are decorative. The commercial asset is the corroboration mechanism on the roadmap, not the current binary. |

## What remains imperfect

- **Truncation blindness.** Deleting trailing log lines is undetectable
  from within. Fix is small (external head-hash anchor) and is first in
  the roadmap queue; shipped as a documented limitation rather than a
  rushed feature.
- **Confidence is theatre.** Stored, clamped, displayed, never trusted.
  The honest fix is corroboration, which is V2 by decision, not
  oversight.
- **Retrieval is a placeholder** and is coupled into the kernel. When
  the embedding projection lands, retrieval should move behind a
  projection interface; extracting that interface *now* would be
  speculation about a consumer that doesn't exist yet.
- **No CI.** Tests exist; automation running them on every push does
  not. Trivial to add, environment-dependent, left to the repo host.
- **Real adapters are validated by humans with keys**, not by the test
  suite. Recorded-fixture tests would be mocks wearing a costume;
  declined on honesty grounds.

## What should wait until V2

Conflict detection, cross-model corroboration, semantic search,
temporal queries, trust scoring, snapshots. All specified with
rationale in docs/roadmap.md. None requires substrate changes — which
is the strongest evidence the substrate is right.

## What should never be added

- Any mutable path to events, including "administrative corrections."
  Corrections are supersession events, full stop.
- A Canon write path that bypasses the log.
- Mandatory dependencies, frameworks, or model SDKs in the core.
- Auth, billing, or telemetry inside the substrate. Product layers may
  exist above it; the substrate remains a file the user owns.
- Background processes. Everything Foundry does is visible, invocable,
  and stoppable by its owner.

## Verdict

The repository now reads as what it is: a small, deliberate system with
one idea, defended by tests, documented by its trade-offs, installable
in one command, and verifiable in five minutes. The 10-year durability
claim rests on three facts — stdlib-only core, one storage primitive,
deterministic replay — each of which is enforced, not aspirational.

Ship it. Then run the real-model validation and archive the transcript.

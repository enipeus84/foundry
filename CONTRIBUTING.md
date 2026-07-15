# Contributing to Foundry

## The bar

Every change is evaluated against one question: **does this strengthen
the demonstration that memory belongs to the substrate, not the model?**
If not, it belongs in `docs/roadmap.md`, however good the idea.

## Constitutional invariants (non-negotiable)

1. The event log is append-only. No edit or delete paths, ever.
2. Claim mutations are events. The Canon never gets its own write path.
3. Replay is deterministic — no model participates in projection.
4. Model identity is recorded on every derivation.
5. Model failure must never corrupt the substrate.

A PR that violates one of these is a new architecture, not a
contribution.

## Practical rules

- Core stays stdlib-only. Model SDKs live behind optional extras.
- Prefer obvious code. If a reviewer needs the comment to understand
  the code, rewrite the code, then keep the comment for the *why*.
- Every behavioural change needs a test. Tests are named for the
  architectural claim they defend.
- Run `./validate.sh` before submitting; all 34+ tests must pass and
  the transcript must generate.
- New model adapter? Subclass `_RealAdapter`, implement `_complete`,
  ~15 lines. If it needs more, raise an issue first.

## What we will decline

Features on the "never" list in the final review (auth, billing,
frameworks in core, background daemons) — see docs/roadmap.md.

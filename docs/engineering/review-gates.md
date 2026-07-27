# Foundry Engineering Review Gates

## Purpose

Foundry is designed to be a long-lived platform rather than a collection
of individual features.

To preserve architectural integrity, every significant change passes
through independent review gates before it is merged.

The objective is not to maximise process.

The objective is to maximise confidence that changes remain:

-   Secure by Design
-   Architecturally consistent
-   Deterministic
-   Auditable
-   Maintainable
-   Honest in their presentation of data

Implementation and governance are deliberately separated.

The engineer (human or AI) implements the change.

Independent reviewers challenge the implementation.

Only after those reviews pass should work be merged.

------------------------------------------------------------------------

# Engineering Workflow

``` text
RFC
    │
    ▼
Implementation
(Codex / Claude / Human)
    │
    ▼
Automated Tests
    │
    ▼
Architecture Gate
    │
    ▼
Security Gate
    │
    ▼
Additional Review Gates (future)
    │
    ▼
Human Approval
    │
    ▼
Merge
```

Every gate is read-only.

No reviewer modifies code.

------------------------------------------------------------------------

# Review Philosophy

Reviewers exist to protect the platform rather than the implementation.

Every reviewer must:

-   remain evidence-based
-   distinguish facts from opinions
-   avoid speculative findings
-   produce actionable feedback
-   clearly identify architectural risk
-   stop once the review is complete

Reviewers do **not**:

-   edit code
-   implement fixes
-   commit
-   merge
-   modify Git state

Implementation is always a separate step.

------------------------------------------------------------------------

# Severity Definitions

## Critical

A verified issue that makes the implementation unsafe to merge.

**Merge policy:** BLOCK

## High

A verified issue that materially weakens correctness, security or
architecture.

**Merge policy:** BLOCK

## Medium

A real issue that should be addressed but may be deferred.

Must be documented if deferred.

## Low

Minor improvements that may be deferred.

------------------------------------------------------------------------

# Current Review Gates

## Architecture Gate

Implemented by:

`adversarial-architect`

Reviews:

-   architectural boundaries
-   domain ownership
-   deterministic replay
-   technical debt
-   projection correctness
-   scaling
-   test coverage
-   platform integrity

Blocks merge when:

-   Critical \> 0
-   High \> 0

## Security Gate

Implemented by:

`security-reviewer`

Reviews:

-   authentication
-   authorisation
-   household isolation
-   session security
-   secrets
-   provenance
-   event integrity
-   dependency risk
-   abuse cases

Blocks merge when:

-   Critical \> 0
-   High \> 0

------------------------------------------------------------------------

# Current Merge Policy

A change may be merged when:

-   Architecture Gate = APPROVE
-   Security Gate = APPROVE
-   Full automated test suite passes
-   No unresolved Critical findings
-   No unresolved High findings
-   Deferred Medium/Low findings are documented

The project maintainer retains final responsibility for every merge.

------------------------------------------------------------------------

# Planned Review Gates

-   Data Integrity Gate
-   Performance Gate
-   Product Design Gate
-   Release Gate

------------------------------------------------------------------------

# Principles

## Secure by Design

Security is designed into the platform rather than added later.

## Models are Replaceable

Implementation may come from any model.

Review standards remain constant.

## Independent Governance

The implementation model never approves its own work.

## Evidence Before Opinion

Every finding should reference observable evidence.

## Honest Software

Foundry must never present greater certainty than the underlying
calculation supports.

## Continuous Improvement

Review gates evolve over time while preserving these principles.

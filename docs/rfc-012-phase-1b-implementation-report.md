# RFC-012 Phase 1B — Operations Console Surface — Implementation Report

Mission declaration: Flight Director authority; Spacecraft Codex; Fuel GPT-5.6;
Effort STANDARD; Mission Type Engineering Implementation.

## Scope delivered

Phase 1B adds the authenticated Operations Console surface at `/operations`
and its manual capture form at `/operations/capture`. The surface renders the
frozen `OperationsConsoleModel` queue and terminal summary without duplicating
platform calculations. Queue actions deep-link to the existing authenticated
RFC-011 acquisition inbox for proposal review and evidence/provenance review.
Manual capture is delegated to RFC-011's existing `ManualAcquisitionProvider`
and `FinanceManualInterpreter`; the console appends no canonical events and
does not introduce persistence, vocabulary, entities, or a new write path.

The existing `/acquisition/inbox` remains available and unchanged, satisfying
AC-10's parity-before-retirement rule.

## SAFE-012-01

All Phase 1B state-changing routes require an authenticated, configured
session; the active household is checked before a stream may be captured; and
the capture route requires a signed, purpose-bound, body-only CSRF token. Query
parameters, alternate content types, duplicate fields, forged purposes, and
cross-household streams fail closed. Regression coverage exercises anonymous
access, query-string CSRF rejection, and the preserved acquisition inbox.

## Validation

Focused RFC-011/RFC-012 web and model tests: **33 passed**. The existing
Starlette/httpx deprecation warning remains pre-existing. Full-suite validation
is required before the implementation PR is opened.

## Deviations and residual risks

No RFC or architecture text was modified. No Phase 1B functionality outside
the approved proving slice was introduced. The capture form intentionally
delegates event-shape and confirmation safety to the frozen Finance manual
contract; broader domain capture remains outside RFC-012. Governor review
should confirm the visual/product gate (G5) against a live preview before any
future surface expansion or retirement of `/acquisition/inbox`.

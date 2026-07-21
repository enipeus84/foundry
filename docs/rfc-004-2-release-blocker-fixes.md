# RFC-004.2 — Release Blocker and Pre-merge Fixes

Status: verified and intentionally uncommitted.

## Implemented scope

Only the release blockers and the two fixes explicitly included in the
review's narrow pre-merge recommendation were implemented.

### Release blocker: range-aware hero

The Flight Plan why-line now distinguishes target-value and target-range
Missions. A range Mission renders, for example:

> Retirement corridor: net worth £480,760 against a target range of
> £500,000–£600,000.

It can no longer render `against a target of —` for a supported range Mission.
An additional defensive branch reports when no numeric target is declared.

### Release blocker: honest range gauge

The target-value gauge still shades its ±1 tolerance band because that band is
Core's on-track policy for a target value.

Range Missions retain the signed variance, status-coloured tick, and ±3
tolerance scale, but omit the shaded centre band. Core marks every value
outside the declared range as WATCH or OFF COURSE; omitting the band prevents
a WATCH tick from appearing inside an apparently on-target region.

Regression coverage now proves both behaviours:

- an in-range Mission states its interval and never prints a dash;
- an outside-range WATCH Mission has its tick and variance but no target band;
- a target-value Mission still has its valid tolerance band.

### Agreed pre-merge fix: changelog accuracy

The v1.5.1 changelog no longer claims that `SINCE FIRST OBSERVATION` appears on
the cash-flow drill-down header. It accurately states that the qualifier is on
the opening telemetry instrument and that the drill-down exposes the raw
result without a separate period header.

### Agreed pre-merge fix: release version

`pyproject.toml` and `foundry.__version__` now report `1.5.1`. Consequently the
health response and Flight Deck footer also report 1.5.1. A regression test
prevents this release metadata from silently returning to 1.0.0.

## Explicitly not implemented

The following review recommendations remain out of scope for this pass:

- per-request replay/performance work;
- footer content changes or test-count redesign;
- HEAD route support;
- logout method changes;
- HSTS or additional CSP changes;
- stale-metric presentation;
- navigation or dead-end destination changes;
- gauge visibility/cosmetic redesign beyond the semantic range correction;
- broader typography or Earthrise changes.

## Regenerated visual review

- [Desktop nominal](rfc-004-2-visual-review/post-review/desktop.jpg)
- [Tablet nominal](rfc-004-2-visual-review/post-review/tablet.jpg)
- [Mobile nominal](rfc-004-2-visual-review/post-review/mobile.jpg)
- [Desktop range WATCH edge state](rfc-004-2-visual-review/post-review/range-watch-desktop.jpg)

The edge-state browser audit confirmed:

- status `WATCH`;
- hero target range `£500,000–£600,000`;
- variance `−£19,240 OUTSIDE RANGE`;
- one live gauge and zero shaded target bands;
- footer version `v1.5.1`;
- no horizontal overflow.

## Verification

- Focused range/gauge/cash-flow tests: 6 passed.
- Focused web/version tests: 7 passed.
- Full suite: 278 passed in 2.10 seconds.
- One existing Starlette `httpx` compatibility deprecation warning remains.
- No commit, PR, merge, deployment, or unrelated recommendation was applied.

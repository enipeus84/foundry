# RFC-004.2 — Flight Deck Visual Refinement

Status: ready for design review; intentionally uncommitted.

## Scope and constitutional check

RFC-004.2 was implemented as a presentation-only refinement on top of the
uncommitted RFC-004.1 working tree. The Engineering and Design Constitutions
remain satisfied. No Core, Finance, Event Log, business-rule, schema, API,
authentication, or mission-evaluation file was changed for RFC-004.2.

The Design Constitution's definition of progress remains authoritative:
progress is distance or deviation from a declared target, not a decorative
completion percentage. Only the real Coast FIRE mission receives a current
position, target envelope, status, and drill-down. Other mission lanes are
explicitly disabled planned views with `TARGET NOT DECLARED` and no values.

## Major design decisions

### Earthrise is the environment

The hero is now full viewport width, begins behind the global header, has no
card border or radius, and is 620 px deep on desktop. The text aligns back to
the content grid while the image extends to the browser edges. A restrained
legibility scrim remains, but the image is materially less obscured.

The existing above-the-fold Earthrise remains preloaded and high-priority
rather than lazy-loaded. It is the primary visual and delaying it would harm
first paint; no below-the-fold imagery exists to lazy-load.

### Telemetry, not KPI widgets

The exact four instruments remain Net Worth, Liquidity, Cash Flow, and Runway.
Rounded boxes, vertical cell borders, `AVAILABLE`, and `VIEW TELEMETRY` were
removed. The instruments are now numbered channels on one shared datum line,
with the values and measurement-period qualifier carrying the hierarchy.
Drill-down remains available through the instrument itself and a quiet arrow.

### Apollo Missions is the programme

The mission area now displays four stable programme lanes:

1. Mortgage Freedom — planned, target not declared.
2. Financial Independence — live; contains the real `Coast FIRE by 2038`
   mission and its existing net-worth target-deviation instrument.
3. Retirement — planned, target not declared.
4. Children's Future — planned, target not declared.

Planned lanes use an empty dashed rail, disabled link semantics, muted status,
and no progress figure. The real Mission name remains visible below the
programme title, so the presentation taxonomy does not hide or rename the
underlying record. Unknown future real Missions remain visible as additional
live rows rather than being forced into a false category.

### One reading order

The prior side-by-side supporting panels were removed. Flight Director now
precedes Recent Course Corrections on every breakpoint, following the required
order. The Director is presented as one calm transmission with a mission-green
rule and a maximum of three sentences. Confidence chrome and recommendation
counts were removed from the prose; verified evidence date remains.

Recent Course Corrections remains one component. The synthetic review fixture
shows only its evidence-backed measurable outcome: employer concentration fell
from roughly 31% to about 15%.

### Scope is subordinate

The boxed scope grid became a quiet text strip. Household carries the single
green operational marker. Chris, Fiona, Hamish, and Harriet remain native
disabled controls labelled `FUTURE SCOPE`.

## RFC-004.1 before / RFC-004.2 after

| Area | RFC-004.1 | RFC-004.2 |
| --- | --- | --- |
| Hero | Earthrise inside a framed 440 px region | Full-bleed 620 px Earthrise environment |
| Telemetry | Four ruled cells with availability and CTA labels | Four numbered instruments driven by typography |
| Missions | One compact real row | Four-lane programme; one live and three honest planned lanes |
| Supporting content | Director and corrections compete side-by-side on desktop | Director then corrections in one vertical reading order |
| Scope | Boxed selector grid | Quiet operational/planned text strip |
| Mobile | Strong but compact hero and one mission | 560 px hero, 2×2 telemetry, four sequential mission lanes |

### Baseline captures

- [Desktop RFC-004.1](rfc-004-2-visual-review/before/desktop-rfc-004-1.jpg)
- [Tablet RFC-004.1](rfc-004-2-visual-review/before/tablet-rfc-004-1.jpg)
- [Mobile RFC-004.1](rfc-004-2-visual-review/before/mobile-rfc-004-1.jpg)

### Refined captures

- [Desktop RFC-004.2](rfc-004-2-visual-review/after/desktop-rfc-004-2.jpg)
- [Tablet RFC-004.2](rfc-004-2-visual-review/after/tablet-rfc-004-2.jpg)
- [Mobile RFC-004.2](rfc-004-2-visual-review/after/mobile-rfc-004-2.jpg)
- [Mobile navigation drawer](rfc-004-2-visual-review/after/mobile-drawer-rfc-004-2.jpg)

The authenticated page was rendered using the existing synthetic demo event
builder and signed TestClient session. The in-app browser caps individual
captures at 1,395 px, so complete-page mock-ups were assembled from overlapping
browser-rendered scroll segments without altering page content.

## Visual refinement pass

The first RFC-004.2 render was reviewed at 1440, 768, and 375 px. It confirmed
the full-bleed hero and programme hierarchy, but the chevron on planned mission
rows looked actionable. The refinement replaced those chevrons with a disabled
dash while retaining the real Mission's drill-down arrow. Final DOM checks
found no horizontal overflow at any reviewed breakpoint.

## Accessibility and security review

- Heading order is H1, Flight Plan, Primary Telemetry, Apollo Missions, Flight
  Director, then Recent Course Corrections.
- Header, primary navigation, main, and footer landmarks remain present.
- Status and planned/live state are expressed in text, not colour alone.
- Planned mission lanes expose `aria-disabled="true"`; individual scopes use
  native disabled buttons.
- The drawer still supports deliberate click, Escape close, focus trapping,
  focus return, and a clear close control.
- The only added motion is a two-pixel hover lift/shift; all new transitions
  are removed under `prefers-reduced-motion`.
- Earthrise retains meaningful alt text and intrinsic dimensions.
- No inline event handler, dynamic HTML injection, `eval`, new script, secret,
  third-party runtime request, CSP relaxation, or unauthenticated user-data
  asset was introduced.

## Performance

RFC-004.1 initial load measured 136,666 bytes. RFC-004.2 measures 139,614
bytes: 23,987 bytes HTML, the unchanged 114,086-byte Earthrise WebP, and the
unchanged 1,541-byte drawer script. The refinement adds 2,948 bytes of HTML and
CSS, no dependency, no image, and no JavaScript.

## Verification

- Python compilation: passed.
- Focused Mission Control and web tests: 35 passed.
- Full suite: 276 passed in 3.65 seconds.
- Warning: one existing Starlette `httpx` compatibility deprecation warning.
- Responsive widths verified without horizontal overflow: 1440, 768, 375 px.
- Work remains uncommitted. No PR, merge, or deployment operation was run.

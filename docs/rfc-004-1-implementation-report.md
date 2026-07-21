# RFC-004.1 — Flight Deck Visual Recovery

Status: ready for visual review; intentionally uncommitted.

## Constitutional check

The Engineering Constitution was read in `docs/architecture.md` and
`CONTRIBUTING.md`. The Design Constitution was read from the authoritative
Google Doc supplied with the RFC. No conflict was found.

The Design Constitution says progress is deviation from a target or range,
not a generic percentage. The RFC's request for prominent mission progress
bars is therefore implemented as a target-deviation instrument: a target
envelope, the current position, the actual value, and the variance. No
percentage or historical movement is invented.

No Core, Finance, Event Log, schema, authentication, mission-evaluation, or
business-rule file was changed.

## Pre-edit visual gap analysis

- The synthetic blue sphere had no photographic credibility or emotional
  role, so the page lacked a recognisable visual identity.
- Flight status was present but sat inside a conventional banner/card rather
  than feeling integrated with the system view.
- The four metrics were isolated rounded cards with uniform visual weight,
  producing a dark-SaaS grid rather than telemetry.
- The real mission appeared as a small secondary card. Its target-deviation
  gauge did not carry the page's emotional centre.
- Flight Director, mission, and evidence areas repeated the same card chrome,
  flattening the information hierarchy.
- The navigation drawer was CSS-only and lacked a proper close control,
  Escape handling, focus trapping, a scrim, and focus return.
- The intended household/member scope hierarchy was absent.
- The prior 375 px capture clipped horizontally, showing that mobile was a
  shrunken desktop composition rather than a designed breakpoint.

## Implemented composition

- Replaced the abstract sphere with a project-local photographic Earthrise.
  The image is a 1774×887, 114,086-byte WebP with intrinsic dimensions,
  meaningful alt text, preload, and `fetchpriority="high"`.
- Integrated Flight Plan status, mission rationale, strategic risk, and the
  real course-correction count directly into the hero image.
- Rebuilt the four exact top-level metrics as a ruled telemetry rail with
  typography and alignment doing most of the visual work.
- Rebuilt Apollo Missions as full-width numbered mission rows with a prominent
  target-envelope instrument and drill-down affordance. Only the one real
  mission in the supplied data is shown.
- Reduced Flight Director and Recent Course Corrections to one restrained
  supporting row. Only one evidence-backed review and one recommendation are
  rendered because those are the available records.
- Added the honest scope strip: Household is active; Chris, Fiona, Hamish, and
  Harriet are visibly disabled future scopes.
- Replaced the permanent/sidebar pattern with a deliberately opened modal
  drawer. A 1,541-byte local script provides Escape close, focus trapping,
  focus return, backdrop close, and body-scroll locking.
- Designed desktop, tablet, and mobile arrangements separately. Mobile order
  is status, core message, four KPIs, mission, correction, Flight Director,
  scope, and system evidence.

## Reference comparison and refinement

Compared with the approved reference, the final page now shares the decisive
photographic header, status-first hierarchy, compact navigation, restrained
green semantics, thin dividers, telemetry alignment, and horizontal mission
instrument. It removes the reference's unsupported multi-mission percentages,
trend lines, confidence theatre, and calculated impacts where the current read
contracts cannot support them.

The first responsive review found that CSS auto-placement moved the mission
name below its gauge at 375 px. The refinement explicitly placed mission
identity before status and telemetry, kept sign-out visible on mobile, added
the overall Flight Plan sentence to Flight Director, and increased the
legibility of disabled future scopes. All three final captures have zero
horizontal overflow.

## Visual evidence

- [Desktop, 1440 px](rfc-004-1-visual-review/desktop-final.jpg)
- [Tablet, 768 px](rfc-004-1-visual-review/tablet-final.jpg)
- [Mobile, 375 px](rfc-004-1-visual-review/mobile-final.jpg)
- [Mobile navigation drawer](rfc-004-1-visual-review/mobile-drawer.jpg)

The fixture was rendered through FastAPI's authenticated TestClient using the
existing synthetic demo event builder and a signed test session. No production
authentication bypass was added. Because the in-app browser caps a single
capture at 1,395 px, each complete-page image was assembled from overlapping
browser-rendered scroll segments; no page content was altered.

## Evidence and honesty review

- Four KPI values still arrive through the Metric Registry.
- Mission status still arrives through the existing mission evaluator.
- The mission gauge uses the existing target/tolerance read values.
- Strategic risk and course-correction counts come from existing composed
  state and active evidence claims.
- Recent corrections are existing Decision Review claims.
- No sparkline, historical trend, mission, percentage, impact, risk rating,
  confidence value, review date, or individual metric was fabricated.

## Accessibility review

- One banner, primary navigation, main landmark, and footer are present, with
  one `h1` followed by section `h2` headings.
- Earthrise has meaningful alt text; status is explicit text as well as colour.
- A skip link and visible focus ring are present.
- The drawer has an accessible name, modal semantics, a clear close control,
  Escape handling, forward/backward focus wrapping, and focus return.
- Disabled member scopes are native disabled buttons and labelled FUTURE SCOPE.
- `prefers-reduced-motion` removes the only transition animation.
- The lowest normal-text palette contrast measured 4.54:1; primary and
  semantic colours are materially higher.
- DOM checks at 1440, 768, and 375 px found no horizontal overflow.

## Security review

- Authentication boundaries and signed-session behaviour are unchanged.
- CSP remains fail-closed and now explicitly permits only same-origin images
  and scripts: `default-src 'none'`, `img-src 'self'`, `script-src 'self'`.
- No inline event handlers, dynamic HTML injection, `eval`, client secret, or
  third-party script/runtime request was introduced.
- The public static files are generated visual assets only and contain no user
  data. Authenticated HTML remains `no-store`; static assets are immutable.
- Existing secure headers remain covered by the web test suite.

## Performance and page weight

The prior authenticated HTML measured 17,705 bytes. The final initial-load
payload is 136,666 bytes: 21,039 bytes HTML, 114,086 bytes Earthrise WebP, and
1,541 bytes JavaScript. This is a 118,961-byte increase, almost entirely the
required photographic identity. The image is under the 150 KB test ceiling,
preloaded above the fold, dimensioned to prevent layout shift, and served with
one-year immutable caching. No framework or dependency was added.

Asset provenance and the generation prompt summary are recorded in
`src/foundry/static/README.md`. The asset was generated with OpenAI's built-in
image generator specifically for this RFC and then encoded locally as WebP;
there is no third-party licensing or runtime dependency.

## Verification

- Python compilation: passed.
- Focused presentation/web tests: 34 passed.
- Full suite: 275 passed in 5.58 seconds.
- Warning: one existing Starlette `httpx` compatibility deprecation warning.
- `git diff --check`: passed.

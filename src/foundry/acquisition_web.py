"""The deliberately small authenticated RFC-011 confirmation surface.

This is separate from Mission Control: acquisition proposals are staging
evidence, never mission telemetry, and are only exposed to the authorised
household through an explicit inbox route.
"""

from __future__ import annotations

import html
import json
import os
from pathlib import Path
from urllib.parse import parse_qs, quote

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from foundry import webauth
from foundry.core.acquisition import (
    AcquisitionError, AssetRegistry, ConfirmationGate, EnvelopeProjection, EvidenceUnavailable,
    EvidenceVault, IdentityIndex, ProposalInbox, ProvenanceService, TelemetryStreamRegistry,
    redact_credentials,
)
from foundry.finance.acquisition import FINANCE_MANUAL_DRAFT_CONTRACT
from foundry.finance.capture_targets import finance_asset_registry
from foundry.mission_control import _as_of, _footer, _render


router = APIRouter()
_PURPOSE = "rfc011-confirmation"


def _email(request: Request) -> str | None:
    cfg = webauth.load_config()
    email = webauth.session_email(request.cookies.get(webauth.SESSION_COOKIE), cfg)
    return email if email and email == cfg.allowed_email else None


def _console(request: Request):
    return request.app.state.console_factory()


def _household_id(console) -> str | None:
    households = [party for party in console.entities.parties.values()
                  if party.party_type == "household" and party.status == "active"]
    return households[-1].id if households else None


def _proposal_recorded_at(log, proposal_id: str) -> float | None:
    for event in log.events():
        if event["kind"] == "core.observation_proposal.declared" and event["payload"].get("id") == proposal_id:
            return event["ts"]
    return None


def _vault_root() -> Path:
    configured = os.environ.get("FOUNDRY_EVIDENCE_VAULT_PATH")
    if configured:
        return Path(configured)
    return Path(os.environ.get("FOUNDRY_DATA_PATH", "foundry_data/events.jsonl")).with_suffix(".vault")


def _vault(email: str) -> EvidenceVault:
    return EvidenceVault(_vault_root(), authorized=lambda actor: actor == email)


def _asset_registry(console) -> AssetRegistry:
    """Use the RFC-015 Finance resolver; never admit a made-up subject."""
    return finance_asset_registry(console.log)


def _scoped_proposal(request: Request, proposal_id: str):
    email = _email(request)
    if email is None:
        return None, None, None, RedirectResponse("/login", status_code=303)
    console = _console(request)
    proposal = ProposalInbox(console.log).proposals.get(proposal_id)
    if proposal is None or proposal.household_id != _household_id(console):
        return None, None, None, HTMLResponse("Not found", status_code=404)
    envelope = EnvelopeProjection(console.log).envelopes.get(proposal.envelope_id)
    if envelope is None:
        return None, None, None, HTMLResponse("Not found", status_code=404)
    return email, console, (proposal, envelope), None


def _timestamp(value: float | None) -> str:
    if value is None:
        return "—"
    import time
    try:
        return time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(value))
    except (OverflowError, OSError, TypeError, ValueError):
        return "Invalid timestamp"


def _capture_label(observation: dict) -> tuple[str, str]:
    """Keep the confirmation decision legible without hiding its audit trail."""
    kind = observation.get("kind")
    if kind == "units":
        return "Investment activity", "Units held after this activity"
    if kind == "price":
        return "Investment value update", "Price per unit"
    if kind == "balance":
        return "Balance update", "Balance reported"
    return "Captured information", "Reported value"


def _page(console, items: list[str]) -> HTMLResponse:
    """The confirmation gate is part of Operations, not a developer page."""
    body = "".join(items) or "<p>No pending acquisition proposals.</p>"
    operations_body = f"""<style>
  .acq-hero {{ padding: 126px 0 44px; border-bottom: 1px solid var(--line); margin-bottom: 42px; }}
  .acq-hero h1 {{ font-size: clamp(38px,5vw,58px); font-weight: 540; letter-spacing: -.04em; margin: 10px 0; }}
  .acq-hero p {{ color: var(--muted); font-size: 15px; }}
  .acq-eyebrow, .acq-panel h2 {{ font-size: 9px; font-weight: 650; letter-spacing: .22em; color: var(--faint); }}
  .acq-panel {{ border-top: 1px solid var(--line); padding: 26px 0; }}
  .acq-panel > article {{ padding: 24px 0; border-bottom: 1px solid var(--line); }}
  .acq-panel article h2 {{ color: var(--text); font-size: 17px; letter-spacing: normal; margin-bottom: 18px; }}
  .acq-panel dl {{ display:grid; grid-template-columns:minmax(150px, .42fr) 1fr; gap:9px 20px; color:var(--text); font-size:13px; }}
  .acq-panel dt {{ color: var(--faint); }} .acq-panel dd {{ min-width: 0; overflow-wrap:anywhere; }}
  .acq-panel code {{ overflow-wrap:anywhere; color:var(--muted); }} .acq-panel pre {{ margin-top: 20px; }}
  .acq-panel button {{ margin:20px 10px 0 0; padding:10px 13px; border:1px solid var(--line-strong); background:transparent; color:var(--text); cursor:pointer; font-size:10px; font-weight:650; letter-spacing:.14em; }}
  .acq-panel .warn {{ color: var(--amber); font-size: 13px; margin-top: 14px; }}
  .acq-panel a {{ color: var(--blue); text-decoration: underline; text-underline-offset: 3px; }}
  .acq-panel details {{ margin-top:20px; border-top:1px solid var(--line); }}
  .acq-panel summary {{ cursor:pointer; padding-top:16px; color:var(--muted); font-size:10px; font-weight:650; letter-spacing:.14em; }}
  .acq-panel summary::after {{ content:"+"; float:right; font-size:16px; }}
  .acq-panel details[open] summary::after {{ content:"−"; }}
  @media (max-width:620px) {{ .acq-hero {{ padding-top:94px; }} .acq-panel dl {{ grid-template-columns:1fr; gap:4px; }} .acq-panel dd {{ margin-bottom:10px; }} }}
</style><section class="acq-hero"><div class="acq-eyebrow">OPERATIONS · REVIEW</div><h1>Review captured information.</h1><p>Nothing changes in your plan until you confirm it here.</p></section>
<section class="acq-panel"><h2>ACQUISITION QUEUE <span class="sr-only">ACQUISITION INBOX</span></h2>{body}</section>"""
    return _render("Review captures", operations_body + _footer(console),
                   _as_of(console), "/operations")


@router.get("/acquisition/inbox", response_class=HTMLResponse)
def inbox(request: Request):
    email = _email(request)
    if email is None:
        return RedirectResponse("/login", status_code=303)
    console = _console(request)
    household_id = _household_id(console)
    if household_id is None:
        return _page(console, [])
    proposals = ProposalInbox(console.log)
    envelopes = EnvelopeProjection(console.log)
    streams = TelemetryStreamRegistry(console.log)
    token = webauth.csrf_token(email, webauth.load_config(), _PURPOSE)
    cards = []
    for proposal in proposals.proposals.values():
        if (proposal.state != "pending" or proposal.household_id != household_id
                or not streams.is_active(proposal.stream_id)):
            continue
        envelope = envelopes.envelopes.get(proposal.envelope_id)
        observation = proposal.observations[0] if proposal.observations else {}
        capture_label, value_label = _capture_label(observation)
        resolutions = ", ".join(html.escape(str(item.get("outcome", "unknown"))) for item in proposal.resolutions) or "none"
        warnings = []
        if any(item.get("outcome") in {"ambiguous", "unresolved"} for item in proposal.resolutions):
            warnings.append("Identity requires explicit human review.")
        if any(item.get("duplicate_of") for item in proposal.resolutions):
            warnings.append("Semantic duplicate: reject or reconcile.")
        warning_html = "".join(f'<p class="warn">{html.escape(value)}</p>' for value in warnings)
        events = "<br>".join("<code>" + html.escape(item["kind"]) + "</code>" for item in proposal.draft_events)
        proposal_id = quote(proposal.id, safe="")
        csrf = html.escape(token, quote=True)
        cards.append(f"""<article><h2>{html.escape(capture_label)}</h2>
<dl><dt>{html.escape(value_label)}</dt><dd>{html.escape(str(observation.get("value", "—")))}</dd>
<dt>Effective date</dt><dd>{_timestamp(observation.get("valid_at"))}</dd>
<dt>Evidence</dt><dd><a href="/acquisition/proposals/{proposal_id}/evidence">Review captured evidence</a></dd></dl>{warning_html}
<form method="post" action="/acquisition/proposals/{proposal_id}/confirm"><input type="hidden" name="csrf" value="{csrf}"><button type="submit">Confirm</button></form>
<form method="post" action="/acquisition/proposals/{proposal_id}/reject"><input type="hidden" name="csrf" value="{csrf}"><button type="submit">Reject</button></form>
<details><summary>TECHNICAL DETAILS</summary><dl><dt>Capture identifier</dt><dd><code>{html.escape(proposal.id)}</code></dd>
<dt>Evidence summary</dt><dd><code>{html.escape(proposal.evidence_id)}</code></dd>
<dt>Source</dt><dd>{html.escape(envelope.source_identity if envelope else "missing envelope")}</dd>
<dt>Proposed identity</dt><dd>{resolutions}</dd>
<dt>Target</dt><dd>{html.escape(str(observation.get("subject_id", "—")))}</dd>
<dt>Observed at</dt><dd>{_timestamp(observation.get("observed_at"))}</dd>
<dt>Received at</dt><dd>{_timestamp(envelope.received_at if envelope else None)}</dd>
<dt>Recorded at</dt><dd>{_timestamp(_proposal_recorded_at(console.log, proposal.id))}</dd>
<dt>Evidence grade</dt><dd>{html.escape(proposal.evidence_grade)}</dd>
<dt>Interpreter</dt><dd>{html.escape(proposal.interpreter_id)} {html.escape(proposal.interpreter_version)}</dd>
<dt>Canonical events on confirmation</dt><dd>{events}</dd></dl></details></article>""")
    return _page(console, cards)


@router.get("/acquisition/proposals/{proposal_id}/evidence", response_class=HTMLResponse)
def evidence_preview(request: Request, proposal_id: str):
    email, console, scoped, error = _scoped_proposal(request, proposal_id)
    if error is not None:
        return error
    proposal, envelope = scoped
    try:
        raw = _vault(email).get(envelope.payload_hash, email)
        if envelope.payload_media_type == "application/json":
            preview = json.dumps(redact_credentials(json.loads(raw.decode("utf-8"))),
                                 sort_keys=True, indent=2, ensure_ascii=False)
        elif envelope.payload_media_type == "text/plain":
            preview = str(redact_credentials(raw.decode("utf-8")))
        else:
            raise EvidenceUnavailable("evidence preview media type is unavailable")
    except (EvidenceUnavailable, UnicodeDecodeError, json.JSONDecodeError):
        return HTMLResponse("Evidence unavailable", status_code=404)
    return _page(console, [f"<article><h2>Evidence review</h2><dl><dt>Evidence identifier</dt><dd><code>{html.escape(envelope.payload_hash)}</code></dd>"
                  f"<dt>Source</dt><dd>{html.escape(envelope.source_identity)}</dd></dl>"
                  f"<pre>{html.escape(preview)}</pre><p><a href=\"/acquisition/inbox\">Back to inbox</a></p></article>"])


@router.get("/acquisition/proposals/{proposal_id}/provenance", response_class=HTMLResponse)
def provenance(request: Request, proposal_id: str):
    _, console, scoped, error = _scoped_proposal(request, proposal_id)
    if error is not None:
        return error
    proposal, _ = scoped
    canonical = next((event for event in console.log.events()
                      if event["payload"].get("provenance", {}).get("proposal_id") == proposal.id), None)
    if canonical is None:
        return HTMLResponse("Provenance unavailable", status_code=404)
    try:
        chain = ProvenanceService(console.log).explain(canonical["id"])
    except AcquisitionError:
        return HTMLResponse("Provenance unavailable", status_code=404)
    rendered = html.escape(json.dumps(chain, sort_keys=True, indent=2))
    return _page(console, [f"<article><h2>Confirmation provenance</h2><pre>{rendered}</pre>"
                  f"<p><a href=\"/acquisition/inbox\">Back to inbox</a></p></article>"])


def _gate(request: Request, proposal_id: str, csrf: str | None):
    email = _email(request)
    if email is None:
        return None, RedirectResponse("/login", status_code=303)
    cfg = webauth.load_config()
    if not webauth.verify_csrf(csrf, email, cfg, _PURPOSE):
        return None, HTMLResponse("Forbidden", status_code=403)
    console = _console(request)
    proposals = ProposalInbox(console.log)
    proposal = proposals.proposals.get(proposal_id)
    if proposal is None or proposal.household_id != _household_id(console):
        return None, HTMLResponse("Not found", status_code=404)
    registry = _asset_registry(console)
    for observation in proposal.observations:
        subject_id = observation.get("subject_id")
        registration = registry.registrations.get(subject_id)
        if (not isinstance(subject_id, str) or not registry.entity_exists(subject_id)
                or registration is None or registration.household_id != proposal.household_id):
            return None, HTMLResponse("Not found", status_code=404)
    return ConfirmationGate(console.log, proposals, TelemetryStreamRegistry(console.log),
                            IdentityIndex(console.log), registry,
                            FINANCE_MANUAL_DRAFT_CONTRACT), None


async def _form_csrf(request: Request) -> str | None:
    """Accept the signed CSRF credential from the POST body only.

    Query strings leak into browser history, proxies and access logs.  The
    token is intentionally unavailable to URL parsing, including forged query
    parameters.
    """
    content_type = request.headers.get("content-type", "").split(";", 1)[0]
    if content_type != "application/x-www-form-urlencoded":
        return None
    try:
        fields = parse_qs((await request.body()).decode("utf-8"), strict_parsing=True)
    except (UnicodeDecodeError, ValueError):
        return None
    values = fields.get("csrf")
    return values[0] if set(fields) == {"csrf"} and values and len(values) == 1 else None


@router.post("/acquisition/proposals/{proposal_id}/confirm")
async def confirm(request: Request, proposal_id: str):
    csrf = await _form_csrf(request)
    gate, error = _gate(request, proposal_id, csrf)
    if error is not None:
        return error
    try:
        gate.confirm(proposal_id, actor=_email(request) or "")
    except AcquisitionError as exc:
        return HTMLResponse("Confirmation refused: " + html.escape(str(exc)), status_code=409)
    return RedirectResponse(f"/acquisition/proposals/{quote(proposal_id, safe='')}/provenance", status_code=303)


@router.post("/acquisition/proposals/{proposal_id}/reject")
async def reject(request: Request, proposal_id: str):
    csrf = await _form_csrf(request)
    gate, error = _gate(request, proposal_id, csrf)
    if error is not None:
        return error
    try:
        gate.reject(proposal_id, actor=_email(request) or "", reason="rejected from authenticated inbox")
    except AcquisitionError as exc:
        return HTMLResponse("Rejection refused: " + html.escape(str(exc)), status_code=409)
    return RedirectResponse("/acquisition/inbox", status_code=303)

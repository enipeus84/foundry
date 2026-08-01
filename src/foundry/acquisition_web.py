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
    return time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(value))


def _page(items: list[str]) -> HTMLResponse:
    body = "".join(items) or "<p>No pending acquisition proposals.</p>"
    return HTMLResponse(f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Foundry acquisition inbox</title>
<style>body{{font-family:system-ui;background:#0b0e12;color:#e6edf3;max-width:62rem;margin:3rem auto;padding:0 1rem}}
article{{border:1px solid #2b3440;border-radius:8px;padding:1rem;margin:1rem 0}}dl{{display:grid;grid-template-columns:12rem 1fr;gap:.35rem}}dt{{color:#9aa7b5}}code{{overflow-wrap:anywhere}}button{{margin-right:.5rem;padding:.5rem .8rem}}.warn{{color:#ffc66d}}</style>
</head><body><h1>ACQUISITION INBOX</h1><p>Evidence is inert until confirmation.</p>{body}</body></html>""")


@router.get("/acquisition/inbox", response_class=HTMLResponse)
def inbox(request: Request):
    email = _email(request)
    if email is None:
        return RedirectResponse("/login", status_code=303)
    console = _console(request)
    household_id = _household_id(console)
    if household_id is None:
        return _page([])
    proposals = ProposalInbox(console.log)
    envelopes = EnvelopeProjection(console.log)
    token = webauth.csrf_token(email, webauth.load_config(), _PURPOSE)
    cards = []
    for proposal in proposals.proposals.values():
        if proposal.state != "pending" or proposal.household_id != household_id:
            continue
        envelope = envelopes.envelopes.get(proposal.envelope_id)
        observation = proposal.observations[0] if proposal.observations else {}
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
        cards.append(f"""<article><h2>Proposal {html.escape(proposal.id)}</h2>
<dl><dt>Evidence summary</dt><dd><code>{html.escape(proposal.evidence_id)}</code></dd>
<dt>Source</dt><dd>{html.escape(envelope.source_identity if envelope else "missing envelope")}</dd>
<dt>Proposed identity</dt><dd>{resolutions}</dd>
<dt>Target</dt><dd>{html.escape(str(observation.get("subject_id", "—")))}</dd>
<dt>Proposed units/value</dt><dd>{html.escape(str(observation.get("value", "—")))}</dd>
<dt>valid_at</dt><dd>{_timestamp(observation.get("valid_at"))}</dd>
<dt>observed_at</dt><dd>{_timestamp(observation.get("observed_at"))}</dd>
<dt>received_at</dt><dd>{_timestamp(envelope.received_at if envelope else None)}</dd>
<dt>recorded_at</dt><dd>{_timestamp(_proposal_recorded_at(console.log, proposal.id))}</dd>
<dt>Evidence grade</dt><dd>{html.escape(proposal.evidence_grade)}</dd>
<dt>Interpreter</dt><dd>{html.escape(proposal.interpreter_id)} {html.escape(proposal.interpreter_version)}</dd>
<dt>Canonical events on confirmation</dt><dd>{events}</dd>
<dt>Evidence</dt><dd><a href="/acquisition/proposals/{proposal_id}/evidence">Review captured evidence</a></dd></dl>{warning_html}
<form method="post" action="/acquisition/proposals/{proposal_id}/confirm"><input type="hidden" name="csrf" value="{csrf}"><button type="submit">Confirm</button></form>
<form method="post" action="/acquisition/proposals/{proposal_id}/reject"><input type="hidden" name="csrf" value="{csrf}"><button type="submit">Reject</button></form></article>""")
    return _page(cards)


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
    return _page([f"<article><h2>Evidence review</h2><dl><dt>Evidence identifier</dt><dd><code>{html.escape(envelope.payload_hash)}</code></dd>"
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
    return _page([f"<article><h2>Confirmation provenance</h2><pre>{rendered}</pre>"
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
    registry = AssetRegistry(console.log, entity_exists=lambda _entity_id: True)
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

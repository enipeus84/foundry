"""Authenticated RFC-012 Operations Console renderer and capture adapter."""

from __future__ import annotations

import html
import json
import os
import time
from pathlib import Path
from urllib.parse import parse_qs

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from foundry import webauth
from foundry.core.acquisition import (
    AssetRegistry, CanonicalObservationProjection, EnvelopeProjection,
    EvidenceVault, IdentityIndex, ManualAcquisitionProvider, ProposalInbox,
    ResolutionService, TelemetryStreamRegistry, ValuationLenses,
    AcquisitionError,
)
from foundry.finance.acquisition import FinanceManualInterpreter
from foundry.operations_console import OperationsConsoleModel

router = APIRouter()
_PURPOSE = "rfc012-capture"


def _email(request: Request) -> str | None:
    cfg = webauth.load_config()
    email = webauth.session_email(request.cookies.get(webauth.SESSION_COOKIE), cfg)
    return email if email and email == cfg.allowed_email else None


def _console(request: Request):
    return request.app.state.console_factory()


def _household(console) -> str | None:
    households = [p for p in console.entities.parties.values()
                  if p.party_type == "household" and p.status == "active"]
    return households[-1].id if households else None


def _model(console) -> OperationsConsoleModel:
    envelopes = EnvelopeProjection(console.log)
    streams = TelemetryStreamRegistry(console.log)
    inbox = ProposalInbox(console.log)
    registry = AssetRegistry(console.log, entity_exists=lambda _entity: True)
    observations = CanonicalObservationProjection(console.log, envelopes)
    return OperationsConsoleModel(registry, streams, inbox,
                                  ValuationLenses(registry, streams, observations), envelopes)


def _page(body: str) -> HTMLResponse:
    return HTMLResponse("""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Foundry operations</title>
<style>body{font-family:system-ui;background:#0b0e12;color:#e6edf3;max-width:62rem;margin:3rem auto;padding:0 1rem}
article{border:1px solid #2b3440;border-radius:8px;padding:1rem;margin:1rem 0}a{color:#8bc8ff}
label{display:block;margin:.6rem 0}input,textarea,select{display:block;width:100%;max-width:40rem;padding:.45rem;background:#111820;color:#e6edf3;border:1px solid #40505f}
button{padding:.55rem .9rem}.muted{color:#9aa7b5}.warn{color:#ffc66d}</style></head><body>
<nav><a href="/operations">OPERATIONS</a> · <a href="/acquisition/inbox">ACQUISITION INBOX</a></nav>""" + body + "</body></html>")


@router.get("/operations", response_class=HTMLResponse)
def operations(request: Request):
    email = _email(request)
    if email is None:
        return RedirectResponse("/login", status_code=303)
    console = _console(request)
    household = _household(console)
    if household is None:
        return _page("<h1>OPERATIONS CONSOLE</h1><p>No active household.</p>")
    as_of = max((event["ts"] for event in console.log.events()), default=0.0)
    view = _model(console).view(household, as_of=as_of, known_at=as_of)
    cards = []
    for item in view.items:
        action = (f'<a href="/acquisition/inbox">Review proposal</a>'
                  if item.action in {"review", "resolve"}
                  else '<a href="/operations/capture">Capture missing fact</a>')
        cards.append(f"<article><h2>{html.escape(item.kind)}</h2>"
                     f"<p>{html.escape(item.summary)}</p><p class=\"muted\">"
                     f"Subject: <code>{html.escape(item.subject_id)}</code></p><p>{action}</p></article>")
    body = (f"<h1>OPERATIONS CONSOLE</h1><p>{html.escape(view.summary_line())}</p>"
            + ("".join(cards) or "<p>Nothing needs attention.</p>")
            + f'<p><a href="/operations/capture">Capture a manual fact</a></p>')
    return _page(body)


@router.get("/operations/capture", response_class=HTMLResponse)
def capture_form(request: Request):
    email = _email(request)
    if email is None:
        return RedirectResponse("/login", status_code=303)
    console = _console(request)
    streams = TelemetryStreamRegistry(console.log)
    options = "".join(f'<option value="{html.escape(s.id, quote=True)}">{html.escape(s.id)}</option>'
                      for s in streams.streams.values() if s.channel == "manual")
    token = html.escape(webauth.csrf_token(email, webauth.load_config(), _PURPOSE), quote=True)
    return _page(f'''<h1>CAPTURE MANUAL FACT</h1><form method="post" action="/operations/capture">
<input type="hidden" name="csrf" value="{token}"><label>Stream<select name="stream_id">{options}</select></label>
<label>Subject ID<input name="subject_id" required></label><label>Observation kind<input name="kind" required></label>
<label>Value<input name="value" type="number" step="any" required></label>
<label>Valid at (Unix timestamp)<input name="valid_at" type="number" step="any" required></label>
<label>External reference<input name="external_ref"></label>
<label>Canonical event kind<input name="event_kind" value="finance.position.updated" required></label>
<label>Canonical event payload (JSON)<textarea name="event_payload" required>{{"entity_id":""}}</textarea></label>
<button type="submit">Submit capture</button></form>''')


async def _body(request: Request) -> dict[str, str] | None:
    if request.headers.get("content-type", "").split(";", 1)[0] != "application/x-www-form-urlencoded":
        return None
    try:
        fields = parse_qs((await request.body()).decode("utf-8"), strict_parsing=True)
    except (UnicodeDecodeError, ValueError):
        return None
    return {key: values[0] for key, values in fields.items() if len(values) == 1}


@router.post("/operations/capture")
async def capture(request: Request):
    email = _email(request)
    if email is None:
        return RedirectResponse("/login", status_code=303)
    fields = await _body(request)
    cfg = webauth.load_config()
    if not fields or set(fields) - {"csrf", "stream_id", "subject_id", "kind", "value", "valid_at", "external_ref", "event_kind", "event_payload"} or not webauth.verify_csrf(fields.get("csrf"), email, cfg, _PURPOSE):
        return HTMLResponse("Forbidden", status_code=403)
    try:
        payload = json.loads(fields["event_payload"])
        if not isinstance(payload, dict):
            raise ValueError
        payload.setdefault("entity_id", fields["subject_id"])
        fact = {"kind": fields["kind"], "subject_id": fields["subject_id"],
                "valid_at": float(fields["valid_at"]), "value": float(fields["value"]),
                "canonical_event": {"kind": fields["event_kind"], "payload": payload}}
        console = _console(request)
        streams = TelemetryStreamRegistry(console.log)
        stream = streams.streams.get(fields["stream_id"])
        if stream is None or stream.household_id != _household(console) or stream.channel != "manual":
            return HTMLResponse("Not found", status_code=404)
        vault_root = os.environ.get("FOUNDRY_EVIDENCE_VAULT_PATH")
        if not vault_root:
            vault_root = str(Path(os.environ.get("FOUNDRY_DATA_PATH", "foundry_data/events.jsonl")).with_suffix(".vault"))
        vault = EvidenceVault(vault_root, authorized=lambda actor: actor == email)
        provider = ManualAcquisitionProvider(console.log, streams, vault, [stream.id])
        envelope = provider.capture(stream.id, {"observations": [fact]}, received_at=time.time(), actor=email,
                                    source_identity=stream.source_identity, external_ref=fields.get("external_ref") or None)
        inbox = ProposalInbox(console.log)
        interpreter = FinanceManualInterpreter(vault, EnvelopeProjection(console.log), streams,
                                               ResolutionService(IdentityIndex(console.log), AssetRegistry(console.log, entity_exists=lambda _e: True), inbox))
        interpreter.interpret(envelope.id, email)
    except (KeyError, TypeError, ValueError, AcquisitionError, json.JSONDecodeError) as exc:
        return HTMLResponse("Capture refused: " + html.escape(str(exc)), status_code=400)
    return RedirectResponse("/acquisition/inbox", status_code=303)

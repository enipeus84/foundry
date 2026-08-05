"""Authenticated RFC-012 Operations Console renderer and capture adapter."""

from __future__ import annotations

import html
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
from foundry.capture_contracts import CaptureContract, CaptureContractRegistry, capture_contract_registry
from foundry.operations_console import OperationsConsoleModel

router = APIRouter()
_PURPOSE = "rfc013-capture"


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


def _contracts(request: Request) -> CaptureContractRegistry:
    """The composition root may inject another registry; renderers never name types."""
    registry = getattr(request.app.state, "capture_contract_registry", None)
    return registry if isinstance(registry, CaptureContractRegistry) else capture_contract_registry()


def _evidence_reference_policy(contract: CaptureContract) -> str:
    """Describe a reference honestly; it is not a verified artefact upload."""
    policy = contract.evidence_policy.value
    if policy == "REQUIRED":
        return "An evidence reference is required; Foundry records the reference, not the external artefact."
    if policy == "RECOMMENDED":
        return "An evidence reference is recommended; Foundry records the reference, not the external artefact."
    if policy == "OPTIONAL":
        return "An evidence reference is optional; Foundry records it if supplied, not the external artefact."
    return "No evidence reference is requested."


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
    registry = _contracts(request)
    contract_id = request.query_params.get("contract")
    if not contract_id:
        cards = "".join(
            f'<article><h2>{html.escape(contract.display_name)}</h2><p>{html.escape(contract.description)}</p>'
            f'<p class="muted">Version {html.escape(contract.version)} · Evidence: '
            f'{html.escape(contract.evidence_policy.value)}</p>'
            f'<p class="muted">{html.escape(_evidence_reference_policy(contract))}</p>'
            f'<p><a href="/operations/capture?contract={html.escape(contract.identifier, quote=True)}">'
            f'Record this</a></p></article>'
            for contract in registry.discover())
        return _page("<h1>WHAT DO YOU WANT TO RECORD?</h1>" + (cards or "<p>Capture is not configured.</p>"))
    contract = registry.get(contract_id)
    if contract is None:
        return HTMLResponse("Not found", status_code=404)
    console = _console(request)
    household = _household(console)
    streams = TelemetryStreamRegistry(console.log)
    eligible = [stream for stream in streams.streams.values()
                if stream.channel == "manual" and stream.household_id == household
                and contract.accepts_stream(stream.property)]
    options = "".join(f'<option value="{html.escape(stream.id, quote=True)}">'
                      f'{html.escape(stream.id)} · {html.escape(stream.subject_id)}</option>'
                      for stream in eligible)
    token = html.escape(webauth.csrf_token(email, webauth.load_config(), _PURPOSE), quote=True)
    rendered_fields = []
    for field in contract.schema:
        required_attribute = " required" if field.required else ""
        step_attribute = ' step="any"' if field.input_type == "number" else ""
        rendered_fields.append(
            f'<label>{html.escape(field.label)}<input name="{html.escape(field.name, quote=True)}"'
            f' type="{html.escape(field.input_type, quote=True)}"{required_attribute}{step_attribute}></label>'
            f'<span class="muted">{html.escape(field.help_text)}</span>')
    fields = "".join(rendered_fields)
    if not eligible:
        return _page(f"<h1>{html.escape(contract.display_name)}</h1><p>No compatible manual telemetry stream is registered.</p>"
                     '<p><a href="/operations/capture">Choose another capture type</a></p>')
    return _page(f'''<h1>{html.escape(contract.display_name)}</h1><p>{html.escape(contract.description)}</p>
<p class="muted">Version {html.escape(contract.version)} · Evidence policy: {html.escape(contract.evidence_policy.value)}</p>
<p class="muted">{html.escape(_evidence_reference_policy(contract))}</p>
<form method="post" action="/operations/capture"><input type="hidden" name="csrf" value="{token}">
<input type="hidden" name="contract_id" value="{html.escape(contract.identifier, quote=True)}">
<label>Target stream<select name="stream_id">{options}</select></label>{fields}
<button type="submit">Create review draft</button></form>''')


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
    if not fields or not webauth.verify_csrf(fields.get("csrf"), email, cfg, _PURPOSE):
        return HTMLResponse("Forbidden", status_code=403)
    try:
        contract = _contracts(request).get(fields.get("contract_id", ""))
        if contract is None:
            return HTMLResponse("Not found", status_code=404)
        system_fields = {"csrf", "contract_id", "stream_id"}
        contract_fields = {field.name for field in contract.schema}
        required_fields = {field.name for field in contract.schema if field.required}
        if (set(fields) - (system_fields | contract_fields)
                or not system_fields <= set(fields) or not required_fields <= set(fields)):
            return HTMLResponse("Forbidden", status_code=403)
        console = _console(request)
        streams = TelemetryStreamRegistry(console.log)
        stream = streams.streams.get(fields["stream_id"])
        if (stream is None or stream.household_id != _household(console) or stream.channel != "manual"
                or not contract.accepts_stream(stream.property)):
            return HTMLResponse("Not found", status_code=404)
        values = {name: fields.get(name, "") for name in contract_fields}
        normalised = contract.normalise(values)
        capture_id = contract.capture_id(normalised, stream_id=stream.id, subject_id=stream.subject_id)
        fact = contract.canonical_mapper.map(normalised, subject_id=stream.subject_id,
                                              capture_id=capture_id)
        vault_root = os.environ.get("FOUNDRY_EVIDENCE_VAULT_PATH")
        if not vault_root:
            vault_root = str(Path(os.environ.get("FOUNDRY_DATA_PATH", "foundry_data/events.jsonl")).with_suffix(".vault"))
        vault = EvidenceVault(vault_root, authorized=lambda actor: actor == email)
        provider = ManualAcquisitionProvider(console.log, streams, vault, [stream.id])
        envelope = provider.capture(stream.id, {
            "capture_contract": {"identifier": contract.identifier, "version": contract.version},
            "review_summary": contract.review_summary(normalised, subject_id=stream.subject_id),
            "observations": [fact],
        }, received_at=time.time(), actor=email, source_identity=stream.source_identity,
           external_ref=normalised.get("evidence_reference") or None)
        inbox = ProposalInbox(console.log)
        interpreter = FinanceManualInterpreter(vault, EnvelopeProjection(console.log), streams,
                                               ResolutionService(IdentityIndex(console.log), AssetRegistry(console.log, entity_exists=lambda _e: True), inbox))
        interpreter.interpret(envelope.id, email)
    except (KeyError, TypeError, ValueError, AcquisitionError) as exc:
        return HTMLResponse("Capture refused: " + html.escape(str(exc)), status_code=400)
    return RedirectResponse("/acquisition/inbox", status_code=303)

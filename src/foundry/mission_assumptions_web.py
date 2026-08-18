"""Authenticated shared editor shell for the four mission schemas."""

from __future__ import annotations

import html
import json
from hashlib import sha256

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from foundry import webauth
from foundry.application.mission_assumptions import MissionAssumptionError, MissionAssumptionService
from foundry.mission_control import _as_of, _console, _footer, _render

router = APIRouter()
PURPOSE = "mission-assumption-onboarding"


def _email(request: Request):
    config = webauth.load_config()
    email = webauth.session_email(request.cookies.get(webauth.SESSION_COOKIE), config)
    return email if email and email == config.allowed_email else None


def _household(console):
    return next((p.id for p in console.entities.parties.values()
                 if p.party_type == "household" and p.status == "active"), None)


def _form_values(form, fields):
    values = {}
    for field in fields:
        raw = form.get(field)
        if raw is None or raw == "":
            continue
        try:
            values[field] = float(raw)
        except (TypeError, ValueError):
            values[field] = raw
    return values


@router.get("/missions/{mission_id}/assumptions", response_class=HTMLResponse)
def assumptions_editor(request: Request, mission_id: str):
    email = _email(request)
    if email is None:
        return RedirectResponse("/login", status_code=303)
    console = _console(request)
    household_id = _household(console)
    try:
        schema = MissionAssumptionService(console.log).schema(mission_id, household_id or "")
    except MissionAssumptionError:
        return HTMLResponse("Mission not found", status_code=404)
    token = html.escape(webauth.csrf_token(email, webauth.load_config(), PURPOSE), quote=True)
    fields = "".join(
        f'<label>{html.escape(field.replace("_", " ").title())}'
        f'<input name="{html.escape(field, quote=True)}" type="number" step="any" required></label>'
        for field in schema.fields)
    body = f'''<section class="mt-hero"><div class="mt-k">ASSUMPTION SETUP</div>
<h1>{html.escape(schema.mission)}</h1>
<p>These are explicit modelling inputs for this mission. Governed policy thresholds are not editable here.</p>
<p>Household context: <code>{html.escape(household_id or "")}</code></p>
<form class="mt-form" method="post" action="/missions/assumptions/review">
<input type="hidden" name="csrf" value="{token}"><input type="hidden" name="mission_id" value="{html.escape(mission_id, quote=True)}">
{fields}<button type="submit">REVIEW ASSUMPTIONS →</button></form></section>'''
    return _render("Assumption Setup", body + _footer(console), _as_of(console), "/missions")


@router.post("/missions/assumptions/review", response_class=HTMLResponse)
async def assumptions_review(request: Request):
    email = _email(request)
    if email is None:
        return RedirectResponse("/login", status_code=303)
    form = await request.form()
    mission_id = str(form.get("mission_id", ""))
    console = _console(request)
    household_id = _household(console)
    try:
        service = MissionAssumptionService(console.log)
        schema = service.schema(mission_id, household_id or "")
        if not webauth.verify_csrf(form.get("csrf"), email, webauth.load_config(), PURPOSE):
            raise MissionAssumptionError("review token invalid")
        values = _form_values(form, schema.fields)
        service._payload(mission_id, household_id or "", values)
    except MissionAssumptionError as exc:
        return HTMLResponse(f"Assumptions refused: {html.escape(str(exc))}", status_code=400)
    digest = sha256(json.dumps(values, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    token = html.escape(webauth.csrf_token(email, webauth.load_config(), PURPOSE), quote=True)
    hidden = "".join(f'<input type="hidden" name="{html.escape(k, quote=True)}" value="{html.escape(str(v), quote=True)}">' for k, v in values.items())
    rows = "".join(f"<dt>{html.escape(k.replace('_', ' ').title())}</dt><dd>{html.escape(str(v))}</dd>" for k, v in values.items())
    body = f'''<section class="mt-hero"><div class="mt-k">REVIEW ASSUMPTION SET</div>
<h1>Make this canonical?</h1><p>Review is informational; approval reloads and validates current mission state before activation.</p>
<dl class="mt-review">{rows}</dl><form method="post" action="/missions/assumptions/declare">
<input type="hidden" name="csrf" value="{token}"><input type="hidden" name="mission_id" value="{html.escape(mission_id, quote=True)}">
<input type="hidden" name="review_digest" value="{digest}">{hidden}<button type="submit">ACTIVATE ASSUMPTION SET →</button></form></section>'''
    return _render("Review Assumption Set", body + _footer(console), _as_of(console), "/missions")


@router.post("/missions/assumptions/declare")
async def assumptions_declare(request: Request):
    email = _email(request)
    if email is None:
        return RedirectResponse("/login", status_code=303)
    form = await request.form()
    console = _console(request)
    household_id = _household(console) or ""
    try:
        service = MissionAssumptionService(console.log)
        schema = service.schema(str(form.get("mission_id", "")), household_id)
        values = _form_values(form, schema.fields)
        digest = sha256(json.dumps(values, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        if form.get("review_digest") != digest or not webauth.verify_csrf(form.get("csrf"), email, webauth.load_config(), PURPOSE):
            raise MissionAssumptionError("review is stale or invalid")
        result = service.declare(mission_id=str(form["mission_id"]), household_id=household_id,
                                 assumptions=values, actor=email)
    except MissionAssumptionError as exc:
        return HTMLResponse(f"Activation refused: {html.escape(str(exc))}", status_code=400)
    return RedirectResponse(f"/missions/{html.escape(result['mission_id'], quote=True)}", status_code=303)

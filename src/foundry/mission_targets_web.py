"""Authenticated RFC-016 Phase 3 Mission Target Management surface.

Review is deliberately informational.  Approval reloads canonical state,
re-derives every authoritative field and refuses if the in-force predecessor
is not the one the operator reviewed.
"""

from __future__ import annotations

from datetime import date, datetime, time as datetime_time, timezone
import html
import time
from urllib.parse import parse_qs, quote

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from foundry import webauth
from foundry.core.mission_targets import (
    MissionTarget,
    MissionTargetError,
    MissionTargetProjection,
    TargetQuantity,
)
from foundry.mission_control import _as_of, _footer, _render


router = APIRouter()
_REVIEW_PURPOSE = "rfc016-target-review"
_DECLARE_PURPOSE = "rfc016-target-declare"
_WITHDRAW_PURPOSE = "rfc016-target-withdraw"


def _email(request: Request) -> str | None:
    cfg = webauth.load_config()
    email = webauth.session_email(
        request.cookies.get(webauth.SESSION_COOKIE), cfg)
    return email if email and email == cfg.allowed_email else None


def _console(request: Request):
    return request.app.state.console_factory()


def _projection(console) -> MissionTargetProjection:
    projection = console.mission_targets
    if not isinstance(projection, MissionTargetProjection):
        raise RuntimeError("Mission Target Management is not composed")
    return projection


def _household_id(console) -> str | None:
    households = [
        party for party in console.entities.parties.values()
        if party.party_type == "household" and party.status == "active"
    ]
    return households[-1].id if households else None


def _horizon_kind(projection: MissionTargetProjection,
                  metric_id: str) -> str | None:
    resolver = projection.metric_resolver
    resolve = getattr(resolver, "horizon_kind", None)
    return resolve(metric_id) if callable(resolve) else None


def _now() -> float:
    return time.time()


def _current_target(projection: MissionTargetProjection,
                    mission_id: str) -> MissionTarget | None:
    return projection.in_force(mission_id, _now())


def _mission_access(console, mission_id: str, household_id: str):
    """Resolve one manageable Mission without disclosing another household."""
    mission = console.entities.missions.get(mission_id)
    if mission is None or mission.status != "active":
        return None
    projection = _projection(console)
    existing = [
        target for target in projection.targets.values()
        if target.mission_id == mission.id
    ]
    if existing and any(
            target.household_id != household_id for target in existing):
        return None
    definition = console.assessments.definition_for_policy(
        mission.assessment_policy_id or "")
    descriptor = projection.metric_resolver.describe(mission.target_metric)
    horizon_kind = _horizon_kind(projection, mission.target_metric)
    if definition is None or descriptor is None or horizon_kind is None:
        return mission, definition, descriptor, horizon_kind, "unavailable"
    if mission.id in projection.conflicts:
        return mission, definition, descriptor, horizon_kind, "conflict"
    return mission, definition, descriptor, horizon_kind, "manageable"


def _page(console, title: str, body: str) -> HTMLResponse:
    return _render(
        title, _styles() + body + _footer(console), _as_of(console), "/missions")


def _refusal(message: str, status_code: int) -> HTMLResponse:
    return HTMLResponse(html.escape(message), status_code=status_code)


async def _body(request: Request) -> dict[str, str] | None:
    content_type = request.headers.get("content-type", "").split(";", 1)[0]
    if content_type != "application/x-www-form-urlencoded":
        return None
    try:
        parsed = parse_qs(
            (await request.body()).decode("utf-8"),
            strict_parsing=True,
            keep_blank_values=True,
        )
    except (UnicodeDecodeError, ValueError):
        return None
    if any(len(values) != 1 for values in parsed.values()):
        return None
    return {key: values[0] for key, values in parsed.items()}


def _expected_declaration_fields(horizon_kind: str, *, approval: bool) -> set[str]:
    fields = {"csrf", "mission_id", "destination_value", "basis"}
    if horizon_kind == "by_date":
        fields.add("horizon_date")
    if approval:
        fields.add("reviewed_in_force")
    return fields


def _horizon_at(value: str) -> float:
    try:
        parsed = date.fromisoformat(value)
        return datetime.combine(
            parsed, datetime_time.min, tzinfo=timezone.utc).timestamp()
    except (OSError, OverflowError, ValueError) as exc:
        raise MissionTargetError("horizon date must be a valid calendar date") from exc


def _operator_inputs(fields: dict[str, str], descriptor, horizon_kind: str):
    try:
        destination = TargetQuantity(
            float(fields["destination_value"]),
            descriptor.unit_or_currency,
            descriptor.dimension,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise MissionTargetError("destination value must be a finite number") from exc
    horizon_at = _horizon_at(fields["horizon_date"]) \
        if horizon_kind == "by_date" else None
    basis = fields.get("basis") or None
    return destination, horizon_at, basis


def _validate_declaration(
    projection: MissionTargetProjection,
    *,
    household_id: str,
    mission,
    descriptor,
    horizon_kind: str,
    destination: TargetQuantity,
    horizon_at: float | None,
    basis: str | None,
    supersedes: str | None,
    effective_from: float,
) -> None:
    projection._validate_declaration(
        household_id,
        mission.id,
        mission.target_metric,
        destination,
        descriptor.destination_direction,
        horizon_kind,
        horizon_at,
        effective_from,
        None,
        basis,
        supersedes,
    )


def _format_destination(target: MissionTarget) -> str:
    value = f"{target.destination.value:,.2f}".rstrip("0").rstrip(".")
    if target.destination.dimension == "currency":
        symbols = {"GBP": "£", "USD": "$", "EUR": "€"}
        return f"{symbols.get(target.destination.unit_or_currency, target.destination.unit_or_currency + ' ')}{value}"
    return f"{value} {target.destination.unit_or_currency}"


def _format_input(destination: TargetQuantity) -> str:
    value = f"{destination.value:,.2f}".rstrip("0").rstrip(".")
    if destination.dimension == "currency":
        symbols = {"GBP": "£", "USD": "$", "EUR": "€"}
        return f"{symbols.get(destination.unit_or_currency, destination.unit_or_currency + ' ')}{value}"
    return f"{value} {destination.unit_or_currency}"


def _styles() -> str:
    return """<style>
  .mt-hero { padding:126px 0 48px; border-bottom:1px solid var(--line); margin-bottom:42px; }
  .mt-hero h1 { font-size:clamp(42px,6vw,68px); font-weight:540; letter-spacing:-.04em; margin:10px 0 14px; }
  .mt-hero p, .mt-empty, .mt-card p, .mt-form p { color:var(--muted); line-height:1.6; }
  .mt-k { font-size:9px; font-weight:650; letter-spacing:.22em; color:var(--faint); text-transform:uppercase; }
  .mt-list { border-top:1px solid var(--line); }
  .mt-card { display:grid; grid-template-columns:minmax(0,1fr) auto; gap:24px; align-items:center; padding:26px 0; border-bottom:1px solid var(--line); }
  .mt-card h2 { font-size:20px; font-weight:550; margin:7px 0; }
  .mt-actions { display:flex; gap:10px; flex-wrap:wrap; justify-content:flex-end; }
  .mt-button, .mt-form button { display:inline-block; border:1px solid var(--green); padding:11px 14px; background:transparent; color:var(--green); cursor:pointer; font-size:10px; font-weight:650; letter-spacing:.14em; }
  .mt-button.secondary { border-color:var(--line-strong); color:var(--text); }
  .mt-form { max-width:720px; padding-bottom:60px; }
  .mt-form label { display:block; margin-top:22px; color:var(--muted); font-size:11px; font-weight:650; letter-spacing:.12em; }
  .mt-form input, .mt-form select, .mt-form textarea { display:block; width:100%; margin-top:8px; padding:12px; background:var(--panel); border:1px solid var(--line-strong); color:var(--text); font:inherit; letter-spacing:normal; }
  .mt-form textarea { min-height:120px; }
  .mt-form button { margin-top:26px; }
  .mt-review { max-width:720px; border-top:1px solid var(--line); padding:24px 0 64px; }
  .mt-review dl { display:grid; grid-template-columns:180px 1fr; gap:10px 20px; margin:24px 0; }
  .mt-review dt { color:var(--faint); } .mt-review dd { overflow-wrap:anywhere; }
  .mt-warning { color:var(--amber) !important; }
  @media (max-width:700px) { .mt-hero { padding-top:94px; } .mt-card { grid-template-columns:1fr; } .mt-actions { justify-content:flex-start; } .mt-review dl { grid-template-columns:1fr; gap:4px; } }
</style>"""


@router.get("/missions", response_class=HTMLResponse)
def missions(request: Request):
    if _email(request) is None:
        return RedirectResponse("/login", status_code=303)
    console = _console(request)
    household_id = _household_id(console)
    body = """<section class="mt-hero"><div class="mt-k">MISSION TARGET MANAGEMENT</div>
<h1>Choose the destination.</h1><p>Declare, replace or withdraw the canonical destination for an existing Mission.</p></section>"""
    if household_id is None:
        return _page(console, "Missions", body +
                     '<p class="mt-empty">No active household is available. No Mission or Mission Target was created.</p>')
    cards = []
    for mission in console.entities.missions.values():
        access = _mission_access(console, mission.id, household_id)
        if access is None:
            continue
        mission, definition, descriptor, horizon_kind, state = access
        label = definition.label if definition is not None else mission.name
        metric = mission.target_metric or "No metric declared"
        if state == "unavailable":
            summary = "This Mission does not have complete target semantics and cannot be managed."
            actions = ""
        elif state == "conflict":
            summary = "Canonical Mission Target state is conflicted. No lifecycle action is available."
            actions = ""
        else:
            target = _current_target(_projection(console), mission.id)
            if target is None:
                summary = "No Mission Target declared."
                actions = (f'<a class="mt-button" href="/missions/targets/new?mission='
                           f'{quote(mission.id, safe="")}">DECLARE →</a>')
            else:
                summary = f"In force: {_format_destination(target)}"
                actions = (f'<a class="mt-button secondary" href="/missions/targets/new?mission='
                           f'{quote(mission.id, safe="")}">CHANGE</a>'
                           f'<a class="mt-button" href="/missions/targets/{quote(target.id, safe="")}/withdraw">WITHDRAW</a>')
        cards.append(f"""<article class="mt-card"><div><div class="mt-k">{html.escape(metric)}</div>
<h2>{html.escape(label)}</h2><p>{html.escape(summary)}</p></div><div class="mt-actions">{actions}</div></article>""")
    if not cards:
        body += '<p class="mt-empty">No manageable Missions exist in canonical state. Nothing was created to populate this page.</p>'
    else:
        body += '<section class="mt-list">' + "".join(cards) + "</section>"
    return _page(console, "Missions", body)


@router.get("/missions/targets/new", response_class=HTMLResponse)
def new_target(request: Request):
    email = _email(request)
    if email is None:
        return RedirectResponse("/login", status_code=303)
    mission_values = request.query_params.getlist("mission")
    if set(request.query_params) != {"mission"} or len(mission_values) != 1:
        return _refusal("Mission not found", 404)
    console = _console(request)
    household_id = _household_id(console)
    access = _mission_access(console, mission_values[0], household_id or "") \
        if household_id else None
    if access is None or access[-1] != "manageable":
        return _refusal("Mission not found", 404)
    selected, definition, _, horizon_kind, _ = access
    option = (
        f'<option value="{html.escape(selected.id, quote=True)}" selected>'
        f'{html.escape(definition.label if definition else selected.name)}</option>')
    token = html.escape(
        webauth.csrf_token(email, webauth.load_config(), _REVIEW_PURPOSE),
        quote=True,
    )
    date_field = ""
    if horizon_kind == "by_date":
        date_field = '<label>HORIZON DATE<input name="horizon_date" type="date" required></label>'
    body = f"""<section class="mt-hero"><div class="mt-k">MISSION TARGET MANAGEMENT</div>
<h1>Declare a destination.</h1><p>Review the canonical consequence before anything is written.</p></section>
<form class="mt-form" method="post" action="/missions/targets/review">
<input type="hidden" name="csrf" value="{token}">
<label>MISSION<select name="mission_id">{option}</select></label>
<label>DESTINATION VALUE<input name="destination_value" type="number" step="any" required></label>
{date_field}<label>OPTIONAL BASIS<textarea name="basis" maxlength="500"></textarea></label>
<p>Basis is optional. If approved, it becomes permanent append-only canonical history and cannot be edited or redacted here.</p>
<button type="submit">REVIEW DECLARATION →</button></form>"""
    return _page(console, "Declare Mission Target", body)


@router.post("/missions/targets/review", response_class=HTMLResponse)
async def review_target(request: Request):
    email = _email(request)
    if email is None:
        return RedirectResponse("/login", status_code=303)
    fields = await _body(request)
    allowed = {"csrf", "mission_id", "destination_value", "horizon_date", "basis"}
    if fields is None or not set(fields) <= allowed or "mission_id" not in fields:
        return _refusal("Forbidden", 403)
    console = _console(request)
    household_id = _household_id(console)
    access = _mission_access(console, fields["mission_id"], household_id or "") \
        if household_id else None
    if access is None or access[-1] != "manageable":
        return _refusal("Mission not found", 404)
    mission, definition, descriptor, horizon_kind, _ = access
    if (set(fields) != _expected_declaration_fields(horizon_kind, approval=False)
            or not webauth.verify_csrf(
                fields.get("csrf"), email, webauth.load_config(), _REVIEW_PURPOSE)):
        return _refusal("Forbidden", 403)
    projection = _projection(console)
    predecessor = _current_target(projection, mission.id)
    try:
        destination, horizon_at, basis = _operator_inputs(
            fields, descriptor, horizon_kind)
        _validate_declaration(
            projection,
            household_id=household_id,
            mission=mission,
            descriptor=descriptor,
            horizon_kind=horizon_kind,
            destination=destination,
            horizon_at=horizon_at,
            basis=basis,
            supersedes=predecessor.id if predecessor else None,
            effective_from=_now(),
        )
    except MissionTargetError as exc:
        return _refusal("Declaration refused: " + str(exc), 400)
    declare_token = html.escape(
        webauth.csrf_token(email, webauth.load_config(), _DECLARE_PURPOSE),
        quote=True,
    )
    reviewed = predecessor.id if predecessor else "none"
    hidden_date = (f'<input type="hidden" name="horizon_date" value="{html.escape(fields["horizon_date"], quote=True)}">'
                   if horizon_kind == "by_date" else "")
    horizon_label = fields["horizon_date"] if horizon_kind == "by_date" else horizon_kind
    predecessor_label = _format_destination(predecessor) if predecessor else "First declaration"
    body = f"""<section class="mt-hero"><div class="mt-k">REVIEW MISSION TARGET</div>
<h1>Make this permanent?</h1><p>Review is informational. Approval reloads current canonical state before append.</p></section>
<section class="mt-review"><dl><dt>Mission</dt><dd>{html.escape(definition.label if definition else mission.name)}</dd>
<dt>Metric</dt><dd>{html.escape(mission.target_metric)}</dd>
<dt>Destination</dt><dd>{html.escape(_format_input(destination))}</dd>
<dt>Direction</dt><dd>{html.escape(descriptor.destination_direction.replace('_', ' '))}</dd>
<dt>Horizon</dt><dd>{html.escape(horizon_label)}</dd>
<dt>Replaces</dt><dd>{html.escape(predecessor_label)}</dd>
<dt>Basis</dt><dd>{html.escape(basis or 'None supplied')}</dd></dl>
<p class="mt-warning">Approval creates permanent append-only canonical history. Any basis text becomes part of that permanent record; it cannot be edited or redacted here.</p>
<form class="mt-form" method="post" action="/missions/targets/declare">
<input type="hidden" name="csrf" value="{declare_token}">
<input type="hidden" name="mission_id" value="{html.escape(mission.id, quote=True)}">
<input type="hidden" name="destination_value" value="{html.escape(fields['destination_value'], quote=True)}">
{hidden_date}<input type="hidden" name="basis" value="{html.escape(fields['basis'], quote=True)}">
<input type="hidden" name="reviewed_in_force" value="{html.escape(reviewed, quote=True)}">
<button type="submit">APPROVE DECLARATION →</button></form></section>"""
    return _page(console, "Review Mission Target", body)


@router.post("/missions/targets/declare")
async def declare_target(request: Request):
    email = _email(request)
    if email is None:
        return RedirectResponse("/login", status_code=303)
    fields = await _body(request)
    allowed = {"csrf", "mission_id", "destination_value", "horizon_date", "basis", "reviewed_in_force"}
    if fields is None or not set(fields) <= allowed or "mission_id" not in fields:
        return _refusal("Forbidden", 403)
    console = _console(request)
    household_id = _household_id(console)
    access = _mission_access(console, fields["mission_id"], household_id or "") \
        if household_id else None
    if access is None:
        return _refusal("Mission not found", 404)
    if access[-1] != "manageable":
        return _refusal("Canonical state changed; review again", 409)
    mission, _, descriptor, horizon_kind, _ = access
    if (set(fields) != _expected_declaration_fields(horizon_kind, approval=True)
            or not webauth.verify_csrf(
                fields.get("csrf"), email, webauth.load_config(), _DECLARE_PURPOSE)):
        return _refusal("Forbidden", 403)
    projection = _projection(console)
    predecessor = _current_target(projection, mission.id)
    current_assertion = predecessor.id if predecessor else "none"
    if fields["reviewed_in_force"] != current_assertion:
        return _refusal("Canonical state changed; review again", 409)
    try:
        destination, horizon_at, basis = _operator_inputs(
            fields, descriptor, horizon_kind)
        effective_from = _now()
        _validate_declaration(
            projection,
            household_id=household_id,
            mission=mission,
            descriptor=descriptor,
            horizon_kind=horizon_kind,
            destination=destination,
            horizon_at=horizon_at,
            basis=basis,
            supersedes=predecessor.id if predecessor else None,
            effective_from=effective_from,
        )
        projection.declare(
            household_id=household_id,
            mission_id=mission.id,
            metric_id=mission.target_metric,
            destination=destination,
            destination_direction=descriptor.destination_direction,
            horizon_kind=horizon_kind,
            horizon_at=horizon_at,
            effective_from=effective_from,
            basis=basis,
            supersedes=predecessor.id if predecessor else None,
            actor=email,
        )
    except MissionTargetError as exc:
        return _refusal("Declaration refused: " + str(exc), 409)
    return RedirectResponse("/missions", status_code=303)


@router.get("/missions/targets/{target_id}/withdraw", response_class=HTMLResponse)
def withdraw_target(request: Request, target_id: str):
    email = _email(request)
    if email is None:
        return RedirectResponse("/login", status_code=303)
    console = _console(request)
    household_id = _household_id(console)
    projection = _projection(console)
    target = projection.targets.get(target_id)
    access = (_mission_access(console, target.mission_id, household_id or "")
              if target is not None and household_id else None)
    current = (_current_target(projection, target.mission_id)
               if target is not None else None)
    if (target is None or target.household_id != household_id or access is None
            or access[-1] != "manageable"
            or current is None or current.id != target.id):
        return _refusal("Mission Target not found", 404)
    mission, definition, _, _, _ = access
    token = html.escape(
        webauth.csrf_token(email, webauth.load_config(), _WITHDRAW_PURPOSE),
        quote=True,
    )
    body = f"""<section class="mt-hero"><div class="mt-k">WITHDRAW MISSION TARGET</div>
<h1>Withdraw this destination?</h1><p>{html.escape(definition.label if definition else mission.name)} · {html.escape(_format_destination(target))}</p></section>
<form class="mt-form" method="post" action="/missions/targets/withdraw">
<input type="hidden" name="csrf" value="{token}">
<input type="hidden" name="target_id" value="{html.escape(target.id, quote=True)}">
<input type="hidden" name="reviewed_in_force" value="{html.escape(target.id, quote=True)}">
<label>WITHDRAWAL REASON<input name="reason" required></label>
<button type="submit">APPROVE WITHDRAWAL →</button></form>"""
    return _page(console, "Withdraw Mission Target", body)


@router.post("/missions/targets/withdraw")
async def withdraw(request: Request):
    email = _email(request)
    if email is None:
        return RedirectResponse("/login", status_code=303)
    fields = await _body(request)
    expected = {"csrf", "target_id", "reviewed_in_force", "reason"}
    if (fields is None or set(fields) != expected
            or not webauth.verify_csrf(
                fields.get("csrf"), email, webauth.load_config(), _WITHDRAW_PURPOSE)):
        return _refusal("Forbidden", 403)
    console = _console(request)
    household_id = _household_id(console)
    projection = _projection(console)
    target = projection.targets.get(fields["target_id"])
    access = (_mission_access(console, target.mission_id, household_id or "")
              if target is not None and household_id else None)
    if target is None or target.household_id != household_id or access is None:
        return _refusal("Mission Target not found", 404)
    if access[-1] != "manageable":
        return _refusal("Canonical state changed; review again", 409)
    current = _current_target(projection, target.mission_id)
    current_assertion = current.id if current else "none"
    if (fields["reviewed_in_force"] != current_assertion
            or current is None or current.id != target.id):
        return _refusal("Canonical state changed; review again", 409)
    try:
        projection.withdraw(
            household_id=household_id,
            target_id=target.id,
            reason=fields["reason"],
            actor=email,
        )
    except MissionTargetError as exc:
        return _refusal("Withdrawal refused: " + str(exc), 409)
    return RedirectResponse("/missions", status_code=303)

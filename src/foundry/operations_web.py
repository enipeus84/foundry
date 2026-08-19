"""Authenticated, human-first RFC-012 Operations surface.

The Operations renderer is deliberately a consumer of the frozen RFC-011
pipeline.  It translates a small set of declared manual streams into ordinary
capture tasks; it never widens the manual contract or writes canonical events.
The original technical capture surface remains available behind an explicit
disclosure for an operator who genuinely needs it.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
import html
import json
import secrets
import time
from urllib.parse import parse_qs
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from foundry import webauth
from foundry.application.capture import CaptureService
from foundry.application.resources import FinancialResourceCommandService, ResourceCommandDenied
from foundry.capture_contracts import CaptureContract, CaptureContractRegistry, capture_contract_registry
from foundry.core.acquisition import (
    AcquisitionError, AssetRegistry, CanonicalObservationProjection,
    EnvelopeProjection, ProposalInbox, TelemetryStream, TelemetryStreamRegistry,
    ValuationLenses,
)
from foundry.core.capture_targets import CaptureTargetRegistry
from foundry.finance.capture_targets import FinanceCaptureTargetResolver, finance_asset_registry
from foundry.finance import entities as finance_entities
from foundry.finance.entities import FinanceEntityProjection
from foundry.finance import vocab as finance_vocab
from foundry.finance.pension_projection import (
    _from_payload as _projection_from_payload,
    record_pension_provider_projection,
)
from foundry.mission_control import _as_of, _footer, _render
from foundry.operations_console import OperationsConsoleModel

router = APIRouter()
_PURPOSE = "rfc012-capture"
_CONTRACT_PURPOSE = "rfc013-capture"
_PROJECTION_PURPOSE = "pension-projection-capture"
_PROJECTION_REVIEW_PURPOSE = "pension-projection-reviewed"
_PROJECTION_REVIEW_TTL = 10 * 60
_PROJECTION_REVIEW_CONSUMED = "operations.pension_projection_review.consumed"
_LONDON = ZoneInfo("Europe/London")


# These are presentation routes over the existing Finance declarations and
# RFC-015 compatibility table.  They are deliberately not a second registry.
_RESOURCE_KINDS = {
    "pension": {"contract": "pension-balance-update", "label": "pension account", "plural": "pension accounts", "capture": "balance updates",
                "entity": "account", "types": ("pension",)},
    "cash": {"contract": "cash-balance-update", "label": "cash account", "plural": "cash accounts", "capture": "cash balance updates",
             "entity": "account", "types": ("checking", "savings")},
    "isa": {"contract": "cash-balance-update", "label": "ISA account", "plural": "ISA accounts", "capture": "balance updates",
            "entity": "account", "types": ("isa",)},
    "property": {"contract": "property-valuation-update", "label": "property", "plural": "properties", "capture": "property valuation updates",
                 "entity": "asset", "types": ("property",)},
}


def _resource_kind_for_contract(contract_id: str) -> str | None:
    return next((kind for kind, spec in _RESOURCE_KINDS.items()
                 if spec["contract"] == contract_id), None)


def _active_members(console, household_id: str):
    return tuple(member for member in console.entities.members_of(household_id)
                 if member.status == "active")


def _resource_diagnosis(console, household_id: str, contract_id: str,
                        bootstrap_diagnostics=()) -> tuple[str, str, str | None] | None:
    diagnosis = CaptureService(console.log).availability(
        household_id, contract_id, bootstrap_diagnostics=tuple(bootstrap_diagnostics))
    if diagnosis is None:
        return None
    return diagnosis.message, diagnosis.action or "", diagnosis.resource_kind


def _email(request: Request) -> str | None:
    cfg = webauth.load_config()
    email = webauth.session_email(request.cookies.get(webauth.SESSION_COOKIE), cfg)
    return email if email and email == cfg.allowed_email else None


def _console(request: Request):
    return request.app.state.console_factory()


def _household(console) -> str | None:
    households = [party for party in console.entities.parties.values()
                  if party.party_type == "household" and party.status == "active"]
    return households[-1].id if households else None


def _model(console) -> OperationsConsoleModel:
    envelopes = EnvelopeProjection(console.log)
    streams = TelemetryStreamRegistry(console.log)
    inbox = ProposalInbox(console.log)
    registry = _asset_registry(console)
    observations = CanonicalObservationProjection(console.log, envelopes)
    return OperationsConsoleModel(
        registry, streams, inbox,
        ValuationLenses(registry, streams, observations), envelopes,
    )


def _target_registry(console) -> CaptureTargetRegistry:
    return CaptureTargetRegistry(console.log, FinanceCaptureTargetResolver(FinanceEntityProjection(console.log)))


def _asset_registry(console) -> AssetRegistry:
    return finance_asset_registry(console.log)


def _page(console, title: str, body: str) -> HTMLResponse:
    """Use Mission Control's shell: Operations is a destination, not a tool."""
    return _render(title, body + _footer(console), _as_of(console), "/operations")


def _contracts(request: Request) -> CaptureContractRegistry:
    """The composition root may inject a registry; renderers name no types."""
    registry = getattr(request.app.state, "capture_contract_registry", None)
    return registry if isinstance(registry, CaptureContractRegistry) else capture_contract_registry()


def _capture_service(request: Request, console) -> CaptureService:
    return CaptureService(console.log, _contracts(request), _household(console))


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


def _workflow(stream: TelemetryStream) -> dict[str, str] | None:
    """Presentation-only mapping from a declared stream to a safe draft.

    There is intentionally no generic fallback.  If Foundry cannot derive a
    valid draft from an existing stream contract, the normal UI must not imply
    that it can; the technical route remains an explicit expert operation.
    """
    property_name = stream.property.lower().replace("-", "_").replace(" ", "_")
    if property_name in {"units", "quantity", "holding_units"}:
        return {
            "title": "Record an investment purchase, sale or RSU vest",
            "prompt": "How many units are now held?",
            "hint": "Enter the total after this activity. Foundry will prepare it for review.",
            "observation_kind": "units",
            "event_kind": "finance.position.updated",
            "event_field": "quantity",
        }
    if property_name in {"price", "unit_price", "holding_price"}:
        return {
            "title": "Update an investment value",
            "prompt": "What is the price per unit?",
            "hint": "Use the value shown by your provider or statement.",
            "observation_kind": "price",
            "event_kind": "finance.position.updated",
            "event_field": "unit_price",
        }
    if property_name in {"statement_total", "account_total", "balance", "account_balance"}:
        return {
            "title": "Update a balance",
            "prompt": "What is the current balance?",
            "hint": "Foundry will ask you to review this update before it changes anything.",
            "observation_kind": "balance",
            "event_kind": "finance.account.reconciliation_observed",
            "event_field": "supplied_total",
        }
    return None


def _manual_streams(console, household_id: str) -> list[TelemetryStream]:
    streams = TelemetryStreamRegistry(console.log)
    return list(streams.active_manual_streams(household_id))


def _stream_label(stream: TelemetryStream) -> str:
    return stream.property.replace("_", " ").replace("-", " ").capitalize()


def _pension_accounts(console, household_id: str):
    """Return active canonical pensions owned by active household members."""
    member_ids = {
        member.id for member in console.entities.members_of(household_id)
        if member.status == "active"
    }
    finance = FinanceEntityProjection(console.log)
    return tuple(sorted(
        (
            account for account in finance.accounts.values()
            if account.status == "active" and account.account_type == "pension"
            and any(
                link.target in member_ids
                and link.relation in finance_vocab.VALUE_OWNERSHIP_RELATIONS
                for link in account.ownership
            )
        ),
        key=lambda account: (account.name or "", account.id),
    ))


def _display_date(timestamp: float) -> str:
    value = datetime.fromtimestamp(timestamp, _LONDON)
    return f"{value.day} {value.strftime('%B %Y')}"


def _projection_payload(fields: dict[str, str]) -> dict:
    """Translate human controls; domain validation remains authoritative."""
    payload = {
        "account_id": fields.get("account_id", ""),
        "provider": fields.get("provider", ""),
        "observed_at": _london_timestamp(fields.get("observed_at", "")),
        "fund_low": float(fields.get("fund_low", "")),
        "fund_medium": float(fields.get("fund_medium", "")),
        "fund_high": float(fields.get("fund_high", "")),
        "income_low": float(fields.get("income_low", "")),
        "income_medium": float(fields.get("income_medium", "")),
        "income_high": float(fields.get("income_high", "")),
        "growth_low_percent": float(fields.get("growth_low_percent", "")),
        "growth_medium_percent": float(fields.get("growth_medium_percent", "")),
        "growth_high_percent": float(fields.get("growth_high_percent", "")),
        "income_basis": fields.get("income_basis", ""),
        "source": fields.get("source", ""),
        "lineage": fields.get("lineage", ""),
    }
    if fields.get("retirement_age", "").strip():
        payload["retirement_age"] = float(fields["retirement_age"])
    if fields.get("retirement_at", "").strip():
        payload["retirement_at"] = _human_date(fields["retirement_at"])
    return payload


def _canonical_projection_payload(record) -> dict:
    """Serialize exactly the normalized object shown on the review page."""
    payload = {
        "account_id": record.account_id,
        "provider": record.provider,
        "observed_at": record.observed_at,
        "fund_low": record.fund_low,
        "fund_medium": record.fund_medium,
        "fund_high": record.fund_high,
        "income_low": record.income_low,
        "income_medium": record.income_medium,
        "income_high": record.income_high,
        "growth_low_percent": record.growth_low_percent,
        "growth_medium_percent": record.growth_medium_percent,
        "growth_high_percent": record.growth_high_percent,
        "income_basis": record.income_basis,
        "source": record.source,
        "lineage": record.lineage,
    }
    if record.retirement_age is not None:
        payload["retirement_age"] = record.retirement_age
    else:
        payload["retirement_at"] = record.retirement_at
    return payload


def _projection_review_token(record, email: str, cfg) -> str:
    return webauth.sign({
        "email": email,
        "purpose": _PROJECTION_REVIEW_PURPOSE,
        "jti": secrets.token_urlsafe(24),
        "projection": _canonical_projection_payload(record),
        "exp": int(time.time()) + _PROJECTION_REVIEW_TTL,
    }, cfg.session_secret)


def _verified_projection_review(token: str, email: str, cfg):
    signed = webauth.verify(token, cfg.session_secret)
    if (not signed or signed.get("email") != email
            or signed.get("purpose") != _PROJECTION_REVIEW_PURPOSE
            or not isinstance(signed.get("jti"), str)
            or not isinstance(signed.get("projection"), dict)):
        raise PermissionError
    return signed["jti"], _projection_from_payload(
        signed["projection"], "review")


def _consume_projection_review(log, token_id: str, email: str) -> None:
    """Durably consume before append; interruption fails closed, never twice."""
    if any(
        event.get("kind") == _PROJECTION_REVIEW_CONSUMED
        and event.get("payload", {}).get("token_id") == token_id
        for event in log.events()
    ):
        raise PermissionError
    log.append(_PROJECTION_REVIEW_CONSUMED, {
        "token_id": token_id,
        "purpose": _PROJECTION_REVIEW_PURPOSE,
    }, actor=email)


def _projection_summary(record, *, heading: str, action: str = "") -> str:
    target = (
        f"Retirement age: {record.retirement_age:g}"
        if record.retirement_age is not None
        else f"Retirement date: {_display_date(record.retirement_at)}"
    )
    hidden = action
    return f'''<section class="ops-hero"><div class="ops-eyebrow">OPERATIONS · PENSION PROJECTION</div>
<h1>{html.escape(heading)}</h1><p>As at: {_display_date(record.observed_at)}<br>{html.escape(target)}</p></section>
<section class="ops-panel"><h2>Projected fund</h2><div class="ops-list">
<div class="ops-item"><div><h3>Low £{record.fund_low:,.0f}</h3></div></div>
<div class="ops-item"><div><h3>Medium £{record.fund_medium:,.0f}</h3></div></div>
<div class="ops-item"><div><h3>High £{record.fund_high:,.0f}</h3></div></div></div></section>
<section class="ops-panel"><h2>Estimated yearly income</h2><div class="ops-list">
<div class="ops-item"><div><h3>Low £{record.income_low:,.0f}</h3></div></div>
<div class="ops-item"><div><h3>Medium £{record.income_medium:,.0f}</h3></div></div>
<div class="ops-item"><div><h3>High £{record.income_high:,.0f}</h3></div></div></div></section>
<section class="ops-panel"><h2>Provider basis</h2><div class="ops-list">
<div class="ops-item"><div><h3>Growth assumptions</h3><p>Low {record.growth_low_percent:g}% · Medium {record.growth_medium_percent:g}% · High {record.growth_high_percent:g}%</p></div></div>
<div class="ops-item"><div><h3>Income basis</h3><p>{html.escape(record.income_basis)}</p></div></div>
<div class="ops-item"><div><h3>Evidence</h3><p>{html.escape(record.source)} · {html.escape(record.lineage)}</p></div></div></div></section>{hidden}'''


def _operational_summary(view) -> str:
    """Translate model status into the operator's decision, not its clock."""
    actionable = sum(item.actionable for item in view.items)
    if view.nominal:
        return view.summary_line()
    if actionable == 0:
        return "No operational action is waiting, but some information is still unavailable."
    return f"{actionable} {'item needs' if actionable == 1 else 'items need'} your attention."


def _human_date(value: str) -> float:
    """Accept normal browser date controls, never expose epoch time by default."""
    try:
        if "T" in value:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.timestamp()
        return datetime.combine(date.fromisoformat(value), datetime.min.time(), timezone.utc).timestamp()
    except ValueError as exc:
        raise ValueError("Please enter a valid date.") from exc


def _london_datetime_input(now: datetime | None = None) -> str:
    """Format a London-local instant for a native datetime-local control."""
    return (now or datetime.now(_LONDON)).astimezone(_LONDON).strftime("%Y-%m-%dT%H:%M")


def _london_timestamp(value: str) -> float:
    """Interpret a browser datetime-local value as Europe/London wall time."""
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is not None:
            raise ValueError
        return parsed.replace(tzinfo=_LONDON).timestamp()
    except ValueError as exc:
        raise ValueError("Please enter a valid date and time.") from exc


def _operations_styles() -> str:
    return """<style>
  .ops-hero { padding: 126px 0 56px; border-bottom: 1px solid var(--line); margin-bottom: 52px; }
  .ops-hero h1 { font-size: clamp(42px,6vw,68px); font-weight: 540; letter-spacing: -.04em; line-height: 1; margin: 10px 0 16px; }
  .ops-hero p { max-width: 59ch; color: var(--muted); font-size: 16px; line-height: 1.65; }
  .ops-eyebrow, .ops-k, .ops-panel h2 { font-size: 9px; font-weight: 650; letter-spacing: .22em; color: var(--faint); text-transform: uppercase; }
  .ops-status { color: var(--green); font-size: 12px; font-weight: 650; letter-spacing: .12em; margin-top: 18px; }
  .ops-status.watch { color: var(--amber); }
  .ops-actions, .ops-grid { display: grid; gap: 1px; border: 1px solid var(--line); background: var(--line); }
  .ops-actions { grid-template-columns: minmax(0,1.75fr) minmax(0,1fr); margin: 28px 0 70px; }
  .ops-action, .ops-stat, .ops-panel { background: var(--surface); padding: 25px; }
  .ops-action { display: block; transition: background .16s ease-out; }
  .ops-action:hover { background: var(--elevated); }
  .ops-action h2 { color: var(--text); font-size: 20px; font-weight: 550; margin: 8px 0; }
  .ops-action p, .ops-stat p { color: var(--muted); font-size: 13px; line-height: 1.6; }
  .ops-action .ops-cta { color: var(--green); font-size: 10px; font-weight: 650; letter-spacing: .16em; margin-top: 18px; }
  .ops-grid { grid-template-columns: repeat(4, minmax(0,1fr)); margin-bottom: 72px; }
  .ops-stat .ops-value { color: var(--text); font-size: 30px; line-height: 1; margin: 11px 0 9px; }
  .ops-stat.warn .ops-value { color: var(--amber); }
  .ops-panel { margin-bottom: 1px; }
  .ops-panel + .ops-panel { border-top: 1px solid var(--line); }
  .ops-list { border-top: 1px solid var(--line); }
  .ops-item { display: grid; grid-template-columns: minmax(0,1fr) auto; gap: 22px; align-items: center; padding: 22px 0; border-bottom: 1px solid var(--line); }
  .ops-item h3 { font-size: 16px; font-weight: 550; margin-bottom: 5px; }
  .ops-item p { color: var(--muted); font-size: 13px; line-height: 1.55; }
  .ops-button { display: inline-block; border: 1px solid var(--line-strong); padding: 10px 13px; color: var(--text); font-size: 10px; font-weight: 650; letter-spacing: .14em; white-space: nowrap; }
  .ops-button.primary { border-color: var(--green); color: var(--green); }
  .ops-empty { color: var(--muted); line-height: 1.65; padding: 20px 0 4px; }
  .ops-form { max-width: 720px; }
  .ops-form label { display:block; margin: 22px 0 0; color: var(--muted); font-size: 11px; font-weight: 650; letter-spacing: .12em; }
  .ops-form input, .ops-form select, .ops-form textarea { display:block; width:100%; margin-top:8px; padding:12px; background:var(--panel); border:1px solid var(--line-strong); color:var(--text); font:inherit; letter-spacing: normal; }
  .ops-form textarea { min-height: 138px; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; }
  .ops-form .hint { color: var(--faint); font-size: 12px; letter-spacing: normal; line-height: 1.55; margin-top: 7px; }
  .ops-submit { margin-top: 26px; border: 1px solid var(--green); padding: 12px 16px; background: transparent; color: var(--green); cursor:pointer; font-size: 10px; font-weight:650; letter-spacing:.16em; }
  .ops-disclosure { margin-top: 54px; border-block: 1px solid var(--line); }
  .ops-disclosure summary { cursor:pointer; padding:18px 2px; color:var(--muted); font-size:10px; font-weight:650; letter-spacing:.16em; }
  .ops-disclosure summary::after { content:"+"; float:right; font-size:16px; }
  .ops-disclosure[open] summary::after { content:"−"; }
  .ops-disclosure .ops-form { padding: 0 0 28px; }
  @media (max-width: 760px) { .ops-hero { padding-top: 94px; margin-bottom: 40px; } .ops-actions, .ops-grid { grid-template-columns: 1fr; } .ops-actions { margin-bottom: 52px; } .ops-grid { margin-bottom: 54px; } .ops-item { grid-template-columns: 1fr; gap: 16px; } .ops-button { justify-self: start; } }
</style>"""


@router.get("/operations", response_class=HTMLResponse)
def operations(request: Request):
    email = _email(request)
    if email is None:
        return RedirectResponse("/login", status_code=303)
    console = _console(request)
    household = _household(console)
    if household is None:
        body = _operations_styles() + """<section class="ops-hero"><div class="ops-eyebrow">OPERATIONS</div>
<h1>Ready when you are.</h1><p>Foundry needs an active household before there is anything to operate.</p></section>"""
        return _page(console, "Operations", body)

    as_of = max((event["ts"] for event in console.log.events()), default=0.0)
    view = _model(console).view(household, as_of=as_of, known_at=as_of)
    inbox = ProposalInbox(console.log)
    envelopes = EnvelopeProjection(console.log)
    pending = [proposal for proposal in inbox.proposals.values()
               if proposal.state == "pending" and proposal.household_id == household
               and TelemetryStreamRegistry(console.log).is_active(proposal.stream_id)]
    validation_issues = sum(
        1 for proposal in pending
        if any(item.get("outcome") in {"ambiguous", "unresolved"} for item in proposal.resolutions)
    )
    action_count = sum(item.actionable for item in view.items)
    recent = sorted(
        (envelope for envelope in envelopes.envelopes.values()
         if (stream := TelemetryStreamRegistry(console.log).streams.get(envelope.stream_id))
         and stream.household_id == household),
        key=lambda envelope: envelope.received_at, reverse=True,
    )[:3]
    status = "All caught up" if not action_count else "Attention needed"
    status_class = "" if not action_count else " watch"
    body = _operations_styles() + f"""<section class="ops-hero">
  <div class="ops-eyebrow">FOUNDRY · OPERATIONS</div>
  <h1>Keep your plan current.</h1>
  <p>{html.escape(_operational_summary(view))} Record what changed, review it once, and let Foundry keep the evidence trail.</p>
  <div class="ops-status{status_class}">{html.escape(status).upper()}</div>
</section>
<section class="ops-actions" aria-label="Operations actions">
  <a class="ops-action" href="/operations/capture"><div class="ops-k">CAPTURE NEW INFORMATION</div><h2>What changed?</h2><p>Record a balance, investment activity or other registered update in a few plain-language steps.</p><div class="ops-cta">START A CAPTURE →</div></a>
  <a class="ops-action" href="/acquisition/inbox"><div class="ops-k">ACQUISITION QUEUE</div><h2>{len(pending)} awaiting review</h2><p>Review captured information before it becomes part of your plan.</p><div class="ops-cta">REVIEW CAPTURES →</div></a>
</section>
<section class="ops-grid" aria-label="Operational awareness">
  <div class="ops-stat"><div class="ops-k">PENDING ITEMS</div><div class="ops-value">{action_count}</div><p>Items that need an action.</p></div>
  <div class="ops-stat"><div class="ops-k">RECENTLY CAPTURED</div><div class="ops-value">{len(recent)}</div><p>Most recent evidence records.</p></div>
  <div class="ops-stat{' warn' if validation_issues else ''}"><div class="ops-k">VALIDATION ISSUES</div><div class="ops-value">{validation_issues}</div><p>Captures that need identity review.</p></div>
  <div class="ops-stat{' warn' if action_count else ''}"><div class="ops-k">PROCESSING STATUS</div><div class="ops-value">{'READY' if not action_count else 'ACTION'}</div><p>{'Nothing is waiting.' if not action_count else 'Review or refresh the items below.'}</p></div>
</section>
<section class="ops-panel"><h2>What needs attention</h2><div class="ops-list">"""
    if view.items:
        action_labels = {"review": "Review capture", "resolve": "Review identity", "capture": "Update now"}
        for item in view.items:
            href = "/acquisition/inbox" if item.action in {"review", "resolve"} else "/operations/capture"
            body += f"""<div class="ops-item"><div><h3>{html.escape(item.summary)}</h3>
<p>{'Foundry needs a human decision before it can continue.' if item.action in {'review', 'resolve'} else 'Record the latest information to bring this item up to date.'}</p></div>
<a class="ops-button" href="{href}">{action_labels.get(item.action, 'Open')} →</a></div>"""
    else:
        body += "<p class=\"ops-empty\">No operational action is waiting. Capture a new fact whenever something meaningful changes.</p>"
    body += "</div></section><section class=\"ops-panel\"><h2>Recently captured facts</h2><div class=\"ops-list\">"
    if recent:
        streams = TelemetryStreamRegistry(console.log)
        for envelope in recent:
            stream = streams.streams.get(envelope.stream_id)
            body += f"<div class=\"ops-item\"><div><h3>{html.escape(_stream_label(stream) if stream else 'Captured information')}</h3><p>Captured evidence is awaiting or has completed its review path.</p></div><a class=\"ops-button\" href=\"/acquisition/inbox\">VIEW QUEUE →</a></div>"
    else:
        body += "<p class=\"ops-empty\">No information has been captured yet.</p>"
    body += "</div></section>"
    return _page(console, "Operations", body)


@router.get("/operations/capture", response_class=HTMLResponse)
def capture_form(request: Request):
    email = _email(request)
    if email is None:
        return RedirectResponse("/login", status_code=303)
    console = _console(request)
    bootstrap_result = getattr(request.app.state, "capture_target_bootstrap_result", None)
    fallback_diagnostic = getattr(request.app.state, "capture_target_bootstrap_diagnostic", None)
    household = _household(console)
    if household is None:
        return _page(console, "Capture information", _operations_styles() + "<section class=\"ops-hero\"><h1>Nothing to capture yet.</h1><p>An active household is required before a capture can be recorded.</p></section>")
    streams = _manual_streams(console, household)
    targets = _target_registry(console)
    registry = _contracts(request)
    contract_id = request.query_params.get("contract")
    if contract_id:
        contract = registry.get(contract_id)
        if contract is None:
            return HTMLResponse("Not found", status_code=404)
        eligible = targets.for_contract(household, contract)
        if not eligible:
            diagnostics = (bootstrap_result.diagnostics if bootstrap_result is not None
                           else ((fallback_diagnostic,) if fallback_diagnostic is not None else ()))
            diagnosis = _resource_diagnosis(console, household, contract.identifier, diagnostics)
            if diagnosis is not None:
                message, action, kind = diagnosis
                link = (f'<p><a class="ops-button primary" href="/operations/resources/new?kind={html.escape(kind, quote=True)}">{html.escape(action).upper()} →</a></p>'
                        if kind else "")
                return _page(console, "Capture information", _operations_styles() +
                             f"<section class=\"ops-hero\"><div class=\"ops-eyebrow\">OPERATIONS · CAPTURE</div><h1>{html.escape(contract.display_name)}</h1><p>{html.escape(message)}</p>{link}<p><a href=\"/operations/capture\">Choose another capture type</a></p></section>")
            return _page(console, "Capture information", _operations_styles() +
                         f"<section class=\"ops-hero\"><div class=\"ops-eyebrow\">OPERATIONS · CAPTURE</div><h1>{html.escape(contract.display_name)}</h1><p>No compatible Capture Targets are registered.</p><p><a href=\"/operations/capture\">Choose another capture type</a></p></section>")
        token = html.escape(webauth.csrf_token(email, webauth.load_config(), _CONTRACT_PURPOSE), quote=True)
        options = "".join(
            f'<option value="{html.escape(target.id, quote=True)}">{html.escape(target.entity.display_name or target.subject_id)} · {html.escape(_stream_label(target.stream))}</option>'
            for target in eligible
        )
        rendered_fields = []
        for field in contract.schema:
            required_attribute = " required" if field.required else ""
            step_attribute = ' step="any"' if field.input_type == "number" else ""
            if field.name == "valid_at":
                rendered_fields.append(
                    f'<label>{html.escape(field.label)}<input name="valid_at" type="datetime-local" value="{_london_datetime_input()}"{required_attribute}></label>'
                    f'<p class="hint">{html.escape(field.help_text)}</p>'
                )
                continue
            if field.name == "currency":
                rendered_fields.append(
                    f'<label>{html.escape(field.label)}<input name="currency" type="text" value="GBP"{required_attribute}></label>'
                    f'<p class="hint">{html.escape(field.help_text)}</p>'
                )
                continue
            if field.name == "valuation_basis":
                rendered_fields.append(
                    '<label>Valuation basis<select name="valuation_basis" required>'
                    '<option value="owner_estimate">Owner estimate</option>'
                    '<option value="purchase_price">Purchase price</option>'
                    '<option value="index_estimate">Index/automated estimate</option>'
                    '<option value="agent_appraisal">Agent appraisal</option>'
                    '<option value="lender_valuation">Lender valuation</option>'
                    '</select></label>'
                    f'<p class="hint">{html.escape(field.help_text)}</p>')
                continue
            if field.name == "source":
                rendered_fields.append(
                    f'<label>{html.escape(field.label)}<input name="source" type="text" value="Household estimate" required></label>'
                    f'<p class="hint">{html.escape(field.help_text)}</p>')
                continue
            rendered_fields.append(
                f'<label>{html.escape(field.label)}<input name="{html.escape(field.name, quote=True)}" type="{html.escape(field.input_type, quote=True)}"{required_attribute}{step_attribute}></label>'
                f'<p class="hint">{html.escape(field.help_text)}</p>'
            )
        body = _operations_styles() + f'''<section class="ops-hero"><div class="ops-eyebrow">OPERATIONS · CAPTURE</div>
<h1>{html.escape(contract.display_name)}</h1><p>{html.escape(contract.description)}</p>
<p class="ops-status">Version {html.escape(contract.version)} · Evidence policy: {html.escape(contract.evidence_policy.value)}</p></section>
<section class="ops-panel"><h2>Capture an update</h2><p class="ops-empty">{html.escape(_evidence_reference_policy(contract))}</p>
<form class="ops-form" method="post" action="/operations/capture"><input type="hidden" name="csrf" value="{token}">
<input type="hidden" name="contract_id" value="{html.escape(contract.identifier, quote=True)}">
<label>Target stream<select name="stream_id">{options}</select></label>{''.join(rendered_fields)}
<button class="ops-submit" type="submit">CREATE REVIEW CAPTURE →</button></form></section>'''
        return _page(console, "Capture information", body)

    contracts = registry.discover()
    cards = "".join(
        f'''<div class="ops-item"><div><h3>{html.escape(contract.display_name)}</h3>
<p>{html.escape(contract.description)}</p><p>{html.escape(_evidence_reference_policy(contract))}</p></div>
<a class="ops-button primary" href="/operations/capture?contract={html.escape(contract.identifier, quote=True)}">RECORD →</a></div>'''
        for contract in contracts
    )
    if _pension_accounts(console, household):
        cards += '''<div class="ops-item"><div><h3>Pension Projection Update</h3>
<p>Record a dated provider pension illustration for review and confirmation.</p></div>
<a class="ops-button primary" href="/operations/pension-projection">RECORD →</a></div>'''
    guided = [(stream, _workflow(stream)) for stream in streams if _workflow(stream)]
    token = html.escape(webauth.csrf_token(email, webauth.load_config(), _PURPOSE), quote=True)
    options = "".join(
        f'<option value="{html.escape(stream.id, quote=True)}">{html.escape(workflow["title"])} · {html.escape(_stream_label(stream))}</option>'
        for stream, workflow in guided
    )
    body = _operations_styles() + """<section class="ops-hero"><div class="ops-eyebrow">OPERATIONS · CAPTURE</div>
<h1>What do you want to record?</h1><p>Tell Foundry what changed in ordinary terms. It will create a reviewable capture; nothing changes in your plan until you approve it.</p></section>"""
    bootstrap_diagnostics = (bootstrap_result.diagnostics if bootstrap_result is not None
                             else ((fallback_diagnostic,) if fallback_diagnostic is not None else ()))
    target_count = len(targets.for_household(household))
    if bootstrap_diagnostics:
        outcome = "partially completed" if target_count else "failed"
        target_summary = (f"{target_count} capture target{'s' if target_count != 1 else ''} "
                          f"{'is' if target_count == 1 else 'are'} registered."
                          if target_count else "No capture targets were registered.")
        details = "".join(
            f"<li>{html.escape(item.validation)}: {html.escape(item.reason)}</li>"
            for item in bootstrap_diagnostics)
        body += f'''<section class="ops-panel"><h2>Capture target bootstrap {outcome}</h2><p class="ops-empty">Foundry recorded {len(bootstrap_diagnostics)} bootstrap issue{'s' if len(bootstrap_diagnostics) != 1 else ''}. {target_summary}</p><ul class="ops-empty">{details}</ul></section>'''
    elif bootstrap_result is not None and target_count:
        body += f'''<section class="ops-panel"><h2>Capture targets ready</h2><p class="ops-empty">Bootstrap completed successfully. {target_count} capture target{'s' if target_count != 1 else ''} {'is' if target_count == 1 else 'are'} registered.</p></section>'''
    elif bootstrap_result is not None:
        body += '''<section class="ops-panel"><h2>No eligible capture targets</h2><p class="ops-empty">Bootstrap completed successfully, but this household has no eligible entities to register.</p></section>'''
    if cards:
        body += f'''<section class="ops-panel"><h2>WHAT DO YOU WANT TO RECORD?</h2><div class="ops-list">{cards}</div></section>'''
    if guided:
        body += f"""<section class="ops-panel"><h2>Capture an update</h2><form class="ops-form" method="post" action="/operations/capture">
<input type="hidden" name="csrf" value="{token}"><input type="hidden" name="mode" value="guided">
<label>What changed?<select name="stream_id" required>{options}</select></label>
<label>New value<input name="value" type="number" step="any" inputmode="decimal" required></label>
<label>When did this take effect?<input name="valid_at" type="date" required></label>
<label>Reference (optional)<input name="external_ref" maxlength="200" placeholder="Statement or confirmation reference"></label>
<p class="hint">Your selected update determines the right Foundry record automatically. You will review it before confirmation.</p>
<button class="ops-submit" type="submit">CREATE REVIEW CAPTURE →</button></form></section>"""
    elif not contracts:
        body += """<section class="ops-panel"><h2>Capture is not configured</h2><p class="ops-empty">There are no registered manual updates that Foundry can safely turn into a guided capture yet. Technical capture remains available for the authorised operator.</p></section>"""
    elif not targets.for_household(household):
        body += """<section class="ops-panel"><h2>Capture Contracts are available</h2><p class="ops-empty">Operations is configured, but no compatible Capture Targets are currently registered.</p></section>"""
    technical_options = "".join(f'<option value="{html.escape(stream.id, quote=True)}">{html.escape(stream.id)}</option>' for stream in streams)
    body += f"""<details class="ops-disclosure"><summary>TECHNICAL DETAILS</summary>
<form class="ops-form" method="post" action="/operations/capture"><input type="hidden" name="csrf" value="{token}"><input type="hidden" name="mode" value="technical">
<label>Registered stream<select name="stream_id">{technical_options}</select></label>
<label>Subject identifier<input name="subject_id" required></label><label>Observation type<input name="kind" required></label>
<label>Value<input name="value" type="number" step="any" required></label><label>Effective time (Unix timestamp)<input name="valid_at" type="number" step="any" required></label>
<label>External reference<input name="external_ref"></label><label>Canonical event type<input name="event_kind" value="finance.position.updated" required></label>
<label>Canonical event payload (JSON)<textarea name="event_payload" required>{{&quot;entity_id&quot;:&quot;&quot;}}</textarea></label>
<button class="ops-submit" type="submit">SUBMIT TECHNICAL CAPTURE →</button></form></details>"""
    return _page(console, "Capture information", body)


_PROJECTION_FIELDS = frozenset({
    "account_id", "provider", "observed_at", "retirement_age", "retirement_at",
    "fund_low", "fund_medium", "fund_high", "income_low", "income_medium",
    "income_high", "growth_low_percent", "growth_medium_percent",
    "growth_high_percent", "income_basis", "source", "lineage",
})


@router.get("/operations/pension-projection", response_class=HTMLResponse)
def pension_projection_form(request: Request):
    email = _email(request)
    if email is None:
        return RedirectResponse("/login", status_code=303)
    console = _console(request)
    household = _household(console)
    accounts = _pension_accounts(console, household or "")
    if not accounts:
        return _page(console, "Pension projection", _operations_styles() +
                     '<section class="ops-hero"><h1>No pension account available.</h1><p>A canonical active pension account is required before a provider projection can be recorded.</p></section>')
    token = html.escape(webauth.csrf_token(
        email, webauth.load_config(), _PROJECTION_PURPOSE), quote=True)
    options = (
        "" if len(accounts) == 1
        else '<option value="" selected disabled>Choose a pension account</option>'
    ) + "".join(
        f'<option value="{html.escape(account.id, quote=True)}"{(" selected" if len(accounts) == 1 else "")}>{html.escape(account.name or account.id)}</option>'
        for account in accounts)
    now = _london_datetime_input()
    body = _operations_styles() + f'''<section class="ops-hero"><div class="ops-eyebrow">OPERATIONS · CAPTURE</div>
<h1>Pension Projection Update</h1><p>Record the provider's illustration as a dated forecast observation. It will not change the pension balance or Net Worth.</p></section>
<section class="ops-panel"><h2>Provider illustration</h2>
<form class="ops-form" method="post" action="/operations/pension-projection/review">
<input type="hidden" name="csrf" value="{token}">
<label>Pension account<select name="account_id" required>{options}</select></label>
<label>Provider<input name="provider" value="Aviva" required></label>
<label>As at<input name="observed_at" type="datetime-local" value="{now}" required></label>
<label>Retirement age<input name="retirement_age" type="number" step="any"></label>
<label>Retirement date<input name="retirement_at" type="date"></label>
<p class="hint">Enter exactly one retirement target: age or date.</p>
<label>Projected fund · Low (£)<input name="fund_low" type="number" min="0" step="any" required></label>
<label>Projected fund · Medium (£)<input name="fund_medium" type="number" min="0" step="any" required></label>
<label>Projected fund · High (£)<input name="fund_high" type="number" min="0" step="any" required></label>
<label>Estimated yearly income · Low (£)<input name="income_low" type="number" min="0" step="any" required></label>
<label>Estimated yearly income · Medium (£)<input name="income_medium" type="number" min="0" step="any" required></label>
<label>Estimated yearly income · High (£)<input name="income_high" type="number" min="0" step="any" required></label>
<label>Growth assumption · Low (%)<input name="growth_low_percent" type="number" step="any" required></label>
<label>Growth assumption · Medium (%)<input name="growth_medium_percent" type="number" step="any" required></label>
<label>Growth assumption · High (%)<input name="growth_high_percent" type="number" step="any" required></label>
<label>Income basis<input name="income_basis" required></label>
<label>Source / evidence<input name="source" required></label>
<label>Lineage / provenance<input name="lineage" required></label>
<button class="ops-submit" type="submit">REVIEW PROJECTION →</button></form></section>'''
    return _page(console, "Pension projection", body)


def _projection_submission(fields, email, request):
    if (not fields or set(fields) - (_PROJECTION_FIELDS | {"csrf"})
            or not webauth.verify_csrf(
                fields.get("csrf"), email, webauth.load_config(), _PROJECTION_PURPOSE)):
        raise PermissionError
    console = _console(request)
    household = _household(console)
    eligible = {account.id for account in _pension_accounts(console, household or "")}
    if fields.get("account_id") not in eligible:
        raise LookupError
    payload = _projection_payload(fields)
    return console, payload, _projection_from_payload(payload, "review")


@router.post("/operations/pension-projection/review", response_class=HTMLResponse)
async def pension_projection_review(request: Request):
    email = _email(request)
    if email is None:
        return RedirectResponse("/login", status_code=303)
    fields = await _body(request)
    try:
        console, _, record = _projection_submission(fields, email, request)
    except PermissionError:
        return HTMLResponse("Forbidden", status_code=403)
    except LookupError:
        return HTMLResponse("Not found", status_code=404)
    except (KeyError, TypeError, ValueError) as exc:
        return HTMLResponse("Capture refused: " + html.escape(str(exc)), status_code=400)
    review_token = html.escape(_projection_review_token(
        record, email, webauth.load_config()), quote=True)
    csrf = html.escape(fields["csrf"], quote=True)
    action = f'''<section class="ops-panel"><h2>Confirm observation</h2>
<p class="ops-empty">{html.escape(record.income_basis)} · {html.escape(record.source)} · {html.escape(record.lineage)}</p>
<form method="post" action="/operations/pension-projection/confirm">
<input type="hidden" name="csrf" value="{csrf}">
<input type="hidden" name="review_token" value="{review_token}">
<button class="ops-submit" type="submit">CONFIRM AND RECORD →</button></form></section>'''
    return _page(console, "Review pension projection",
                 _operations_styles() + _projection_summary(
                     record, heading=f"Review {record.provider} pension projection", action=action))


@router.post("/operations/pension-projection/confirm", response_class=HTMLResponse)
async def pension_projection_confirm(request: Request):
    email = _email(request)
    if email is None:
        return RedirectResponse("/login", status_code=303)
    fields = await _body(request)
    cfg = webauth.load_config()
    try:
        if (not fields or set(fields) != {"csrf", "review_token"}
                or not webauth.verify_csrf(
                    fields.get("csrf"), email, cfg, _PROJECTION_PURPOSE)):
            raise PermissionError
        token_id, reviewed = _verified_projection_review(
            fields["review_token"], email, cfg)
        console = _console(request)
        household = _household(console)
        eligible = {
            account.id for account in _pension_accounts(console, household or "")}
        if reviewed.account_id not in eligible:
            raise LookupError
        _consume_projection_review(console.log, token_id, email)
        record = record_pension_provider_projection(
            console.log, actor=email,
            **_canonical_projection_payload(reviewed))
    except PermissionError:
        return HTMLResponse("Forbidden", status_code=403)
    except LookupError:
        return HTMLResponse("Not found", status_code=404)
    except (KeyError, TypeError, ValueError) as exc:
        return HTMLResponse("Capture refused: " + html.escape(str(exc)), status_code=400)
    action = '''<section class="ops-panel"><h2>Next</h2><p class="ops-empty">The provider observation is now available to Pension Independence.</p>
<a class="ops-button primary" href="/missions/pension-independence">VIEW PENSION INDEPENDENCE →</a></section>'''
    return _page(_console(request), "Pension projection recorded",
                 _operations_styles() + _projection_summary(
                     record, heading=f"{record.provider} pension projection recorded", action=action))


@router.get("/operations/resources/new", response_class=HTMLResponse)
def new_resource(request: Request):
    email = _email(request)
    if email is None:
        return RedirectResponse("/login", status_code=303)
    kind = request.query_params.get("kind", "")
    spec = _RESOURCE_KINDS.get(kind)
    console = _console(request)
    household = _household(console)
    if spec is None or household is None:
        return HTMLResponse("Not found", status_code=404)
    members = _active_members(console, household)
    if not members:
        return _page(console, "Register resource", _operations_styles() +
                     "<section class=\"ops-hero\"><h1>No owner is available.</h1><p>An active household member is required before a financial resource can be registered.</p></section>")
    token = html.escape(webauth.csrf_token(email, webauth.load_config(), "finance-resource-registration"), quote=True)
    types = "".join(f'<option value="{item}">{html.escape(item.title())}</option>' for item in spec["types"])
    owner_options = "".join(f'<option value="{html.escape(member.id, quote=True)}">{html.escape(member.attributes.get("name") or member.id)}</option>' for member in members)
    body = _operations_styles() + f'''<section class="ops-hero"><div class="ops-eyebrow">OPERATIONS · RESOURCE</div>
<h1>Register {html.escape(spec['label'])}.</h1><p>Record the economic resource and its owner. Foundry will prepare any compatible capture route automatically.</p></section>
<section class="ops-panel"><form class="ops-form" method="post" action="/operations/resources">
<input type="hidden" name="csrf" value="{token}"><input type="hidden" name="kind" value="{html.escape(kind, quote=True)}">
<label>Name or provider<input name="name" maxlength="200" required></label><label>Resource type<select name="resource_type" required>{types}</select></label>
<label>Currency<input name="currency" value="GBP" minlength="3" maxlength="3" required></label><label>Owner<select name="owner_id" required>{owner_options}</select></label>
<p class="hint">Ownership is an economic fact. It is independent of any Mission Target subject.</p><button class="ops-submit" type="submit">REGISTER {html.escape(spec['label']).upper()} →</button></form></section>'''
    return _page(console, "Register resource", body)


@router.post("/operations/resources")
async def create_resource(request: Request):
    email = _email(request)
    if email is None:
        return RedirectResponse("/login", status_code=303)
    fields = await _body(request)
    required = {"csrf", "kind", "name", "resource_type", "currency", "owner_id"}
    if not fields or set(fields) != required:
        return HTMLResponse("Forbidden", status_code=403)
    if not webauth.verify_csrf(fields["csrf"], email, webauth.load_config(), "finance-resource-registration"):
        return HTMLResponse("Forbidden", status_code=403)
    spec = _RESOURCE_KINDS.get(fields["kind"])
    if spec is None or fields["resource_type"] not in spec["types"]:
        return HTMLResponse("Resource refused", status_code=400)
    name, currency = fields["name"].strip(), fields["currency"].strip().upper()
    if not name or len(currency) != 3 or not currency.isalpha():
        return HTMLResponse("Resource refused: name and three-letter currency are required", status_code=400)
    console = _console(request)
    household = _household(console)
    if household is None or fields["owner_id"] not in {member.id for member in _active_members(console, household)}:
        return HTMLResponse("Forbidden", status_code=403)
    try:
        resource = FinancialResourceCommandService(console.log).create_financial_resource(
            household_id=household, resource_type=fields["resource_type"], currency=currency,
            name=name, owner=fields["owner_id"], actor=email, require_authority=False)
    except (TypeError, ValueError, AcquisitionError, ResourceCommandDenied) as exc:
        return HTMLResponse("Resource refused: " + html.escape(str(exc)), status_code=400)
    return RedirectResponse(f"/operations/capture?contract={spec['contract']}", status_code=303)


async def _body(request: Request) -> dict[str, str] | None:
    if request.headers.get("content-type", "").split(";", 1)[0] != "application/x-www-form-urlencoded":
        return None
    try:
        fields = parse_qs((await request.body()).decode("utf-8"), strict_parsing=True)
    except (UnicodeDecodeError, ValueError):
        return None
    return {key: values[0] for key, values in fields.items() if len(values) == 1}


def _guided_fact(stream: TelemetryStream, fields: dict[str, str]) -> dict:
    workflow = _workflow(stream)
    if workflow is None:
        raise AcquisitionError("This update is not available as a guided capture.")
    valid_at = _human_date(fields["valid_at"])
    value = float(fields["value"])
    payload = {"entity_id": stream.subject_id, workflow["event_field"]: value}
    if workflow["event_kind"] == "finance.position.updated":
        payload["valuation_date"] = valid_at
    return {
        "kind": workflow["observation_kind"], "subject_id": stream.subject_id,
        "valid_at": valid_at, "value": value,
        "canonical_event": {"kind": workflow["event_kind"], "payload": payload},
    }


@router.post("/operations/capture")
async def capture(request: Request):
    email = _email(request)
    if email is None:
        return RedirectResponse("/login", status_code=303)
    fields = await _body(request)
    cfg = webauth.load_config()
    if fields and "contract_id" in fields:
        registry = _contracts(request)
        contract = registry.get(fields["contract_id"])
        if contract is None or not webauth.verify_csrf(fields.get("csrf"), email, cfg, _CONTRACT_PURPOSE):
            return HTMLResponse("Forbidden", status_code=403)
        system_fields = {"csrf", "contract_id", "stream_id"}
        contract_fields = {field.name for field in contract.schema}
        required_fields = {field.name for field in contract.schema if field.required}
        if (set(fields) - (system_fields | contract_fields) or
                not system_fields <= set(fields) or not required_fields <= set(fields)):
            return HTMLResponse("Forbidden", status_code=403)
        try:
            console = _console(request)
            household = _household(console)
            if household is None:
                return HTMLResponse("Not found", status_code=404)
            capture_values = {name: fields.get(name, "") for name in contract_fields}
            _capture_service(request, console).propose(
                contract.identifier, fields["stream_id"], capture_values,
                actor=email, channel="manual")
        except LookupError:
            return HTMLResponse("Not found", status_code=404)
        except (KeyError, TypeError, ValueError, AcquisitionError, json.JSONDecodeError) as exc:
            return HTMLResponse("Capture refused: " + html.escape(str(exc)), status_code=400)
        return RedirectResponse("/acquisition/inbox", status_code=303)
    common = {"csrf", "mode", "stream_id", "value", "valid_at", "external_ref"}
    technical = common | {"subject_id", "kind", "event_kind", "event_payload"}
    if (not fields or set(fields) not in (common, technical) or
            fields.get("mode") not in {"guided", "technical"} or
            not webauth.verify_csrf(fields.get("csrf"), email, cfg, _PURPOSE)):
        return HTMLResponse("Forbidden", status_code=403)
    try:
        console = _console(request)
        streams = TelemetryStreamRegistry(console.log)
        active = {stream.id: stream for stream in streams.active_manual_streams(_household(console) or "")}
        stream = active.get(fields["stream_id"])
        if stream is None:
            return HTMLResponse("Not found", status_code=404)
        if fields["mode"] == "guided":
            fact = _guided_fact(stream, fields)
        else:
            payload = json.loads(fields["event_payload"])
            if not isinstance(payload, dict):
                raise ValueError("Canonical payload must be an object.")
            payload.setdefault("entity_id", fields["subject_id"])
            fact = {
                "kind": fields["kind"], "subject_id": fields["subject_id"],
                "valid_at": float(fields["valid_at"]), "value": float(fields["value"]),
                "canonical_event": {"kind": fields["event_kind"], "payload": payload},
            }
        _capture_service(request, console).propose_fact(
            _household(console) or "", stream.id, fact, actor=email, channel="manual",
            external_ref=fields.get("external_ref") or None)
    except LookupError:
        return HTMLResponse("Not found", status_code=404)
    except (KeyError, TypeError, ValueError, AcquisitionError, json.JSONDecodeError) as exc:
        return HTMLResponse("Capture refused: " + html.escape(str(exc)), status_code=400)
    return RedirectResponse("/acquisition/inbox", status_code=303)

"""Privileged MCP adapter for Foundry's governed financial-resource surface."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from foundry.application.mcp_context import (
    McpPrincipal, authenticated_principal_from_environment, query_for_mcp_principal,
)
from foundry.application.mcp_writes import (
    McpBalanceCapture, McpClientSafeDenied, McpFinancialResourceWrites,
    McpPensionProviderProjectionCapture, McpWriteDenied,
)
from foundry.application.mission_assumptions import MissionAssumptionError, MissionAssumptionService
from foundry.application.pension_mission import PensionMissionQueryError, PensionMissionQueryService
from foundry.application.pension_timing import PensionTimingError, PensionTimingService
from foundry.application.resources import FinancialResourceQuery, ResourceNotFound


_GENERIC_OBSERVATION_REFUSAL = "financial observation proposal refused"


def _observation_refusal_message(exc: McpWriteDenied) -> str:
    """Return only reviewed capture-contract denial text to MCP clients."""
    if isinstance(exc, McpClientSafeDenied):
        return str(exc)
    return _GENERIC_OBSERVATION_REFUSAL


def create_mcp_server(query: FinancialResourceQuery | None = None,
                      principal: McpPrincipal | None = None,
                      streamable_http_path: str = "/mcp", *, host: str = "127.0.0.1",
                      transport_security=None, auth=None, auth_server_provider=None) -> FastMCP:
    """Build the governed MCP surface; no transport code knows event shapes."""
    active_principal = principal or authenticated_principal_from_environment()
    query = query or query_for_mcp_principal(active_principal)
    balance_capture = McpBalanceCapture(
        query.log, active_principal.email, active_principal.household_id,
        active_principal.client, active_principal.witness_model)
    resource_writes = McpFinancialResourceWrites(
        query.log, active_principal.email, active_principal.household_id,
        active_principal.client, active_principal.witness_model)
    pension_projection_capture = McpPensionProviderProjectionCapture(
        query.log, active_principal.email, active_principal.household_id,
        active_principal.client, active_principal.witness_model)
    mission_assumptions = MissionAssumptionService(query.log)
    pension_mission = PensionMissionQueryService(query.log, active_principal.household_id)
    pension_timing = PensionTimingService(query.log, active_principal.household_id)
    server = FastMCP("Foundry", instructions="Governed household finance and Mission access.",
                     streamable_http_path=streamable_http_path, host=host,
                     transport_security=transport_security, auth=auth,
                     auth_server_provider=auth_server_provider)

    @server.tool()
    def inspect_pension_independence(mission_id: str | None = None,
                                    as_of: str | None = None) -> dict:
        """Inspect the authorised Pension Independence Mission and its exact blockers."""
        try:
            return pension_mission.inspect(mission_id, as_of)
        except PensionMissionQueryError as exc:
            raise ValueError(str(exc)) from exc

    @server.tool()
    def explain_pension_independence_planning_point(
            mission_id: str | None = None, as_of: str | None = None) -> dict:
        """Explain this Mission's canonical planning point and provider-date compatibility."""
        try:
            return pension_mission.explain_planning_point(mission_id, as_of)
        except PensionMissionQueryError as exc:
            raise ValueError(str(exc)) from exc

    @server.tool()
    def get_current_pension_value(mission_id: str | None = None,
                                  as_of: str | None = None) -> dict:
        """Return canonical aggregated pension wealth; clients need not replay history."""
        try:
            return pension_mission.current_value(mission_id, as_of)
        except PensionMissionQueryError as exc:
            raise ValueError(str(exc)) from exc

    @server.tool()
    def evaluate_pension_independence(mission_id: str | None = None,
                                      as_of: str | None = None) -> dict:
        """Evaluate Pension Independence through Foundry's canonical Mission assessor."""
        try:
            return pension_mission.evaluate(mission_id, as_of)
        except PensionMissionQueryError as exc:
            raise ValueError(str(exc)) from exc

    @server.tool()
    def propose_person_date_of_birth(person_id: str, date_of_birth: str) -> dict:
        """Propose one authorised Person DOB declaration; this never writes identity state."""
        try:
            return {"state": "proposed", "requires_execution": True,
                    **pension_timing.propose_person_date_of_birth(
                        person_id=person_id, date_of_birth=date_of_birth,
                        principal=active_principal.email)}
        except PensionTimingError as exc:
            raise ValueError(str(exc)) from exc

    @server.tool()
    def declare_person_date_of_birth(person_id: str, date_of_birth: str,
                                     proposal_id: str, command_id: str) -> dict:
        """Execute only the exact authorised DOB proposal, idempotently."""
        try:
            return pension_timing.declare_person_date_of_birth(
                person_id=person_id, date_of_birth=date_of_birth, proposal_id=proposal_id,
                command_id=command_id, principal=active_principal.email)
        except PensionTimingError as exc:
            raise ValueError(str(exc)) from exc

    @server.tool()
    def propose_state_pension_age(person_id: str, state_pension_age: float,
                                  effective_at: str, source: str, lineage: str,
                                  confidence: float) -> dict:
        """Propose one authorised person-scoped State Pension age declaration."""
        try:
            return {"state": "proposed", "requires_execution": True,
                    **pension_timing.propose_state_pension_age(
                        person_id=person_id, state_pension_age=state_pension_age,
                        effective_at=effective_at, source=source, lineage=lineage,
                        confidence=confidence, principal=active_principal.email)}
        except PensionTimingError as exc:
            raise ValueError(str(exc)) from exc

    @server.tool()
    def declare_state_pension_age(person_id: str, state_pension_age: float,
                                  effective_at: str, source: str, lineage: str,
                                  confidence: float, proposal_id: str,
                                  command_id: str) -> dict:
        """Execute only the exact authorised State Pension age proposal, idempotently."""
        try:
            return pension_timing.declare_state_pension_age(
                person_id=person_id, state_pension_age=state_pension_age,
                effective_at=effective_at, source=source, lineage=lineage,
                confidence=confidence, proposal_id=proposal_id, command_id=command_id,
                principal=active_principal.email)
        except PensionTimingError as exc:
            raise ValueError(str(exc)) from exc

    @server.tool()
    def get_mission_assumption_readiness(mission_id: str) -> dict:
        """Explain the authorised mission's Assumption Set readiness."""
        try:
            return mission_assumptions.readiness(mission_id, active_principal.household_id).as_dict()
        except MissionAssumptionError as exc:
            raise ValueError("mission assumption readiness unavailable") from exc

    @server.tool()
    def propose_mission_assumption_set(mission_id: str, assumptions: dict) -> dict:
        """Propose an exact typed Assumption Set payload; this never activates it."""
        try:
            result = mission_assumptions.propose(
                mission_id=mission_id, household_id=active_principal.household_id,
                assumptions=assumptions, principal=active_principal.email)
            return {"operation": "declare_mission_assumption_set", "state": "proposed",
                    **result, "requires_execution": True}
        except MissionAssumptionError as exc:
            raise ValueError("mission assumption proposal refused") from exc

    @server.tool()
    def execute_mission_assumption_set(mission_id: str, assumptions: dict,
                                       proposal_id: str, command_id: str) -> dict:
        """Execute only the matching prior typed proposal, idempotently."""
        try:
            return mission_assumptions.execute(
                proposal_id=proposal_id, mission_id=mission_id,
                household_id=active_principal.household_id, assumptions=assumptions,
                principal=active_principal.email, command_id=command_id)
        except MissionAssumptionError as exc:
            raise ValueError("mission assumption execution refused") from exc

    @server.tool()
    def list_financial_resources() -> dict:
        """List registered financial resources visible to the authenticated household."""
        resources = query.list_financial_resources()
        for resource in resources:
            resource["capture_availability"] = query.capture_availability(resource["id"])
        return {"resources": resources}

    @server.tool()
    def get_financial_resource(resource_id: str) -> dict:
        """Return one registered financial resource and its canonical provenance references."""
        try:
            result = query.get_financial_resource(resource_id)
            result["capture_availability"] = query.capture_availability(resource_id)
            return result
        except ResourceNotFound as exc:
            raise ValueError("unknown financial resource") from exc

    @server.tool()
    def create_financial_resource(resource_type: str, currency: str, owner: str | None = None,
                                  name: str | None = None, provider: str | None = None,
                                  owners: list[str] | None = None,
                                  liquidity_classification: str | None = None,
                                  projection_authority: str | None = None) -> dict:
        """Propose creation; this tool never mutates canonical financial state.

        `projection_authority` ("provider_managed" or "foundry_modelled")
        is pension-only and must come from the household's explicit
        statement — never from the provider name or any other string."""
        receipt = resource_writes.propose_create(
            resource_type=resource_type, currency=currency, owner=owner, owners=owners,
            name=name, provider=provider, liquidity_classification=liquidity_classification,
            projection_authority=projection_authority)
        return {"operation": "create_financial_resource", "state": "proposed",
                "proposal_id": receipt.proposal_id, "requires_execution": True,
                "resource_type": resource_type, "currency": currency,
                "owner": owner, "owners": owners, "name": name, "provider": provider,
                "liquidity_classification": liquidity_classification,
                "projection_authority": projection_authority}

    @server.tool()
    def execute_create_financial_resource(resource_type: str, currency: str, command_id: str,
                                          proposal_id: str, owner: str | None = None,
                                          name: str | None = None, provider: str | None = None,
                                          owners: list[str] | None = None,
                                          liquidity_classification: str | None = None,
                                          projection_authority: str | None = None) -> dict:
        """Execute a previously proposed creation by its proposal receipt."""
        try:
            return resource_writes.create(resource_type=resource_type, currency=currency,
                                          owner=owner, owners=owners, command_id=command_id,
                                          proposal_id=proposal_id,
                                          name=name, provider=provider,
                                          liquidity_classification=liquidity_classification,
                                          projection_authority=projection_authority)
        except McpWriteDenied as exc:
            raise ValueError("financial resource creation refused") from exc

    @server.tool()
    def declare_pension_projection_authority(resource_id: str, projection_authority: str,
                                             reason: str,
                                             provider_name: str | None = None) -> dict:
        """Propose which authority may forecast an existing pension.

        "provider_managed" means the provider's own illustration is the
        only admissible Expected Outcome: while none is current, the
        Mission reports no Expected Outcome rather than substituting
        Foundry's internal forecast. Declare it only on the household's
        explicit instruction."""
        receipt = resource_writes.propose_pension_projection_authority(
            resource_id=resource_id, projection_authority=projection_authority,
            reason=reason, provider_name=provider_name)
        return {"operation": "declare_pension_projection_authority", "state": "proposed",
                "proposal_id": receipt.proposal_id, "requires_execution": True,
                "resource_id": resource_id, "projection_authority": projection_authority,
                "provider_name": provider_name, "reason": reason}

    @server.tool()
    def execute_declare_pension_projection_authority(
            resource_id: str, projection_authority: str, reason: str, command_id: str,
            proposal_id: str, provider_name: str | None = None) -> dict:
        """Execute a previously proposed projection-authority declaration."""
        try:
            return resource_writes.declare_pension_projection_authority(
                resource_id=resource_id, projection_authority=projection_authority,
                reason=reason, provider_name=provider_name,
                command_id=command_id, proposal_id=proposal_id)
        except McpWriteDenied as exc:
            raise ValueError("pension projection authority declaration refused") from exc

    @server.tool()
    def update_financial_resource(resource_id: str, name: str, reason: str = "metadata update") -> dict:
        receipt = resource_writes.propose_update(resource_id=resource_id, name=name, reason=reason)
        return {"operation": "update_financial_resource", "state": "proposed",
                "proposal_id": receipt.proposal_id, "resource_id": resource_id,
                "name": name, "reason": reason, "requires_execution": True}

    @server.tool()
    def execute_update_financial_resource(resource_id: str, name: str, command_id: str,
                                          proposal_id: str,
                                  reason: str = "metadata update") -> dict:
        """Execute a previously proposed resource rename."""
        try:
            return resource_writes.update(resource_id=resource_id, name=name,
                                          command_id=command_id, reason=reason, proposal_id=proposal_id)
        except McpWriteDenied as exc:
            raise ValueError("financial resource update refused") from exc

    @server.tool()
    def close_financial_resource(resource_id: str, reason: str = "closed") -> dict:
        """Propose closure without changing the canonical resource."""
        receipt = resource_writes.propose_close(resource_id=resource_id, reason=reason)
        return {"operation": "close_financial_resource", "state": "proposed",
                "proposal_id": receipt.proposal_id, "resource_id": resource_id,
                "reason": reason, "requires_execution": True}

    @server.tool()
    def execute_close_financial_resource(resource_id: str, command_id: str,
                                         proposal_id: str, reason: str = "closed") -> dict:
        """Execute a previously proposed resource closure."""
        try:
            return resource_writes.close(resource_id=resource_id, command_id=command_id,
                                         reason=reason, proposal_id=proposal_id)
        except McpWriteDenied as exc:
            raise ValueError("financial resource closure refused") from exc

    @server.tool()
    def explain_capture_availability(resource_id: str) -> dict:
        """Describe existing governed capture operations supported by one resource."""
        try:
            return query.capture_availability(resource_id)
        except ResourceNotFound as exc:
            raise ValueError("unknown financial resource") from exc

    @server.tool()
    def record_account_balance(resource_id: str, amount: float, currency: str, as_at: str,
                               request_id: str, evidence_reference: str | None = None) -> dict:
        """Create a reviewable governed balance-capture proposal for an authorised account."""
        try:
            receipt = balance_capture.record_account_balance(
                resource_id, amount, currency, as_at, request_id, evidence_reference)
        except (McpWriteDenied, ValueError) as exc:
            raise ValueError("account balance capture refused") from exc
        return {"proposal_id": receipt.proposal_id, "envelope_id": receipt.envelope_id,
                "state": "pending"}

    @server.tool()
    def propose_financial_observation(resource_id: str, capture_contract_id: str,
                                      amount: float, currency: str, as_at: str,
                                      command_id: str, evidence_reference: str | None = None,
                                      valuation_basis: str | None = None,
                                      source: str | None = None) -> dict:
        """Propose one available contract-backed observation for human confirmation.

        This stages a pending acquisition proposal only. Canonical confirmation
        remains on Foundry's acquisition review surface.
        """
        try:
            receipt = balance_capture.propose_financial_observation(
                resource_id=resource_id, capture_contract_id=capture_contract_id,
                amount=amount, currency=currency, as_at=as_at, command_id=command_id,
                evidence_reference=evidence_reference, valuation_basis=valuation_basis,
                source=source)
        except McpWriteDenied as exc:
            raise ValueError(_observation_refusal_message(exc)) from exc
        return {
            "operation": "propose_financial_observation", "state": "pending",
            "proposal_id": receipt.proposal_id, "envelope_id": receipt.envelope_id,
            "resource_id": receipt.resource_id, "capture_contract_id": receipt.contract_id,
            "capture_contract_version": receipt.contract_version,
            "command_id": receipt.command_id, "summary": receipt.review_summary,
            "requires_confirmation": True,
            "confirmation_surface": "Foundry acquisition review",
        }

    @server.tool()
    def propose_pension_provider_projection(
            resource_id: str, provider: str, observed_at: float, currency: str,
            retirement_age: float | None, retirement_at: float | None,
            fund_low: float, fund_medium: float, fund_high: float,
            income_low: float, income_medium: float, income_high: float,
            growth_low_percent: float, growth_medium_percent: float, growth_high_percent: float,
            income_basis: str, source: str, lineage: str) -> dict:
        """Propose one complete provider-issued pension illustration; no state is changed."""
        values = {
            "provider": provider, "observed_at": observed_at, "currency": currency,
            "retirement_age": retirement_age, "retirement_at": retirement_at,
            "fund_low": fund_low, "fund_medium": fund_medium, "fund_high": fund_high,
            "income_low": income_low, "income_medium": income_medium, "income_high": income_high,
            "growth_low_percent": growth_low_percent,
            "growth_medium_percent": growth_medium_percent,
            "growth_high_percent": growth_high_percent,
            "income_basis": income_basis, "source": source, "lineage": lineage,
        }
        try:
            receipt = pension_projection_capture.propose(resource_id=resource_id, values=values)
        except McpWriteDenied as exc:
            raise ValueError("provider projection proposal refused") from exc
        return {"operation": "record_pension_provider_projection", "state": "proposed",
                "proposal_id": receipt.proposal_id, "resource_id": receipt.resource_id,
                "summary": receipt.summary, "requires_execution": True}

    @server.tool()
    def execute_pension_provider_projection(
            resource_id: str, proposal_id: str, command_id: str, provider: str,
            observed_at: float, currency: str, retirement_age: float | None,
            retirement_at: float | None, fund_low: float, fund_medium: float, fund_high: float,
            income_low: float, income_medium: float, income_high: float,
            growth_low_percent: float, growth_medium_percent: float, growth_high_percent: float,
            income_basis: str, source: str, lineage: str) -> dict:
        """Record only the exact provider illustration represented by a proposal receipt."""
        values = {
            "provider": provider, "observed_at": observed_at, "currency": currency,
            "retirement_age": retirement_age, "retirement_at": retirement_at,
            "fund_low": fund_low, "fund_medium": fund_medium, "fund_high": fund_high,
            "income_low": income_low, "income_medium": income_medium, "income_high": income_high,
            "growth_low_percent": growth_low_percent,
            "growth_medium_percent": growth_medium_percent,
            "growth_high_percent": growth_high_percent,
            "income_basis": income_basis, "source": source, "lineage": lineage,
        }
        try:
            return pension_projection_capture.execute(
                resource_id=resource_id, values=values, proposal_id=proposal_id,
                command_id=command_id)
        except McpWriteDenied as exc:
            raise ValueError("provider projection execution refused") from exc

    return server


def main() -> None:
    create_mcp_server().run(transport="stdio")


if __name__ == "__main__":
    main()

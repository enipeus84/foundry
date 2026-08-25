"""Provider-managed pensions are declared, never inferred.

Foundry must be able to answer "does this pension require provider
projection evidence?" from the resource itself, before any evidence is
read. Without that truth a provider-managed pension whose illustration
is missing silently falls back to Foundry's internal forecast — the
unsafe ambiguity this coverage exists to prevent.
"""

import pytest

from foundry.application.mcp_writes import McpFinancialResourceWrites, McpWriteDenied
from foundry.application.resources import (
    FinancialResourceCommandService, FinancialResourceQuery, ResourceCommandDenied,
)
from foundry.core.entities import (
    EntityProjection, declare_party, join_household, update_party,
)
from foundry.core.principal_authority import grant_principal_household_authority
from foundry.errors import VocabularyError
from foundry.eventlog import EventLog
from foundry.finance import entities as fin
from foundry.finance.entities import FinanceEntityProjection
from foundry.finance.pension_projection import record_pension_provider_projection

from test_pension_assessment import (
    PENSION_FIXTURE_AS_OF, _assessment, _record_provider, _seed,
)


PRINCIPAL = "mcp@example.com"


def _declare_provider_managed(log, account_id, provider_name="Aviva"):
    return fin.declare_pension_projection_authority(
        log, account_id, projection_authority="provider_managed",
        reason="household confirmed the scheme is managed by its provider",
        provider_name=provider_name)


def _world(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    household = declare_party(log, "household")
    chris = declare_party(log, "person")
    update_party(log, chris.id, {"name": "Chris"}, "test identity")
    join_household(log, chris.id, household.id)
    grant_principal_household_authority(log, PRINCIPAL, household.id, actor="test")
    writes = McpFinancialResourceWrites(log, PRINCIPAL, household.id, "claude-code", "gpt-test")
    return log, household, writes


# ------------------------------------------------ assessment semantics

def test_provider_managed_pension_with_valid_projection_uses_the_provider(tmp_path):
    log, household = _seed(tmp_path)
    planning_at = _assessment(log, household).forecast[-1].at
    _declare_provider_managed(log, household.alex_pension_id)
    _declare_provider_managed(log, household.sam_pension_id)
    first = _record_provider(log, household.alex_pension_id, planning_at, 604_000)
    second = _record_provider(log, household.sam_pension_id, planning_at, 401_000)

    assessment = _assessment(log, household)
    expected = next(item for item in assessment.telemetry if item.label == "EXPECTED OUTCOME")

    assert assessment.status != "unavailable"
    assert expected.result.value == 1_005_000
    assert set(expected.result.evidence_references) == {first.event_id, second.event_id}
    assert any("not a Foundry forecast" in value for value in assessment.limitations)


def test_provider_managed_pension_without_any_projection_withholds_the_outcome(tmp_path):
    log, household = _seed(tmp_path)
    internal = _assessment(log, household)
    assert internal.status != "unavailable"  # the unsafe fallback, before declaration

    _declare_provider_managed(log, household.alex_pension_id)
    assessment = _assessment(log, household)

    assert assessment.status == "none"
    assert assessment.completeness == "partial"
    assert any("provider projection required" in value for value in assessment.limitations)
    # `forecast` is empty when partial, so assert the internal figure is
    # absent from every stated number rather than from an empty tuple.
    assert assessment.forecast == ()
    assert internal.forecast[-1].base not in {
        item.result.value for item in assessment.telemetry}


def test_provider_managed_pension_with_stale_projection_fails_closed(tmp_path):
    log, household = _seed(tmp_path)
    planning_at = _assessment(log, household).forecast[-1].at
    _declare_provider_managed(log, household.alex_pension_id)
    _declare_provider_managed(log, household.sam_pension_id)
    for account_id in (household.alex_pension_id, household.sam_pension_id):
        record_pension_provider_projection(
            log, account_id, provider="Aviva", currency="GBP",
            observed_at=PENSION_FIXTURE_AS_OF - 900 * 86_400, retirement_at=planning_at,
            fund_low=500_000, fund_medium=604_000, fund_high=700_000,
            income_low=20_000, income_medium=30_000, income_high=40_000,
            growth_low_percent=1.0, growth_medium_percent=2.0, growth_high_percent=3.0,
            income_basis="Provider illustration", source="Aviva statement",
            lineage="household supplied statement")

    assessment = _assessment(log, household)

    assert assessment.status == "none"
    assert assessment.completeness == "partial"
    assert any("provider projection required" in value for value in assessment.limitations)


def test_unclassified_pension_without_projection_keeps_the_foundry_forecast(tmp_path):
    log, household = _seed(tmp_path)

    assessment = _assessment(log, household)

    assert assessment.status != "unavailable"
    assert assessment.forecast[-1].base == pytest.approx(785_000.0, abs=1.0)
    assert not any("provider projection" in value for value in assessment.limitations)


def test_mixed_portfolio_cannot_substitute_foundry_modelling_for_the_missing_member(tmp_path):
    log, household = _seed(tmp_path)
    planning_at = _assessment(log, household).forecast[-1].at
    _declare_provider_managed(log, household.alex_pension_id)
    _record_provider(log, household.sam_pension_id, planning_at, 401_000)

    assessment = _assessment(log, household)

    assert assessment.status == "none"
    assert assessment.completeness == "partial"
    assert any("every included pension" in value for value in assessment.limitations)


def test_assessment_without_a_projection_view_still_fails_closed(tmp_path):
    """A caller that omits provider evidence entirely must not be a loophole."""
    from foundry.core.metrics import MetricRegistry
    from foundry.core.mission_assessment import MissionAssessmentRequest
    from foundry.core.scope import Subject
    from foundry.finance.metrics import FinanceMetricProvider
    from foundry.finance.pension_assessment import POLICY_ID, PensionIndependenceAssessor
    from foundry.finance.pension_evidence import PensionEvidenceProjection
    from foundry.finance.pension_metrics import FinancePensionMetricProvider

    log, household = _seed(tmp_path)
    _declare_provider_managed(log, household.alex_pension_id)
    core, finance = EntityProjection(log), FinanceEntityProjection(log)
    evidence = PensionEvidenceProjection(log)
    metrics = MetricRegistry()
    metrics.register(FinanceMetricProvider(finance, core))
    metrics.register(FinancePensionMetricProvider(finance, core, evidence))
    assessor = PensionIndependenceAssessor(metrics, finance, core, evidence)
    mission = next(item for item in core.missions.values()
                   if item.assessment_policy_id == POLICY_ID)

    assessment = assessor.assess(MissionAssessmentRequest(
        mission.id, POLICY_ID, Subject("party", household.household_id), household.as_of))

    assert assessment.status == "none"
    assert assessment.completeness == "partial"


# ------------------------------------------------------ canonical model

def test_classification_survives_persistence_and_reload(tmp_path):
    log, household = _seed(tmp_path)
    _declare_provider_managed(log, household.alex_pension_id)

    reloaded = FinanceEntityProjection(EventLog(tmp_path / "events.jsonl"))
    account = reloaded.accounts[household.alex_pension_id]

    assert account.projection_authority == "provider_managed"
    assert account.provider_name == "Aviva"
    assert reloaded.accounts[household.sam_pension_id].projection_authority is None
    incremental = FinanceEntityProjection(log)
    assert incremental.accounts == reloaded.accounts


def test_declaration_is_recorded_as_provenance_not_as_evidence(tmp_path):
    log, household = _seed(tmp_path)
    event = _declare_provider_managed(log, household.alex_pension_id)

    assert event["kind"] == "finance.account.updated"
    assert event["payload"]["reason"]
    assert event["id"] in FinanceEntityProjection(log).accounts[
        household.alex_pension_id].history
    assert not any(item["kind"].startswith("finance.pension_provider_projection")
                   for item in log.events())


def test_projection_authority_is_a_controlled_vocabulary_and_pension_only(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    with pytest.raises(VocabularyError):
        fin.declare_account(log, "pension", "GBP", projection_authority="aviva_manages_it")
    with pytest.raises(ValueError):
        fin.declare_account(log, "savings", "GBP", projection_authority="provider_managed")
    with pytest.raises(ValueError):
        fin.declare_pension_projection_authority(
            log, "pension-1", projection_authority="provider_managed", reason="  ")
    assert not list(log.events())


def test_provider_like_names_never_confer_provider_management(tmp_path):
    log, household = _seed(tmp_path)
    named = fin.declare_account(log, "pension", "GBP", name="Aviva",
                                provider_name="Aviva")

    assert named.projection_authority is None
    assert FinanceEntityProjection(log).accounts[
        household.alex_pension_id].projection_authority is None
    assert _assessment(log, household).status != "unavailable"


# ----------------------------------------------- governed write paths

def test_creation_can_declare_provider_management_through_the_canonical_command(tmp_path):
    log, household, writes = _world(tmp_path)
    proposal = writes.propose_create(resource_type="pension", currency="GBP", provider="Aviva",
                                     owner="Chris", projection_authority="provider_managed")
    resource = writes.create(resource_type="pension", currency="GBP", provider="Aviva",
                             owner="Chris", projection_authority="provider_managed",
                             command_id="cmd-1", proposal_id=proposal.proposal_id)

    assert resource["projection_authority"] == "provider_managed"
    assert resource["provider_name"] == "Aviva"
    with pytest.raises(McpWriteDenied):
        stale = writes.propose_create(resource_type="isa", currency="GBP", name="AJ Bell",
                                      owner="Chris", projection_authority="provider_managed")
        writes.create(resource_type="isa", currency="GBP", name="AJ Bell", owner="Chris",
                      projection_authority="provider_managed", command_id="cmd-2",
                      proposal_id=stale.proposal_id)


def test_existing_pension_is_declared_through_a_proposed_and_confirmed_command(tmp_path):
    log, household, writes = _world(tmp_path)
    proposal = writes.propose_create(resource_type="pension", currency="GBP", provider="Aviva",
                                     owner="Chris")
    resource = writes.create(resource_type="pension", currency="GBP", provider="Aviva",
                             owner="Chris", command_id="cmd-1", proposal_id=proposal.proposal_id)
    assert resource["projection_authority"] is None

    with pytest.raises(McpWriteDenied):  # confirmation boundary holds
        writes.declare_pension_projection_authority(
            resource_id=resource["id"], projection_authority="provider_managed",
            reason="household confirmed", command_id="cmd-2")

    receipt = writes.propose_pension_projection_authority(
        resource_id=resource["id"], projection_authority="provider_managed",
        reason="household confirmed", provider_name="Aviva")
    declared = writes.declare_pension_projection_authority(
        resource_id=resource["id"], projection_authority="provider_managed",
        reason="household confirmed", provider_name="Aviva",
        command_id="cmd-2", proposal_id=receipt.proposal_id)
    replay = writes.declare_pension_projection_authority(
        resource_id=resource["id"], projection_authority="provider_managed",
        reason="household confirmed", provider_name="Aviva",
        command_id="cmd-2", proposal_id=receipt.proposal_id)

    assert declared["projection_authority"] == "provider_managed"
    assert replay == declared
    assert sum(event["kind"] == "finance.account.updated" for event in log.events()) == 1


def test_declaration_is_household_isolated_and_pension_only(tmp_path):
    log, household, writes = _world(tmp_path)
    proposal = writes.propose_create(resource_type="pension", currency="GBP", provider="Aviva",
                                     owner="Chris")
    pension = writes.create(resource_type="pension", currency="GBP", provider="Aviva",
                            owner="Chris", command_id="cmd-1", proposal_id=proposal.proposal_id)
    savings_proposal = writes.propose_create(resource_type="savings", currency="GBP",
                                             name="Rainy day", owner="Chris")
    savings = writes.create(resource_type="savings", currency="GBP", name="Rainy day",
                            owner="Chris", command_id="cmd-2",
                            proposal_id=savings_proposal.proposal_id)

    outsider = declare_party(log, "household")
    service = FinancialResourceCommandService(log)
    with pytest.raises(Exception) as isolation:
        service.declare_pension_projection_authority(
            household_id=outsider.id, resource_id=pension["id"],
            projection_authority="provider_managed", reason="cross-household attempt",
            actor="test", require_authority=False)
    assert isolation.type.__name__ in {"ResourceNotFound", "ResourceCommandDenied"}

    with pytest.raises(ResourceCommandDenied):
        service.declare_pension_projection_authority(
            household_id=household.id, resource_id=savings["id"],
            projection_authority="provider_managed", reason="not a pension",
            actor="test", require_authority=False)
    assert FinanceEntityProjection(log).accounts[pension["id"]].projection_authority is None


def test_read_surface_exposes_the_classification_for_pensions_only(tmp_path):
    log, household, writes = _world(tmp_path)
    proposal = writes.propose_create(resource_type="pension", currency="GBP", provider="Aviva",
                                     owner="Chris", projection_authority="provider_managed")
    pension = writes.create(resource_type="pension", currency="GBP", provider="Aviva",
                            owner="Chris", projection_authority="provider_managed",
                            command_id="cmd-1", proposal_id=proposal.proposal_id)
    cash_proposal = writes.propose_create(resource_type="savings", currency="GBP",
                                          name="Rainy day", owner="Chris")
    writes.create(resource_type="savings", currency="GBP", name="Rainy day", owner="Chris",
                  command_id="cmd-2", proposal_id=cash_proposal.proposal_id)

    listed = FinancialResourceQuery(log, household.id).list_financial_resources()
    by_id = {item["id"]: item for item in listed}

    assert by_id[pension["id"]]["projection_authority"] == "provider_managed"
    assert by_id[pension["id"]]["provider_name"] == "Aviva"
    assert all("projection_authority" not in item for item in listed
               if item["resource_type"] != "pension")


# ------------------------------- omission gap (SAFE remediation)

def _unvalued_provider_pension(log, household, *, authority="provider_managed"):
    """An owned pension Foundry cannot value — the shape a fully
    provider-managed scheme takes when no Foundry valuation exists."""
    owner = next(link.target for link in FinanceEntityProjection(log)
                 .accounts[household.alex_pension_id].ownership)
    account = fin.declare_account(log, "pension", "GBP", name="Provider scheme",
                                  projection_authority=authority)
    fin.link_ownership(log, "account", account.id, "owner", owner)
    return account


def test_unvalued_provider_managed_pension_cannot_be_dropped_from_the_assessment(tmp_path):
    """The exact SAFE finding: a provider-managed pension with no Foundry
    valuation was removed by the projectability filter before the
    authority check ran, letting an Expected Outcome be stated as though
    the pension did not exist."""
    log, household = _seed(tmp_path)
    projectable = _assessment(log, household)
    assert projectable.status != "unavailable"  # assessor is otherwise capable

    ghost = _unvalued_provider_pension(log, household)
    assessment = _assessment(log, household)

    assert FinanceEntityProjection(log).accounts[ghost.id].projection_authority == "provider_managed"
    assert not FinanceEntityProjection(log).valuations_of(ghost.id)
    assert assessment.status == "none"
    assert assessment.completeness == "partial"
    assert any("provider projection required" in value for value in assessment.limitations)
    assert projectable.forecast[-1].base not in {
        item.result.value for item in assessment.telemetry}


def test_unvalued_provider_managed_pension_with_stale_projection_fails_closed(tmp_path):
    log, household = _seed(tmp_path)
    planning_at = _assessment(log, household).forecast[-1].at
    ghost = _unvalued_provider_pension(log, household)
    record_pension_provider_projection(
        log, ghost.id, provider="Aviva", currency="GBP",
        observed_at=PENSION_FIXTURE_AS_OF - 900 * 86_400, retirement_at=planning_at,
        fund_low=90_000, fund_medium=100_000, fund_high=110_000,
        income_low=1_000, income_medium=2_000, income_high=3_000,
        growth_low_percent=1.0, growth_medium_percent=2.0, growth_high_percent=3.0,
        income_basis="Provider illustration", source="Aviva statement",
        lineage="household supplied statement")

    assessment = _assessment(log, household)

    assert assessment.status == "none"
    assert assessment.completeness == "partial"
    assert any("provider projection required" in value for value in assessment.limitations)


def test_unvalued_provider_managed_pension_is_honoured_when_its_projection_is_valid(tmp_path):
    """Requiring the illustration and then ignoring it would be incoherent:
    once supplied, the provider's numbers are the pension's economic truth
    even though Foundry holds no valuation for it."""
    log, household = _seed(tmp_path)
    planning_at = _assessment(log, household).forecast[-1].at
    ghost = _unvalued_provider_pension(log, household)
    _record_provider(log, household.alex_pension_id, planning_at, 604_000)
    _record_provider(log, household.sam_pension_id, planning_at, 401_000)
    ghost_record = _record_provider(log, ghost.id, planning_at, 100_000)

    assessment = _assessment(log, household)
    expected = next(item for item in assessment.telemetry if item.label == "EXPECTED OUTCOME")

    assert assessment.status != "unavailable"
    assert expected.result.value == 1_105_000
    assert ghost_record.event_id in set(expected.result.evidence_references)


def test_unvalued_legacy_pension_preserves_existing_behaviour(tmp_path):
    """An unclassified pension Foundry cannot value stays silently outside
    the projection, exactly as before this remediation."""
    log, household = _seed(tmp_path)
    baseline = _assessment(log, household)
    _unvalued_provider_pension(log, household, authority=None)

    assessment = _assessment(log, household)

    assert assessment.status == baseline.status
    assert assessment.forecast[-1].base == baseline.forecast[-1].base
    assert not any("provider projection" in value for value in assessment.limitations)


def test_explicitly_foundry_modelled_pension_raises_no_provider_requirement(tmp_path):
    """The positive branch of the vocabulary, proven rather than inferred
    from a legacy `None`."""
    log, household = _seed(tmp_path)
    baseline = _assessment(log, household)
    fin.declare_pension_projection_authority(
        log, household.alex_pension_id, projection_authority="foundry_modelled",
        reason="household confirmed Foundry models this scheme")
    fin.declare_pension_projection_authority(
        log, household.sam_pension_id, projection_authority="foundry_modelled",
        reason="household confirmed Foundry models this scheme")

    assessment = _assessment(log, household)

    assert FinanceEntityProjection(log).accounts[
        household.alex_pension_id].projection_authority == "foundry_modelled"
    assert assessment.status != "unavailable"
    assert assessment.forecast[-1].base == baseline.forecast[-1].base
    assert not any("provider projection" in value for value in assessment.limitations)


def test_unvalued_foundry_modelled_pension_raises_no_provider_requirement(tmp_path):
    log, household = _seed(tmp_path)
    baseline = _assessment(log, household)
    _unvalued_provider_pension(log, household, authority="foundry_modelled")

    assessment = _assessment(log, household)

    assert assessment.status != "unavailable"
    assert assessment.forecast[-1].base == baseline.forecast[-1].base
    assert not any("provider projection" in value for value in assessment.limitations)

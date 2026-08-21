import pytest

from foundry.application.mission_assumptions import MissionAssumptionError, MissionAssumptionService
from foundry.core.entities import declare_mission, declare_party
from foundry.eventlog import EventLog
from foundry.finance.mission_assessment import POLICY_ID as FI
from foundry.finance.missions import FINANCE_MISSION_DEFINITIONS
from foundry.finance.mortgage_assessment import POLICY_ID as MORTGAGE
from foundry.finance.pension_assessment import POLICY_ID as PENSION
from foundry.finance.resilience_assessment import POLICY_ID as RESILIENCE


def _world(tmp_path, policy):
    log = EventLog(tmp_path / "events.jsonl")
    household = declare_party(log, "household")
    mission = declare_mission(log, "Test mission", assessment_policy_id=policy,
                              household_id=household.id)
    return log, household, mission, MissionAssumptionService(log)


PAYLOADS = {
    FI: {"monthly_contribution": 1000, "low_real_return": .01, "base_real_return": .03,
         "high_real_return": .05, "horizon_years": 30, "history_months": 12,
         "delta_v_lookback_days": 90, "desired_annual_spending": 30000, "withdrawal_rate": .04},
    RESILIENCE: {"critical_floor_months": 1, "income_concentration_limit": .5,
                 "outflow_crosscheck_tolerance": .2, "evidence_stale_after_days": 120,
                 "movement_lookback_days": 90, "income_reduction_fraction": .25,
                 "income_reduction_months": 3, "unexpected_expenditure": 5000,
                 "rate_shock_monthly_cost": 300, "temporary_unemployment_months": 3},
    PENSION: {"required_retirement_income_annual": 40000, "low_real_return": .01,
              "base_real_return": .03, "high_real_return": .05, "sustainable_withdrawal_rate": .04,
              "assumed_annual_fee_percent": .0075, "contribution_stale_after_days": 400,
              "valuation_stale_after_days": 550, "evidence_crosscheck_tolerance": .2,
              "accelerated_threshold_months": 36, "divergent_floor_fraction": .75,
              "surplus_high_fraction": .2, "shortfall_low_fraction": .1,
              "sp_reliance_low_fraction": 1/3, "sp_reliance_mid_fraction": .5,
              "sp_reliance_high_fraction": 2/3, "delta_v_lookback_days": 90,
              "recommendation_liquidity_floor_months": 6},
    MORTGAGE: {"low_post_fix_rate": .03, "base_post_fix_rate": .04,
               "high_post_fix_rate": .05, "forecast_horizon_months": 360,
               "balance_stale_after_days": 120, "valuation_stale_after_days": 365,
               "liquidity_floor_months": 12},
}


@pytest.mark.parametrize("policy", [FI, RESILIENCE, PENSION, MORTGAGE])
def test_each_mission_has_typed_editable_schema(tmp_path, policy):
    log, household, mission, service = _world(tmp_path, policy)
    schema = service.schema(mission.id, household.id)
    assert schema.fields
    assert "reserve_target_months" not in schema.fields
    assert "secure_floor_months" not in schema.fields
    assert "commitment_horizon_months" not in schema.fields
    assert not {"milestone_fraction_1", "milestone_fraction_2", "milestone_fraction_3", "milestone_fraction_4"} & set(schema.fields)


def test_lifecycle_is_household_bound_and_revision_is_immutable(tmp_path):
    log, household, mission, service = _world(tmp_path, FI)
    first = service.declare(mission_id=mission.id, household_id=household.id, assumptions=PAYLOADS[FI])
    assert service.readiness(mission.id, household.id).has_active_set
    second_payload = {**PAYLOADS[FI], "monthly_contribution": 1250}
    second = service.declare(mission_id=mission.id, household_id=household.id, assumptions=second_payload)
    finance = service._state()[1]
    assert finance.assumption_sets[first["assumption_set_id"]].status == "archived"
    assert finance.assumption_sets[first["assumption_set_id"]].assumptions["monthly_contribution"] == 1000
    assert finance.assumption_sets[second["assumption_set_id"]].status == "active"

    other = declare_party(log, "household")
    with pytest.raises(MissionAssumptionError):
        service.readiness(mission.id, other.id)


def test_proposal_binds_payload_mission_principal_and_replay(tmp_path):
    log, household, mission, service = _world(tmp_path, FI)
    proposal = service.propose(mission_id=mission.id, household_id=household.id,
                               assumptions=PAYLOADS[FI], principal="owner@example.com")
    with pytest.raises(MissionAssumptionError):
        service.execute(proposal_id=proposal["proposal_id"], mission_id=mission.id,
                        household_id=household.id, assumptions={**PAYLOADS[FI], "monthly_contribution": 2},
                        principal="owner@example.com", command_id="cmd-1")
    result = service.execute(proposal_id=proposal["proposal_id"], mission_id=mission.id,
                             household_id=household.id, assumptions=PAYLOADS[FI],
                             principal="owner@example.com", command_id="cmd-1")
    assert service.execute(proposal_id=proposal["proposal_id"], mission_id=mission.id,
                           household_id=household.id, assumptions=PAYLOADS[FI],
                           principal="owner@example.com", command_id="cmd-1") == result


def test_execute_command_id_collision_is_household_scoped(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    household_a = declare_party(log, "household")
    household_b = declare_party(log, "household")
    mission_a = declare_mission(log, "Household A FI", assessment_policy_id=FI,
                                household_id=household_a.id)
    mission_b = declare_mission(log, "Household B FI", assessment_policy_id=FI,
                                household_id=household_b.id)
    service = MissionAssumptionService(log)
    proposal_a = service.propose(mission_id=mission_a.id, household_id=household_a.id,
                                 assumptions=PAYLOADS[FI], principal="owner@example.com")
    result_a = service.execute(proposal_id=proposal_a["proposal_id"], mission_id=mission_a.id,
                               household_id=household_a.id, assumptions=PAYLOADS[FI],
                               principal="owner@example.com", command_id="shared-command")

    proposal_b = service.propose(mission_id=mission_b.id, household_id=household_b.id,
                                 assumptions=PAYLOADS[FI], principal="owner@example.com")
    result_b = service.execute(proposal_id=proposal_b["proposal_id"], mission_id=mission_b.id,
                               household_id=household_b.id, assumptions=PAYLOADS[FI],
                               principal="owner@example.com", command_id="shared-command")

    assert result_b != result_a
    assert result_b["mission_id"] == mission_b.id
    assert service.execute(proposal_id=proposal_b["proposal_id"], mission_id=mission_b.id,
                           household_id=household_b.id, assumptions=PAYLOADS[FI],
                           principal="owner@example.com", command_id="shared-command") == result_b


def test_execute_rejects_command_id_reuse_for_different_operation(tmp_path):
    _, household, mission, service = _world(tmp_path, FI)
    first = service.propose(mission_id=mission.id, household_id=household.id,
                            assumptions=PAYLOADS[FI], principal="owner@example.com")
    service.execute(proposal_id=first["proposal_id"], mission_id=mission.id,
                    household_id=household.id, assumptions=PAYLOADS[FI],
                    principal="owner@example.com", command_id="command-1")
    changed = {**PAYLOADS[FI], "monthly_contribution": 1250}
    second = service.propose(mission_id=mission.id, household_id=household.id,
                             assumptions=changed, principal="owner@example.com")
    with pytest.raises(MissionAssumptionError, match="different operation"):
        service.execute(proposal_id=second["proposal_id"], mission_id=mission.id,
                        household_id=household.id, assumptions=changed,
                        principal="owner@example.com", command_id="command-1")

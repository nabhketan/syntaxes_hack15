import pytest
from fairshift.models import Applicant, Program, ScenarioCondition
from fairshift.validator import AllocationValidator


def test_validator_detects_all_violations():
    """Verify that AllocationValidator catches all types of constraint breaches independently."""
    progs = [
        Program("P1", "Program 1", capacity=1, eligibility_criteria="ALL"),
        Program("P_SPEC", "Specialized", capacity=2, eligibility_criteria="SPEC_TAG"),
    ]
    apps = [
        Applicant("A1", "Alice", eligibility=["ALL"], preferences=["P1"], status="active"),
        Applicant("A2", "Bob", eligibility=["ALL"], preferences=["P1"], status="active"),
        Applicant("A3", "Withdrawn Charlie", eligibility=["ALL"], preferences=["P1"], status="withdrawn"),
        Applicant("A4", "Diana", eligibility=["ALL"], preferences=["P_SPEC"], status="active"),
    ]

    # Test 1: Capacity Violation (2 assigned to P1 which has capacity 1)
    v1 = AllocationValidator(apps, progs)
    res1 = v1.validate({"A1": "P1", "A2": "P1"})
    assert res1.is_valid is False
    assert res1.checked_rules["program_capacity"] is False
    assert any("capacity exceeded" in err.lower() for err in res1.errors)

    # Test 2: Withdrawal Violation (withdrawn Charlie assigned)
    res2 = v1.validate({"A3": "P1"})
    assert res2.is_valid is False
    assert res2.checked_rules["withdrawals_respected"] is False
    assert any("withdrawn applicant" in err.lower() for err in res2.errors)

    # Test 3: Eligibility Violation (Diana not having SPEC_TAG assigned to P_SPEC)
    res3 = v1.validate({"A4": "P_SPEC"})
    assert res3.is_valid is False
    assert res3.checked_rules["eligibility_met"] is False
    assert any("not eligible" in err.lower() for err in res3.errors)

    # Test 4: Scenario Condition Violation
    condition = ScenarioCondition(applicant_id="A1", requested_program_id="P_SPEC", enforce=True)
    v4 = AllocationValidator(apps, progs, scenario_conditions=[condition])
    res4 = v4.validate({"A1": "P1"})  # Assigned P1 instead of P_SPEC
    assert res4.is_valid is False
    assert res4.checked_rules["scenario_conditions_met"] is False

    # Test 5: Unknown Entity Violation
    res5 = v1.validate({"UNKNOWN_APP": "P1", "A1": "UNKNOWN_PROG"})
    assert res5.is_valid is False
    assert res5.checked_rules["valid_entity_references"] is False


def test_validator_passes_clean_allocation():
    """Verify validator approves a perfectly compliant allocation."""
    progs = [
        Program("P1", "Program 1", capacity=2, eligibility_criteria="ALL"),
    ]
    apps = [
        Applicant("A1", "Alice", eligibility=["ALL"], preferences=["P1"], status="active"),
        Applicant("A2", "Bob", eligibility=["ALL"], preferences=["P1"], status="active"),
    ]
    v = AllocationValidator(apps, progs)
    res = v.validate({"A1": "P1", "A2": "P1"})
    assert res.is_valid is True
    assert len(res.errors) == 0


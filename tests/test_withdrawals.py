import pytest
from fairshift.models import Applicant, Program, SolverStatusEnum
from fairshift.optimizer import AllocationOptimizer
from fairshift.analyzer import ScenarioAnalyzer
from fairshift.validator import AllocationValidator


def test_withdrawn_applicant_not_assigned():
    """Verify withdrawn applicants never receive assignments in solver."""
    progs = [
        Program("P1", "Program 1", capacity=5, eligibility_criteria="ALL"),
    ]
    apps = [
        Applicant("A1", "Active Alice", eligibility=["ALL"], preferences=["P1"], status="active"),
        Applicant("A2", "Withdrawn Bob", eligibility=["ALL"], preferences=["P1"], status="withdrawn"),
    ]

    opt = AllocationOptimizer(applicants=apps, programs=progs)
    res = opt.solve()

    assert res.solver_status == SolverStatusEnum.OPTIMAL
    assert res.assignments.get("A1") == "P1"
    assert "A2" not in res.assignments

    validator = AllocationValidator(apps, progs)
    val = validator.validate(res.assignments)
    assert val.is_valid is True
    assert val.checked_rules["withdrawals_respected"] is True


def test_withdrawal_cascade_and_ripple_effect():
    """Demonstrate a withdrawal freeing a seat, promoting another applicant, and cascading to an unassigned applicant.
    
    Setup:
    P1 has capacity 1. P2 has capacity 1.
    A1: 1st P1 (gets P1 in baseline)
    A2: 1st P1, 2nd P2 (gets P2 in baseline because A2's 2nd choice beats A3's 3rd choice)
    A3: 1st P_FULL, 2nd P_FULL2, 3rd P2 (unassigned in baseline because P2 taken by A2)

    Scenario: A1 withdraws!
    P1 is freed -> A2 gets promoted to P1 (1st choice)!
    P2 is freed -> A3 gets newly assigned to P2 (3rd choice)!
    """
    progs = [
        Program("P1", "Top AI Fellowship", capacity=1, eligibility_criteria="ALL"),
        Program("P2", "Data Analytics", capacity=1, eligibility_criteria="ALL"),
    ]
    apps = [
        Applicant("A1", "Alice", eligibility=["ALL"], preferences=["P1"], status="active"),
        Applicant("A2", "Bob", eligibility=["ALL"], preferences=["P1", "P2"], status="active"),
        Applicant("A3", "Charlie", eligibility=["ALL"], preferences=["P_NONEXIST1", "P_NONEXIST2", "P2"], status="active"),
    ]

    # Baseline run
    base_opt = AllocationOptimizer(applicants=apps, programs=progs)
    base_res = base_opt.solve()

    assert base_res.assignments.get("A1") == "P1"
    assert base_res.assignments.get("A2") == "P2"
    assert "A3" not in base_res.assignments

    # Scenario: A1 withdraws
    analyzer = ScenarioAnalyzer(applicants=apps, programs=progs, baseline_result=base_res)
    scen_res, report = analyzer.analyze_withdrawal("A1")

    assert scen_res.solver_status == SolverStatusEnum.OPTIMAL
    # A1 is withdrawn and has no assignment
    assert "A1" not in scen_res.assignments
    # A2 got promoted to P1
    assert scen_res.assignments.get("A2") == "P1"
    # A3 is newly assigned to P2
    assert scen_res.assignments.get("A3") == "P2"

    # Verify impact report details
    assert report.is_feasible is True
    assert report.reassignment_count == 2  # A2 changed from P2 to P1, A3 newly assigned
    assert report.affected_count == 3  # A1, A2, A3

    # Check applicant change records
    change_map = {c.applicant_id: c for c in report.changes}
    assert change_map["A1"].change_type == "withdrawn"
    assert change_map["A2"].change_type == "promoted"
    assert change_map["A2"].before_program == "P2"
    assert change_map["A2"].after_program == "P1"
    assert change_map["A3"].change_type == "newly_assigned"
    assert change_map["A3"].after_program == "P2"

    # Check factual explanations
    assert any("releasing 1 seat" in exp for exp in report.factual_explanations)

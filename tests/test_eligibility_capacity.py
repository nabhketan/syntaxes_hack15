import pytest
from fairshift.models import Applicant, Program, SolverStatusEnum
from fairshift.optimizer import AllocationOptimizer
from fairshift.validator import AllocationValidator


def test_eligibility_enforcement():
    """Verify applicants are never assigned to programs they are not eligible for."""
    progs = [
        Program("P_OPEN", "Open Program", capacity=5, eligibility_criteria="ALL"),
        Program("P_SPEC", "Specialized Program", capacity=5, eligibility_criteria="SPEC_REQUIRED"),
    ]
    apps = [
        Applicant("A1", "Eligible Alice", eligibility=["ALL", "SPEC_REQUIRED"], preferences=["P_SPEC", "P_OPEN"]),
        Applicant("A2", "Ineligible Bob", eligibility=["ALL"], preferences=["P_SPEC", "P_OPEN"]),
        Applicant("A3", "Ineligible Charlie", eligibility=["ALL"], preferences=["P_SPEC"]),
    ]

    opt = AllocationOptimizer(applicants=apps, programs=progs)
    res = opt.solve()

    assert res.solver_status == SolverStatusEnum.OPTIMAL
    # A1 can receive P_SPEC
    assert res.assignments.get("A1") == "P_SPEC"
    # A2 cannot receive P_SPEC, should receive P_OPEN
    assert res.assignments.get("A2") == "P_OPEN"
    # A3 only requested P_SPEC which he is not eligible for, so must remain unassigned
    assert "A3" not in res.assignments
    assert "A3" in res.unassigned_applicants

    # Independent validation
    validator = AllocationValidator(apps, progs)
    val = validator.validate(res.assignments)
    assert val.is_valid is True
    assert val.checked_rules["eligibility_met"] is True


def test_capacity_limits():
    """Verify program capacity is never exceeded even under high demand."""
    progs = [
        Program("P1", "Limited Program", capacity=2, eligibility_criteria="ALL"),
    ]
    apps = [
        Applicant(f"A{i}", f"Applicant {i}", eligibility=["ALL"], preferences=["P1"])
        for i in range(1, 10)
    ]

    opt = AllocationOptimizer(applicants=apps, programs=progs)
    res = opt.solve()

    assert res.solver_status == SolverStatusEnum.OPTIMAL
    assert res.total_assigned == 2
    assert len(res.unassigned_applicants) == 7

    assigned_to_p1 = [a for a, p in res.assignments.items() if p == "P1"]
    assert len(assigned_to_p1) == 2

    validator = AllocationValidator(apps, progs)
    val = validator.validate(res.assignments)
    assert val.is_valid is True
    assert val.checked_rules["program_capacity"] is True


def test_zero_capacity_program():
    """Verify program with 0 capacity receives 0 assignments."""
    progs = [
        Program("P_ZERO", "Zero Cap Program", capacity=0, eligibility_criteria="ALL"),
        Program("P_SPARE", "Spare Program", capacity=5, eligibility_criteria="ALL"),
    ]
    apps = [
        Applicant("A1", "Alice", eligibility=["ALL"], preferences=["P_ZERO", "P_SPARE"]),
    ]
    opt = AllocationOptimizer(applicants=apps, programs=progs)
    res = opt.solve()

    assert res.solver_status == SolverStatusEnum.OPTIMAL
    assert res.assignments.get("A1") == "P_SPARE"
    assert res.capacity_utilization["P_ZERO"]["assigned"] == 0


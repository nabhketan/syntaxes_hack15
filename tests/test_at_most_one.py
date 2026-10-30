import pytest
from fairshift.models import Applicant, Program, SolverStatusEnum
from fairshift.optimizer import AllocationOptimizer
from fairshift.validator import AllocationValidator


def test_at_most_one_assignment_per_applicant():
    """Verify each applicant receives at most one program regardless of multiple eligible choices."""
    progs = [
        Program("P1", "Program 1", capacity=10, eligibility_criteria="ALL"),
        Program("P2", "Program 2", capacity=10, eligibility_criteria="ALL"),
        Program("P3", "Program 3", capacity=10, eligibility_criteria="ALL"),
    ]
    apps = [
        Applicant("A1", "Alice", eligibility=["ALL"], preferences=["P1", "P2", "P3"]),
        Applicant("A2", "Bob", eligibility=["ALL"], preferences=["P2", "P3", "P1"]),
        Applicant("A3", "Charlie", eligibility=["ALL"], preferences=["P3", "P1", "P2"]),
    ]

    opt = AllocationOptimizer(applicants=apps, programs=progs)
    res = opt.solve()

    assert res.solver_status == SolverStatusEnum.OPTIMAL
    assigned_apps = list(res.assignments.keys())
    # Each applicant ID should appear at most once
    assert len(assigned_apps) == len(set(assigned_apps))
    assert len(assigned_apps) == 3

    validator = AllocationValidator(apps, progs)
    val = validator.validate(res.assignments)
    assert val.is_valid is True
    assert val.checked_rules["unique_assignment"] is True


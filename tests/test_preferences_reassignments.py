import pytest
from fairshift.models import Applicant, Program, SolverStatusEnum, OptimizationConfig
from fairshift.optimizer import AllocationOptimizer


def test_preference_scoring_prioritization():
    """Verify that when 2 applicants compete for a single seat, the one with higher preference rank gets it."""
    progs = [
        Program("P1", "Target Program", capacity=1, eligibility_criteria="ALL"),
        Program("P2", "Alternate Program", capacity=5, eligibility_criteria="ALL"),
    ]
    apps = [
        # Alice has P1 as choice 1
        Applicant("A1", "Alice", eligibility=["ALL"], preferences=["P1", "P2"]),
        # Bob has P1 as choice 2
        Applicant("A2", "Bob", eligibility=["ALL"], preferences=["P2", "P1"]),
    ]

    opt = AllocationOptimizer(apps, progs)
    res = opt.solve()

    assert res.solver_status == SolverStatusEnum.OPTIMAL
    # Alice gets P1 (choice 1), Bob gets P2 (choice 1) -> Total preference satisfaction is maximized
    assert res.assignments.get("A1") == "P1"
    assert res.assignments.get("A2") == "P2"
    assert res.rank_distribution.get(1) == 2


def test_stability_minimizes_unnecessary_reassignments():
    """Verify that when alternative equivalent optimal allocations exist, the solver preserves the baseline assignments."""
    progs = [
        Program("P1", "Program 1", capacity=1, eligibility_criteria="ALL"),
        Program("P2", "Program 2", capacity=1, eligibility_criteria="ALL"),
    ]
    # A1 and A2 both have identical preferences [P1, P2]
    apps = [
        Applicant("A1", "Alice", eligibility=["ALL"], preferences=["P1", "P2"]),
        Applicant("A2", "Bob", eligibility=["ALL"], preferences=["P1", "P2"]),
    ]

    # Baseline: suppose A1 is in P2 and A2 is in P1
    baseline = {"A1": "P2", "A2": "P1"}

    opt = AllocationOptimizer(apps, progs, baseline_assignments=baseline)
    res = opt.solve()

    assert res.solver_status == SolverStatusEnum.OPTIMAL
    # Because baseline had A1 in P2 and A2 in P1, stability objective preserves it!
    assert res.assignments.get("A1") == "P2"
    assert res.assignments.get("A2") == "P1"
    assert res.reassignment_count == 0


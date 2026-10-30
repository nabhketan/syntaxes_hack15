import pytest
from fairshift.models import Applicant, Program, SolverStatusEnum, OptimizationConfig, ScenarioCondition
from fairshift.optimizer import AllocationOptimizer


def test_solver_status_optimal():
    """Verify standard solvable instance returns OPTIMAL."""
    progs = [Program("P1", "Program 1", capacity=2, eligibility_criteria="ALL")]
    apps = [Applicant("A1", "Alice", eligibility=["ALL"], preferences=["P1"])]

    opt = AllocationOptimizer(apps, progs)
    res = opt.solve()
    assert res.solver_status == SolverStatusEnum.OPTIMAL


def test_solver_status_infeasible():
    """Verify mathematically impossible problem returns INFEASIBLE."""
    progs = [Program("P1", "Program 1", capacity=0, eligibility_criteria="ALL")]
    # Force placement of A1 into P1 with capacity 0
    apps = [Applicant("A1", "Alice", eligibility=["ALL"], preferences=["P1"])]
    cond = ScenarioCondition(applicant_id="A1", requested_program_id="P1", enforce=True)

    opt = AllocationOptimizer(apps, progs)
    res = opt.solve(scenario_conditions=[cond])
    assert res.solver_status == SolverStatusEnum.INFEASIBLE


def test_solver_status_timeout_is_never_reported_as_infeasible():
    """Verify that when the solver times out, it reports UNKNOWN_OR_TIMEOUT, never INFEASIBLE."""
    # Create an optimization problem and set an impossibly short timeout (e.g. 0.0000001 seconds)
    progs = [
        Program(f"P{i}", f"Program {i}", capacity=5, eligibility_criteria="ALL")
        for i in range(10)
    ]
    apps = [
        Applicant(f"A{i}", f"Applicant {i}", eligibility=["ALL"], preferences=[f"P{j}" for j in range(10)])
        for i in range(100)
    ]

    # Impossibly tight time limit
    config = OptimizationConfig(time_limit_seconds=0.000001)
    opt = AllocationOptimizer(apps, progs, config=config)
    res = opt.solve()

    # The status must NOT be reported as INFEASIBLE
    assert res.solver_status != SolverStatusEnum.INFEASIBLE
    # It must be either OPTIMAL (if solved instantly) or UNKNOWN_OR_TIMEOUT
    assert res.solver_status in (SolverStatusEnum.UNKNOWN_OR_TIMEOUT, SolverStatusEnum.OPTIMAL, SolverStatusEnum.FEASIBLE)


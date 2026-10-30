import pytest
from fairshift.models import Applicant, Program, SolverStatusEnum
from fairshift.optimizer import AllocationOptimizer
from fairshift.analyzer import ScenarioAnalyzer


def test_capacity_increase():
    """Verify that increasing capacity admits previously unassigned applicants."""
    progs = [
        Program("P1", "Program 1", capacity=1, eligibility_criteria="ALL"),
    ]
    apps = [
        Applicant("A1", "Alice", eligibility=["ALL"], preferences=["P1"]),
        Applicant("A2", "Bob", eligibility=["ALL"], preferences=["P1"]),
    ]

    base_opt = AllocationOptimizer(apps, progs)
    base_res = base_opt.solve()
    assert base_res.total_assigned == 1

    # Increase capacity to 2
    analyzer = ScenarioAnalyzer(apps, progs, baseline_result=base_res)
    scen_res, report = analyzer.analyze_capacity_change("P1", new_capacity=2)

    assert scen_res.solver_status == SolverStatusEnum.OPTIMAL
    assert scen_res.total_assigned == 2
    assert scen_res.assignments.get("A1") == "P1"
    assert scen_res.assignments.get("A2") == "P1"
    assert report.net_assigned_change == 1


def test_capacity_decrease():
    """Verify that decreasing capacity bumps an assigned applicant to unassigned or lower preference."""
    progs = [
        Program("P1", "Program 1", capacity=2, eligibility_criteria="ALL"),
    ]
    apps = [
        Applicant("A1", "Alice", eligibility=["ALL"], preferences=["P1"]),
        Applicant("A2", "Bob", eligibility=["ALL"], preferences=["P1"]),
    ]

    base_opt = AllocationOptimizer(apps, progs)
    base_res = base_opt.solve()
    assert base_res.total_assigned == 2

    # Decrease capacity to 1
    analyzer = ScenarioAnalyzer(apps, progs, baseline_result=base_res)
    scen_res, report = analyzer.analyze_capacity_change("P1", new_capacity=1)

    assert scen_res.solver_status == SolverStatusEnum.OPTIMAL
    assert scen_res.total_assigned == 1
    assert report.net_assigned_change == -1
    assert len(report.changes) >= 1
    became_unassigned = [c for c in report.changes if c.change_type == "became_unassigned"]
    assert len(became_unassigned) == 1


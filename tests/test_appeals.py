import pytest
from fairshift.models import Applicant, Program, SolverStatusEnum
from fairshift.optimizer import AllocationOptimizer
from fairshift.analyzer import ScenarioAnalyzer


def test_feasible_appeal_scenario():
    """Verify that a feasible appeal places the appellant into requested program and adjusts others without mutating baseline."""
    progs = [
        Program("P1", "Elite Program", capacity=1, eligibility_criteria="ALL"),
        Program("P2", "Standard Program", capacity=1, eligibility_criteria="ALL"),
    ]
    apps = [
        Applicant("A1", "Alice", eligibility=["ALL"], preferences=["P1"]),
        Applicant("A2", "Bob", eligibility=["ALL"], preferences=["P1", "P2"]),
    ]

    base_opt = AllocationOptimizer(apps, progs)
    base_res = base_opt.solve()

    # Baseline: Alice gets P1, Bob gets P2
    assert base_res.assignments.get("A1") == "P1"
    assert base_res.assignments.get("A2") == "P2"

    # Bob appeals for P1!
    analyzer = ScenarioAnalyzer(apps, progs, baseline_result=base_res)
    appeal_res, report = analyzer.analyze_appeal(applicant_id="A2", requested_program_id="P1")

    assert appeal_res.solver_status == SolverStatusEnum.OPTIMAL
    assert appeal_res.assignments.get("A2") == "P1"  # Bob granted P1
    # Baseline was NOT overwritten!
    assert base_res.assignments.get("A1") == "P1"
    assert base_res.assignments.get("A2") == "P2"

    # Report accurately reflects change
    assert report.is_feasible is True
    assert report.affected_count >= 1


def test_infeasible_appeal_due_to_ineligibility():
    """Verify that an appeal requesting a program for which the applicant is ineligible proves INFEASIBLE."""
    progs = [
        Program("P_HEALTH", "Healthcare", capacity=5, eligibility_criteria="HEALTH_CERT"),
    ]
    apps = [
        Applicant("A1", "Alice", eligibility=["ALL"], preferences=[]),  # Not HEALTH_CERT
    ]

    base_opt = AllocationOptimizer(apps, progs)
    base_res = base_opt.solve()

    analyzer = ScenarioAnalyzer(apps, progs, baseline_result=base_res)
    appeal_res, report = analyzer.analyze_appeal(applicant_id="A1", requested_program_id="P_HEALTH")

    assert appeal_res.solver_status == SolverStatusEnum.INFEASIBLE
    assert report.is_feasible is False
    assert any("does not meet the eligibility requirements" in exp for exp in report.factual_explanations)


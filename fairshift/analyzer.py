"""Scenario and impact analysis for withdrawals, capacity adjustments, and appeals.

Strictly compares baseline allocations with scenario outcomes, identifying:
- Exact list of applicants whose assignments changed, stayed, or were newly assigned/unassigned.
- Metric differentials (assignments, preference scores, reassignments, capacities).
- Factual, evidence-based chain of explanations grounded solely in inputs and solver output.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from .models import Applicant, Program, AllocationResult, ScenarioCondition, SolverStatusEnum
from .optimizer import AllocationOptimizer


@dataclass
class ApplicantChange:
    applicant_id: str
    name: str
    status: str
    before_program: Optional[str]
    after_program: Optional[str]
    before_program_name: Optional[str]
    after_program_name: Optional[str]
    before_rank: Optional[int]
    after_rank: Optional[int]
    change_type: str  # "promoted", "demoted", "stayed", "newly_assigned", "became_unassigned", "withdrawn", "lateral"
    details: str


@dataclass
class ImpactReport:
    scenario_type: str
    scenario_title: str
    baseline_run_id: str
    scenario_run_id: str
    solver_status: SolverStatusEnum
    is_feasible: bool
    total_assigned_before: int
    total_assigned_after: int
    net_assigned_change: int
    pref_score_before: int
    pref_score_after: int
    pref_score_change: int
    reassignment_count: int
    affected_count: int
    changes: List[ApplicantChange] = field(default_factory=list)
    capacity_diffs: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    factual_explanations: List[str] = field(default_factory=list)
    validation_status: bool = True
    validation_errors: List[str] = field(default_factory=list)


class ScenarioAnalyzer:
    """Analyzer executing what-if simulations against a fixed baseline allocation."""

    def __init__(
        self,
        applicants: List[Applicant],
        programs: List[Program],
        baseline_result: AllocationResult,
    ):
        self.applicants = {a.applicant_id: a for a in applicants}
        self.programs = {p.program_id: p for p in programs}
        self.baseline_result = baseline_result

    def analyze_withdrawal(
        self,
        withdrawn_applicant_id: str,
        config=None,
    ) -> Tuple[AllocationResult, ImpactReport]:
        """Analyze the ripple effect of an applicant withdrawing and releasing their seat."""
        applicant = self.applicants.get(withdrawn_applicant_id)
        if not applicant:
            raise ValueError(f"Applicant '{withdrawn_applicant_id}' not found.")

        # Create updated applicants list where target applicant is marked withdrawn
        modified_applicants: List[Applicant] = []
        for a in self.applicants.values():
            if a.applicant_id == withdrawn_applicant_id:
                # Mark as withdrawn
                modified_applicants.append(
                    Applicant(
                        applicant_id=a.applicant_id,
                        name=a.name,
                        eligibility=list(a.eligibility),
                        preferences=list(a.preferences),
                        status="withdrawn",
                        notes=f"{a.notes} [Withdrawn in analysis]".strip(),
                    )
                )
            else:
                modified_applicants.append(a)

        optimizer = AllocationOptimizer(
            applicants=modified_applicants,
            programs=list(self.programs.values()),
            baseline_assignments=self.baseline_result.assignments,
            config=config,
        )

        scenario_desc = f"Withdrawal of {applicant.name} ({withdrawn_applicant_id})"
        scenario_result = optimizer.solve(
            scenario_type="withdrawal",
            scenario_description=scenario_desc,
            baseline_run_id=self.baseline_result.run_id,
        )

        report = self._build_impact_report(
            scenario_type="withdrawal",
            scenario_title=scenario_desc,
            scenario_result=scenario_result,
            context={"withdrawn_id": withdrawn_applicant_id},
        )
        return scenario_result, report

    def analyze_capacity_change(
        self,
        program_id: str,
        new_capacity: int,
        config=None,
    ) -> Tuple[AllocationResult, ImpactReport]:
        """Analyze the impact of increasing or decreasing a program's seat capacity."""
        target_prog = self.programs.get(program_id)
        if not target_prog:
            raise ValueError(f"Program '{program_id}' not found.")
        if new_capacity < 0:
            raise ValueError("Program capacity cannot be negative.")

        modified_programs: List[Program] = []
        for p in self.programs.values():
            if p.program_id == program_id:
                modified_programs.append(
                    Program(
                        program_id=p.program_id,
                        name=p.name,
                        capacity=new_capacity,
                        eligibility_criteria=p.eligibility_criteria,
                        description=p.description,
                    )
                )
            else:
                modified_programs.append(p)

        optimizer = AllocationOptimizer(
            applicants=list(self.applicants.values()),
            programs=modified_programs,
            baseline_assignments=self.baseline_result.assignments,
            config=config,
        )

        cap_delta = new_capacity - target_prog.capacity
        delta_str = f"+{cap_delta}" if cap_delta > 0 else f"{cap_delta}"
        scenario_desc = f"Capacity change for {target_prog.name} ({program_id}): {target_prog.capacity} -> {new_capacity} ({delta_str} seats)"

        scenario_result = optimizer.solve(
            scenario_type="capacity_change",
            scenario_description=scenario_desc,
            baseline_run_id=self.baseline_result.run_id,
        )

        report = self._build_impact_report(
            scenario_type="capacity_change",
            scenario_title=scenario_desc,
            scenario_result=scenario_result,
            modified_programs={p.program_id: p for p in modified_programs},
            context={"program_id": program_id, "old_capacity": target_prog.capacity, "new_capacity": new_capacity},
        )
        return scenario_result, report

    def analyze_appeal(
        self,
        applicant_id: str,
        requested_program_id: str,
        config=None,
    ) -> Tuple[AllocationResult, ImpactReport]:
        """Analyze counterfactual appeal: forcing placement of applicant into requested program."""
        applicant = self.applicants.get(applicant_id)
        prog = self.programs.get(requested_program_id)

        if not applicant:
            raise ValueError(f"Applicant '{applicant_id}' not found.")
        if not prog:
            raise ValueError(f"Program '{requested_program_id}' not found.")

        condition = ScenarioCondition(
            applicant_id=applicant_id,
            requested_program_id=requested_program_id,
            enforce=True,
            description=f"Appeal placement of {applicant.name} into {prog.name}",
        )

        optimizer = AllocationOptimizer(
            applicants=list(self.applicants.values()),
            programs=list(self.programs.values()),
            baseline_assignments=self.baseline_result.assignments,
            config=config,
        )

        scenario_desc = f"Appeal: Assign {applicant.name} ({applicant_id}) to {prog.name} ({requested_program_id})"
        scenario_result = optimizer.solve(
            scenario_type="appeal",
            scenario_description=scenario_desc,
            scenario_conditions=[condition],
            baseline_run_id=self.baseline_result.run_id,
        )

        report = self._build_impact_report(
            scenario_type="appeal",
            scenario_title=scenario_desc,
            scenario_result=scenario_result,
            context={"applicant_id": applicant_id, "program_id": requested_program_id},
        )
        return scenario_result, report

    def _build_impact_report(
        self,
        scenario_type: str,
        scenario_title: str,
        scenario_result: AllocationResult,
        modified_programs: Optional[Dict[str, Program]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> ImpactReport:
        """Construct a rigorous, fact-based impact report comparing baseline to scenario."""
        programs_map = modified_programs or self.programs
        context = context or {}

        base_assign = self.baseline_result.assignments
        scen_assign = scenario_result.assignments

        is_feasible = scenario_result.solver_status in (SolverStatusEnum.OPTIMAL, SolverStatusEnum.FEASIBLE)

        changes: List[ApplicantChange] = []
        reassignment_count = 0
        affected_count = 0

        # Examine all applicants known
        for app_id, app in self.applicants.items():
            base_p = base_assign.get(app_id)
            scen_p = scen_assign.get(app_id)

            base_p_name = self.programs[base_p].name if base_p in self.programs else None
            scen_p_name = programs_map[scen_p].name if scen_p in programs_map else None

            base_rank = app.preference_rank(base_p) if base_p else None
            scen_rank = app.preference_rank(scen_p) if scen_p else None

            if context.get("withdrawn_id") == app_id:
                # Target withdrawn applicant
                changes.append(
                    ApplicantChange(
                        applicant_id=app_id,
                        name=app.name,
                        status="withdrawn",
                        before_program=base_p,
                        after_program=None,
                        before_program_name=base_p_name,
                        after_program_name=None,
                        before_rank=base_rank,
                        after_rank=None,
                        change_type="withdrawn",
                        details=f"Withdrew from program '{base_p or 'None'}'. Released seat for reassignment.",
                    )
                )
                affected_count += 1
                continue

            if base_p == scen_p:
                if base_p is not None:
                    changes.append(
                        ApplicantChange(
                            applicant_id=app_id,
                            name=app.name,
                            status="active",
                            before_program=base_p,
                            after_program=scen_p,
                            before_program_name=base_p_name,
                            after_program_name=scen_p_name,
                            before_rank=base_rank,
                            after_rank=scen_rank,
                            change_type="stayed",
                            details="Assignment unchanged from baseline.",
                        )
                    )
            else:
                affected_count += 1
                if base_p is None and scen_p is not None:
                    # Newly assigned
                    changes.append(
                        ApplicantChange(
                            applicant_id=app_id,
                            name=app.name,
                            status="active",
                            before_program=None,
                            after_program=scen_p,
                            before_program_name=None,
                            after_program_name=scen_p_name,
                            before_rank=None,
                            after_rank=scen_rank,
                            change_type="newly_assigned",
                            details=f"Previously unassigned; now assigned to {scen_p_name} (Rank {scen_rank}).",
                        )
                    )
                    reassignment_count += 1
                elif base_p is not None and scen_p is None:
                    # Became unassigned
                    changes.append(
                        ApplicantChange(
                            applicant_id=app_id,
                            name=app.name,
                            status="active",
                            before_program=base_p,
                            after_program=None,
                            before_program_name=base_p_name,
                            after_program_name=None,
                            before_rank=base_rank,
                            after_rank=None,
                            change_type="became_unassigned",
                            details=f"Displaced from {base_p_name} (Rank {base_rank}); now unassigned.",
                        )
                    )
                    reassignment_count += 1
                else:
                    # Reassigned from one program to another
                    reassignment_count += 1
                    if scen_rank is not None and base_rank is not None:
                        if scen_rank < base_rank:
                            ctype = "promoted"
                            details = f"Promoted from {base_p_name} (Choice #{base_rank}) to {scen_p_name} (Choice #{scen_rank})."
                        elif scen_rank > base_rank:
                            ctype = "demoted"
                            details = f"Demoted from {base_p_name} (Choice #{base_rank}) to {scen_p_name} (Choice #{scen_rank})."
                        else:
                            ctype = "lateral"
                            details = f"Reassigned from {base_p_name} to {scen_p_name} (both Choice #{base_rank})."
                    else:
                        ctype = "reassigned"
                        details = f"Reassigned from {base_p_name} to {scen_p_name}."

                    changes.append(
                        ApplicantChange(
                            applicant_id=app_id,
                            name=app.name,
                            status="active",
                            before_program=base_p,
                            after_program=scen_p,
                            before_program_name=base_p_name,
                            after_program_name=scen_p_name,
                            before_rank=base_rank,
                            after_rank=scen_rank,
                            change_type=ctype,
                            details=details,
                        )
                    )

        # Capacity diffs
        capacity_diffs: Dict[str, Dict[str, Any]] = {}
        for p_id in programs_map:
            base_stat = self.baseline_result.capacity_utilization.get(
                p_id, {"capacity": self.programs.get(p_id, programs_map[p_id]).capacity, "assigned": 0, "remaining": 0}
            )
            scen_stat = scenario_result.capacity_utilization.get(
                p_id, {"capacity": programs_map[p_id].capacity, "assigned": 0, "remaining": 0}
            )
            capacity_diffs[p_id] = {
                "name": programs_map[p_id].name,
                "capacity_before": base_stat["capacity"],
                "capacity_after": scen_stat["capacity"],
                "assigned_before": base_stat["assigned"],
                "assigned_after": scen_stat["assigned"],
                "net_assigned_change": scen_stat["assigned"] - base_stat["assigned"],
                "remaining_after": scen_stat["remaining"],
            }

        # Build factual explanations
        factual_explanations: List[str] = []
        if not is_feasible:
            factual_explanations.append(
                f"Solver proved scenario is {scenario_result.solver_status.value}. No feasible assignment satisfying all hard constraints exists."
            )
            if scenario_type == "appeal":
                app_id = context.get("applicant_id")
                req_p = context.get("program_id")
                app_obj = self.applicants.get(app_id)
                p_obj = self.programs.get(req_p)
                if app_obj and p_obj and not app_obj.is_eligible_for(p_obj):
                    factual_explanations.append(
                        f"Fact: Applicant {app_obj.name} ({app_id}) does not meet the eligibility requirements for {p_obj.name}."
                    )
                elif p_obj and p_obj.capacity <= 0:
                    factual_explanations.append(
                        f"Fact: Program {p_obj.name} has a seat capacity of {p_obj.capacity}."
                    )
                else:
                    factual_explanations.append(
                        "Fact: Enforcing this placement prevents the optimizer from finding any allocation that satisfies program capacities, eligibility, and withdrawal constraints simultaneously."
                    )
        else:
            net_assign = scenario_result.total_assigned - self.baseline_result.total_assigned
            pref_delta = scenario_result.preference_score - self.baseline_result.preference_score

            factual_explanations.append(
                f"Solver reached status '{scenario_result.solver_status.value}' in {scenario_result.wall_time_seconds}s."
            )
            factual_explanations.append(
                f"Total assigned active applicants changed by {net_assign:+d} (from {self.baseline_result.total_assigned} to {scenario_result.total_assigned})."
            )
            factual_explanations.append(
                f"Overall preference satisfaction score changed by {pref_delta:+d} (from {self.baseline_result.preference_score} to {scenario_result.preference_score})."
            )
            factual_explanations.append(
                f"A total of {reassignment_count} applicant reassignments occurred relative to the baseline allocation."
            )

            # Specific scenario observations
            if scenario_type == "withdrawal":
                w_id = context.get("withdrawn_id")
                w_app = self.applicants.get(w_id)
                base_prog_id = base_assign.get(w_id)
                if base_prog_id:
                    base_prog = self.programs.get(base_prog_id)
                    factual_explanations.append(
                        f"Applicant {w_app.name if w_app else w_id} withdrew, releasing 1 seat in {base_prog.name if base_prog else base_prog_id}."
                    )
                else:
                    factual_explanations.append(
                        f"Applicant {w_app.name if w_app else w_id} was unassigned in baseline, so no occupied seat was released."
                    )

            elif scenario_type == "capacity_change":
                p_id = context.get("program_id")
                p_name = self.programs[p_id].name if p_id in self.programs else p_id
                old_cap = context.get("old_capacity")
                new_cap = context.get("new_capacity")
                factual_explanations.append(
                    f"Program {p_name} capacity adjusted from {old_cap} to {new_cap} ({new_cap - old_cap:+d} seats)."
                )

            elif scenario_type == "appeal":
                app_id = context.get("applicant_id")
                req_p = context.get("program_id")
                app_obj = self.applicants.get(app_id)
                p_obj = self.programs.get(req_p)
                factual_explanations.append(
                    f"Appeal placement enforced: Applicant {app_obj.name if app_obj else app_id} assigned to {p_obj.name if p_obj else req_p}."
                )

        val = scenario_result.validation_result

        return ImpactReport(
            scenario_type=scenario_type,
            scenario_title=scenario_title,
            baseline_run_id=self.baseline_result.run_id,
            scenario_run_id=scenario_result.run_id,
            solver_status=scenario_result.solver_status,
            is_feasible=is_feasible,
            total_assigned_before=self.baseline_result.total_assigned,
            total_assigned_after=scenario_result.total_assigned,
            net_assigned_change=scenario_result.total_assigned - self.baseline_result.total_assigned,
            pref_score_before=self.baseline_result.preference_score,
            pref_score_after=scenario_result.preference_score,
            pref_score_change=scenario_result.preference_score - self.baseline_result.preference_score,
            reassignment_count=reassignment_count,
            affected_count=affected_count,
            changes=changes,
            capacity_diffs=capacity_diffs,
            factual_explanations=factual_explanations,
            validation_status=val.is_valid if val else False,
            validation_errors=val.errors if val else [],
        )


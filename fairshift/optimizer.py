"""Mathematical allocation engine using Google OR-Tools CP-SAT.

Enforces:
1. At most one program per applicant.
2. Program capacities cannot be exceeded.
3. Applicants only assigned to programs for which they are eligible.
4. Withdrawn applicants receive no assignment.
5. Scenario conditions (e.g. appeal placement) are strictly enforced.

Optimization objectives (Lexicographic or Weighted):
1. Maximize active applicants assigned.
2. Maximize preference satisfaction score.
3. Preserve valid existing assignments and minimize reassignments (stability).
"""

from __future__ import annotations
import time
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

from ortools.sat.python import cp_model

from .models import (
    Applicant,
    Program,
    ScenarioCondition,
    OptimizationConfig,
    AllocationResult,
    SolverStatusEnum,
)
from .validator import AllocationValidator


class AllocationOptimizer:
    """Core allocation engine powered by Google OR-Tools CP-SAT."""

    def __init__(
        self,
        applicants: List[Applicant],
        programs: List[Program],
        baseline_assignments: Optional[Dict[str, str]] = None,
        config: Optional[OptimizationConfig] = None,
    ):
        self.applicants = {a.applicant_id: a for a in applicants}
        self.programs = {p.program_id: p for p in programs}
        self.baseline_assignments = baseline_assignments or {}
        self.config = config or OptimizationConfig()

    def get_preference_score(self, applicant: Applicant, program_id: str) -> int:
        """Calculate preference points for assigning applicant to program."""
        rank = applicant.preference_rank(program_id)
        if rank is None:
            return 1  # Minimal score for unranked but eligible
        points_list = self.config.points_per_rank
        if 1 <= rank <= len(points_list):
            return points_list[rank - 1]
        # For lower ranks beyond list, decaying score
        return max(1, points_list[-1] - (rank - len(points_list)) * 2)

    def solve(
        self,
        scenario_type: str = "initial",
        scenario_description: str = "Standard allocation run",
        scenario_conditions: Optional[List[ScenarioCondition]] = None,
        baseline_run_id: Optional[str] = None,
    ) -> AllocationResult:
        """Solve allocation problem using CP-SAT.
        
        Supports staged lexicographic optimization (assigned -> preferences -> stability)
        or weighted single-stage optimization based on config.
        """
        start_time = time.perf_counter()
        scenario_conditions = scenario_conditions or []

        if self.config.priority_mode == "lexicographic":
            result = self._solve_lexicographic(
                scenario_type=scenario_type,
                scenario_description=scenario_description,
                scenario_conditions=scenario_conditions,
                baseline_run_id=baseline_run_id,
                start_time=start_time,
            )
        else:
            result = self._solve_weighted(
                scenario_type=scenario_type,
                scenario_description=scenario_description,
                scenario_conditions=scenario_conditions,
                baseline_run_id=baseline_run_id,
                start_time=start_time,
            )

        # Run independent validator on final proposed allocation
        validator = AllocationValidator(
            applicants=list(self.applicants.values()),
            programs=list(self.programs.values()),
            scenario_conditions=scenario_conditions,
        )
        validation_result = validator.validate(result.assignments)
        result.validation_result = validation_result

        # Calculate detailed quality & utilization measures
        self._enrich_result_metrics(result)
        return result

    def _build_base_model(
        self,
        scenario_conditions: List[ScenarioCondition],
    ) -> Tuple[cp_model.CpModel, Dict[Tuple[str, str], cp_model.IntVar], Dict[str, List[cp_model.IntVar]], Dict[str, List[cp_model.IntVar]]]:
        """Build base CP-SAT model with mandatory hard constraints."""
        model = cp_model.CpModel()
        x: Dict[Tuple[str, str], cp_model.IntVar] = {}
        app_vars: Dict[str, List[cp_model.IntVar]] = {a_id: [] for a_id in self.applicants}
        prog_vars: Dict[str, List[cp_model.IntVar]] = {p_id: [] for p_id in self.programs}

        # Create binary variables for eligible active applicants
        # Gather scenario forced placements so we allow them even if not in preferences
        forced_pairs = set()
        for cond in scenario_conditions:
            if cond.enforce and cond.requested_program_id:
                forced_pairs.add((cond.applicant_id, cond.requested_program_id))

        for app_id, app in self.applicants.items():
            if not app.is_active:
                # Withdrawn applicants cannot be assigned
                continue
            for prog_id, prog in self.programs.items():
                if not app.is_eligible_for(prog):
                    continue

                # Check preference requirement
                is_preferred = prog_id in app.preferences
                is_forced = (app_id, prog_id) in forced_pairs
                if self.config.only_assign_preferred and not is_preferred and not is_forced:
                    continue

                var = model.NewBoolVar(f"x_{app_id}_{prog_id}")
                x[(app_id, prog_id)] = var
                app_vars[app_id].append(var)
                prog_vars[prog_id].append(var)

        # Constraint 1: At most one program per applicant
        for app_id, vars_list in app_vars.items():
            if vars_list:
                model.Add(sum(vars_list) <= 1)

        # Constraint 2: Program capacities
        for prog_id, prog in self.programs.items():
            vars_list = prog_vars[prog_id]
            # If negative capacity is somehow provided, capacity is 0 (validator will also error)
            effective_cap = max(0, prog.capacity)
            model.Add(sum(vars_list) <= effective_cap)

        # Constraint 3: Scenario conditions (appeal placements or forced assignments)
        for cond in scenario_conditions:
            if not cond.enforce:
                continue
            app_id = cond.applicant_id
            req_prog = cond.requested_program_id

            if req_prog is None:
                # Force unassigned
                if app_vars.get(app_id):
                    model.Add(sum(app_vars[app_id]) == 0)
            else:
                if (app_id, req_prog) in x:
                    model.Add(x[(app_id, req_prog)] == 1)
                else:
                    # Infeasible scenario condition: applicant is ineligible, withdrawn, or prog invalid
                    # Add impossible constraint 0 == 1 to strictly enforce solver proves INFEASIBLE
                    model.Add(model.NewConstant(0) == 1)

        return model, x, app_vars, prog_vars

    def _solve_lexicographic(
        self,
        scenario_type: str,
        scenario_description: str,
        scenario_conditions: List[ScenarioCondition],
        baseline_run_id: Optional[str],
        start_time: float,
    ) -> AllocationResult:
        """Solve lexicographically in 3 strict stages:
        Stage 1: Maximize total assigned applicants (Z1)
        Stage 2: Maximize preference satisfaction score (Z2) subject to Z1 >= Z1*
        Stage 3: Maximize retained baseline assignments / minimize reassignments (Z3) subject to Z1 >= Z1*, Z2 >= Z2*
        """
        model, x, app_vars, prog_vars = self._build_base_model(scenario_conditions)

        # STAGE 1: Maximize Total Assignments
        total_assigned_expr = sum(x.values()) if x else 0
        model.Maximize(total_assigned_expr)

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self.config.time_limit_seconds
        solver.parameters.random_seed = self.config.random_seed

        status_stage1 = solver.Solve(model)
        status_enum = self._map_solver_status(status_stage1)

        if status_enum in (SolverStatusEnum.INFEASIBLE, SolverStatusEnum.UNKNOWN_OR_TIMEOUT):
            wall_time = time.perf_counter() - start_time
            return AllocationResult(
                run_id=f"run_{uuid.uuid4().hex[:8]}",
                timestamp=datetime.now().isoformat(),
                scenario_type=scenario_type,
                scenario_description=scenario_description,
                solver_status=status_enum,
                wall_time_seconds=round(wall_time, 4),
                unassigned_applicants=[a for a in self.applicants if self.applicants[a].is_active],
                baseline_run_id=baseline_run_id,
            )

        optimal_assigned_count = int(solver.ObjectiveValue()) if x else 0

        # STAGE 2: Maximize Preference Score subject to Z1 >= Z1*
        model.Add(total_assigned_expr >= optimal_assigned_count)
        
        pref_expr_terms = []
        for (app_id, prog_id), var in x.items():
            score = self.get_preference_score(self.applicants[app_id], prog_id)
            pref_expr_terms.append(score * var)
        pref_score_expr = sum(pref_expr_terms) if pref_expr_terms else 0

        model.Maximize(pref_score_expr)
        status_stage2 = solver.Solve(model)
        status_enum_stage2 = self._map_solver_status(status_stage2)

        optimal_pref_score = int(solver.ObjectiveValue()) if pref_expr_terms else 0

        # STAGE 3: Maximize Retained Baseline Assignments (Stability)
        retained_terms = []
        if self.baseline_assignments:
            model.Add(pref_score_expr >= optimal_pref_score)
            for (app_id, prog_id), var in x.items():
                if self.baseline_assignments.get(app_id) == prog_id:
                    retained_terms.append(var)

            if retained_terms:
                model.Maximize(sum(retained_terms))
                status_stage3 = solver.Solve(model)
                status_enum_final = self._map_solver_status(status_stage3)
            else:
                status_enum_final = status_enum_stage2
        else:
            status_enum_final = status_enum_stage2

        wall_time = time.perf_counter() - start_time

        # Extract assignments from solution
        assignments: Dict[str, str] = {}
        for (app_id, prog_id), var in x.items():
            if solver.Value(var) == 1:
                assignments[app_id] = prog_id

        unassigned = [
            a_id for a_id, app in self.applicants.items()
            if app.is_active and a_id not in assignments
        ]

        obj_measures = {
            "stage1_max_assigned": optimal_assigned_count,
            "stage2_max_preference_score": optimal_pref_score,
            "stage3_retained_baseline_count": sum(
                1 for a, p in assignments.items() if self.baseline_assignments.get(a) == p
            ),
            "priority_order": "1. Mandatory Rules -> 2. Max Assigned -> 3. Max Preferences -> 4. Max Stability",
        }

        return AllocationResult(
            run_id=f"run_{uuid.uuid4().hex[:8]}",
            timestamp=datetime.now().isoformat(),
            scenario_type=scenario_type,
            scenario_description=scenario_description,
            solver_status=status_enum_final,
            wall_time_seconds=round(wall_time, 4),
            assignments=assignments,
            unassigned_applicants=unassigned,
            total_assigned=len(assignments),
            objective_measures=obj_measures,
            baseline_run_id=baseline_run_id,
        )

    def _solve_weighted(
        self,
        scenario_type: str,
        scenario_description: str,
        scenario_conditions: List[ScenarioCondition],
        baseline_run_id: Optional[str],
        start_time: float,
    ) -> AllocationResult:
        """Single-stage weighted optimization with explicit priority weights."""
        model, x, app_vars, prog_vars = self._build_base_model(scenario_conditions)

        objective_terms = []
        w_assigned = self.config.weight_assigned
        w_pref = self.config.weight_preference
        w_stability = self.config.weight_stability

        for (app_id, prog_id), var in x.items():
            # Assigned weight
            coef = w_assigned
            # Preference score weight
            pref_score = self.get_preference_score(self.applicants[app_id], prog_id)
            coef += pref_score * w_pref
            # Baseline stability bonus
            if self.baseline_assignments.get(app_id) == prog_id:
                coef += w_stability
            objective_terms.append(coef * var)

        if objective_terms:
            model.Maximize(sum(objective_terms))

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self.config.time_limit_seconds
        solver.parameters.random_seed = self.config.random_seed

        status = solver.Solve(model)
        status_enum = self._map_solver_status(status)
        wall_time = time.perf_counter() - start_time

        if status_enum in (SolverStatusEnum.INFEASIBLE, SolverStatusEnum.UNKNOWN_OR_TIMEOUT):
            return AllocationResult(
                run_id=f"run_{uuid.uuid4().hex[:8]}",
                timestamp=datetime.now().isoformat(),
                scenario_type=scenario_type,
                scenario_description=scenario_description,
                solver_status=status_enum,
                wall_time_seconds=round(wall_time, 4),
                unassigned_applicants=[a for a in self.applicants if self.applicants[a].is_active],
                baseline_run_id=baseline_run_id,
            )

        assignments: Dict[str, str] = {}
        for (app_id, prog_id), var in x.items():
            if solver.Value(var) == 1:
                assignments[app_id] = prog_id

        unassigned = [
            a_id for a_id, app in self.applicants.items()
            if app.is_active and a_id not in assignments
        ]

        obj_measures = {
            "mode": "Weighted Single Stage",
            "weights": {
                "weight_assigned": w_assigned,
                "weight_preference": w_pref,
                "weight_stability": w_stability,
            },
            "total_objective_val": solver.ObjectiveValue() if objective_terms else 0,
        }

        return AllocationResult(
            run_id=f"run_{uuid.uuid4().hex[:8]}",
            timestamp=datetime.now().isoformat(),
            scenario_type=scenario_type,
            scenario_description=scenario_description,
            solver_status=status_enum,
            wall_time_seconds=round(wall_time, 4),
            assignments=assignments,
            unassigned_applicants=unassigned,
            total_assigned=len(assignments),
            objective_measures=obj_measures,
            baseline_run_id=baseline_run_id,
        )

    def _map_solver_status(self, status: int) -> SolverStatusEnum:
        """Map OR-Tools CpSolverStatus strictly to distinct domain statuses."""
        if status == cp_model.OPTIMAL:
            return SolverStatusEnum.OPTIMAL
        elif status == cp_model.FEASIBLE:
            return SolverStatusEnum.FEASIBLE
        elif status == cp_model.INFEASIBLE:
            return SolverStatusEnum.INFEASIBLE
        else:
            return SolverStatusEnum.UNKNOWN_OR_TIMEOUT

    def _enrich_result_metrics(self, result: AllocationResult) -> None:
        """Compute preference scores, rank distributions, and capacity utilizations."""
        rank_distribution: Dict[int, int] = {}
        total_pref_score = 0

        for app_id, prog_id in result.assignments.items():
            app = self.applicants.get(app_id)
            if app:
                rank = app.preference_rank(prog_id)
                r_key = rank if rank is not None else 999  # 999 for unranked
                rank_distribution[r_key] = rank_distribution.get(r_key, 0) + 1
                total_pref_score += self.get_preference_score(app, prog_id)

        result.preference_score = total_pref_score
        result.rank_distribution = dict(sorted(rank_distribution.items()))

        # Program capacity utilization
        prog_assigned: Dict[str, int] = {p_id: 0 for p_id in self.programs}
        for prog_id in result.assignments.values():
            if prog_id in prog_assigned:
                prog_assigned[prog_id] += 1

        capacity_util = {}
        for p_id, prog in self.programs.items():
            assigned = prog_assigned.get(p_id, 0)
            remaining = max(0, prog.capacity - assigned)
            pct = round((assigned / prog.capacity * 100), 1) if prog.capacity > 0 else 0.0
            capacity_util[p_id] = {
                "name": prog.name,
                "capacity": prog.capacity,
                "assigned": assigned,
                "remaining": remaining,
                "fill_percentage": pct,
            }
        result.capacity_utilization = capacity_util

        # Reassignments compared to baseline
        if self.baseline_assignments:
            reassignments = 0
            for app_id, base_prog in self.baseline_assignments.items():
                app = self.applicants.get(app_id)
                # Count if active applicant had a baseline assignment and was changed or lost it
                if app and app.is_active:
                    current_prog = result.assignments.get(app_id)
                    if current_prog != base_prog:
                        reassignments += 1
            result.reassignment_count = reassignments

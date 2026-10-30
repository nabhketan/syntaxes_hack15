"""Independent validator for FAIRSHIFT allocations.

This module is completely separate from the optimization solver.
It audits proposed allocations against mandatory business rules, eligibility,
capacity limits, withdrawal statuses, and scenario constraints.
"""

from __future__ import annotations
from typing import Dict, List, Optional, Any
from .models import Applicant, Program, ScenarioCondition, ValidationResult


class AllocationValidator:
    """Independent validator verifying every proposed allocation against business rules."""

    def __init__(
        self,
        applicants: List[Applicant],
        programs: List[Program],
        scenario_conditions: Optional[List[ScenarioCondition]] = None,
    ):
        self.applicants = {a.applicant_id: a for a in applicants}
        self.programs = {p.program_id: p for p in programs}
        self.scenario_conditions = scenario_conditions or []

    def validate(self, assignments: Dict[str, str]) -> ValidationResult:
        """Validate an assignment dictionary (applicant_id -> program_id).
        
        Returns a ValidationResult with is_valid boolean, list of error messages,
        warnings, and rule check statuses.
        """
        errors: List[str] = []
        warnings: List[str] = []
        checked_rules: Dict[str, bool] = {
            "unique_assignment": True,
            "program_capacity": True,
            "eligibility_met": True,
            "withdrawals_respected": True,
            "scenario_conditions_met": True,
            "valid_entity_references": True,
        }

        # 1. Check entity references and at-most-one assignment
        applicant_counts: Dict[str, int] = {}
        for app_id, prog_id in assignments.items():
            applicant_counts[app_id] = applicant_counts.get(app_id, 0) + 1
            if app_id not in self.applicants:
                errors.append(f"Invalid reference: Assignment references unknown applicant ID '{app_id}'.")
                checked_rules["valid_entity_references"] = False
            if prog_id not in self.programs:
                errors.append(f"Invalid reference: Applicant '{app_id}' assigned to unknown program ID '{prog_id}'.")
                checked_rules["valid_entity_references"] = False

        # At-most-one assignment check (dict inherently enforces 1 key, but check for count > 1 just in case)
        for app_id, count in applicant_counts.items():
            if count > 1:
                errors.append(f"At-most-one violation: Applicant '{app_id}' has {count} program assignments.")
                checked_rules["unique_assignment"] = False

        # 2. Check withdrawal status (withdrawn applicants cannot receive assignments)
        for app_id, prog_id in assignments.items():
            app = self.applicants.get(app_id)
            if app and app.is_withdrawn:
                errors.append(
                    f"Withdrawal violation: Withdrawn applicant '{app_id}' ({app.name}) is assigned to '{prog_id}'."
                )
                checked_rules["withdrawals_respected"] = False

        # 3. Check applicant eligibility
        for app_id, prog_id in assignments.items():
            app = self.applicants.get(app_id)
            prog = self.programs.get(prog_id)
            if app and prog:
                if not app.is_eligible_for(prog):
                    errors.append(
                        f"Eligibility violation: Applicant '{app_id}' ({app.name}) is NOT eligible for program "
                        f"'{prog_id}' ({prog.name}). Criteria: '{prog.eligibility_criteria}', Applicant eligibility: {app.eligibility}."
                    )
                    checked_rules["eligibility_met"] = False

        # 4. Check program capacities
        program_assigned_counts: Dict[str, int] = {p_id: 0 for p_id in self.programs}
        for app_id, prog_id in assignments.items():
            if prog_id in program_assigned_counts:
                program_assigned_counts[prog_id] += 1

        for prog_id, prog in self.programs.items():
            assigned = program_assigned_counts[prog_id]
            if prog.capacity < 0:
                errors.append(f"Capacity violation: Program '{prog_id}' has a negative capacity ({prog.capacity}).")
                checked_rules["program_capacity"] = False
            elif assigned > prog.capacity:
                errors.append(
                    f"Capacity violation: Program '{prog_id}' ({prog.name}) capacity exceeded! "
                    f"Capacity: {prog.capacity}, Assigned: {assigned} (Over capacity by {assigned - prog.capacity})."
                )
                checked_rules["program_capacity"] = False
            elif assigned == prog.capacity and prog.capacity > 0:
                pass  # Perfectly full
            elif assigned < prog.capacity:
                # Information/warning if program is under-enrolled
                pass

        # 5. Check scenario conditions (e.g. appeal placement)
        for cond in self.scenario_conditions:
            if not cond.enforce:
                continue
            app_id = cond.applicant_id
            req_prog = cond.requested_program_id

            if app_id not in self.applicants:
                errors.append(f"Scenario condition failed: Applicant '{app_id}' does not exist.")
                checked_rules["scenario_conditions_met"] = False
                continue

            actual_prog = assignments.get(app_id)
            if req_prog is None:
                # Required to be unassigned
                if actual_prog is not None:
                    errors.append(
                        f"Scenario condition violated: Applicant '{app_id}' was required to be unassigned, "
                        f"but was assigned to '{actual_prog}'."
                    )
                    checked_rules["scenario_conditions_met"] = False
            else:
                # Required to be assigned to req_prog
                if actual_prog != req_prog:
                    errors.append(
                        f"Scenario condition violated: Applicant '{app_id}' requested placement in '{req_prog}', "
                        f"but actual assignment was '{actual_prog or 'UNASSIGNED'}'."
                    )
                    checked_rules["scenario_conditions_met"] = False

        # 6. Warnings for preferences (non-fatal, but noteworthy)
        for app_id, prog_id in assignments.items():
            app = self.applicants.get(app_id)
            if app:
                rank = app.preference_rank(prog_id)
                if rank is None:
                    warnings.append(
                        f"Preference note: Applicant '{app_id}' was assigned to '{prog_id}', which was not in their ranked preferences."
                    )

        is_valid = len(errors) == 0
        metrics = {
            "total_assigned": len(assignments),
            "program_fill_counts": program_assigned_counts,
            "total_capacity": sum(p.capacity for p in self.programs.values()),
            "errors_count": len(errors),
            "warnings_count": len(warnings),
        }

        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            checked_rules=checked_rules,
            metrics=metrics,
        )


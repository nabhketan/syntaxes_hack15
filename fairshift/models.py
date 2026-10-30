"""Data models and structures for FAIRSHIFT."""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any


class SolverStatusEnum(str, Enum):
    OPTIMAL = "Optimal"
    FEASIBLE = "Feasible, not proven optimal"
    INFEASIBLE = "Infeasible"
    UNKNOWN_OR_TIMEOUT = "Unknown or timed out"


@dataclass
class Program:
    program_id: str
    name: str
    capacity: int
    eligibility_criteria: str = "ALL"  # e.g., "ALL" or comma-separated required tags
    description: str = ""

    def to_dict(self) -> dict:
        return {
            "program_id": self.program_id,
            "name": self.name,
            "capacity": self.capacity,
            "eligibility_criteria": self.eligibility_criteria,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Program:
        return cls(
            program_id=str(data["program_id"]).strip(),
            name=str(data.get("name", data["program_id"])).strip(),
            capacity=int(data["capacity"]),
            eligibility_criteria=str(data.get("eligibility_criteria", "ALL")).strip(),
            description=str(data.get("description", "")).strip(),
        )


@dataclass
class Applicant:
    applicant_id: str
    name: str
    eligibility: List[str] = field(default_factory=list)  # Program IDs or tags applicant is eligible for
    preferences: List[str] = field(default_factory=list)  # Ordered program IDs (choice 1, 2, ...)
    status: str = "active"  # "active" or "withdrawn"
    notes: str = ""

    @property
    def is_active(self) -> bool:
        return self.status.strip().lower() == "active"

    @property
    def is_withdrawn(self) -> bool:
        return self.status.strip().lower() == "withdrawn"

    def is_eligible_for(self, program: Program) -> bool:
        """Check if applicant is eligible for given program.
        Applicant is eligible if:
        1. Program criteria is 'ALL', or
        2. Program ID is explicitly in applicant's eligibility list, or
        3. Program eligibility criteria tag is in applicant's eligibility list.
        """
        if not self.is_active:
            return False
        criteria = program.eligibility_criteria.strip()
        if criteria.upper() == "ALL":
            return True
        elig_set = {e.strip() for e in self.eligibility if e.strip()}
        if program.program_id in elig_set:
            return True
        req_tags = {t.strip() for t in criteria.split(",") if t.strip()}
        if req_tags and req_tags.issubset(elig_set):
            return True
        return False

    def preference_rank(self, program_id: str) -> Optional[int]:
        """Return 1-based preference rank if program is in preferences, else None."""
        try:
            return self.preferences.index(program_id) + 1
        except ValueError:
            return None

    def to_dict(self) -> dict:
        return {
            "applicant_id": self.applicant_id,
            "name": self.name,
            "eligibility": ",".join(self.eligibility),
            "preferences": ",".join(self.preferences),
            "status": self.status,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Applicant:
        elig_raw = data.get("eligibility", "")
        if isinstance(elig_raw, list):
            elig = [str(x).strip() for x in elig_raw if str(x).strip()]
        else:
            elig = [x.strip() for x in str(elig_raw).split(",") if x.strip()]

        pref_raw = data.get("preferences", "")
        if isinstance(pref_raw, list):
            pref = [str(x).strip() for x in pref_raw if str(x).strip()]
        else:
            pref = [x.strip() for x in str(pref_raw).split(",") if x.strip()]

        return cls(
            applicant_id=str(data["applicant_id"]).strip(),
            name=str(data.get("name", data["applicant_id"])).strip(),
            eligibility=elig,
            preferences=pref,
            status=str(data.get("status", "active")).strip().lower(),
            notes=str(data.get("notes", "")).strip(),
        )


@dataclass
class ScenarioCondition:
    applicant_id: str
    requested_program_id: Optional[str]  # None means applicant forced unassigned
    enforce: bool = True
    description: str = ""


@dataclass
class OptimizationConfig:
    priority_mode: str = "lexicographic"  # "lexicographic" or "weighted"
    # Lexicographic stages:
    # Stage 1: Maximize total assigned active applicants
    # Stage 2: Maximize preference satisfaction score
    # Stage 3: Minimize reassignments from baseline (stability)
    
    # Linear preference weights: Rank 1 gets max points, rank 2 gets less...
    # For K preferences: points = (max_rank - rank + 1) * weight
    points_per_rank: List[int] = field(default_factory=lambda: [100, 70, 45, 25, 10])
    
    # If True, applicants can only be assigned to programs they ranked in their preferences
    only_assign_preferred: bool = True

    # For weighted mode:
    weight_assigned: int = 100000
    weight_preference: int = 1000
    weight_stability: int = 50000
    
    # Solver options
    time_limit_seconds: float = 15.0
    random_seed: int = 42


@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    checked_rules: Dict[str, bool] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AllocationResult:
    run_id: str
    timestamp: str
    scenario_type: str  # "initial", "withdrawal", "capacity_change", "appeal"
    scenario_description: str
    solver_status: SolverStatusEnum
    wall_time_seconds: float
    assignments: Dict[str, str] = field(default_factory=dict)  # applicant_id -> program_id
    unassigned_applicants: List[str] = field(default_factory=list)
    total_assigned: int = 0
    preference_score: int = 0
    reassignment_count: int = 0  # relative to baseline if provided
    rank_distribution: Dict[int, int] = field(default_factory=dict)  # rank -> count
    capacity_utilization: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # program_id -> stats
    objective_measures: Dict[str, Any] = field(default_factory=dict)
    validation_result: Optional[ValidationResult] = None
    baseline_run_id: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "scenario_type": self.scenario_type,
            "scenario_description": self.scenario_description,
            "solver_status": self.solver_status.value,
            "wall_time_seconds": self.wall_time_seconds,
            "assignments": self.assignments,
            "unassigned_applicants": self.unassigned_applicants,
            "total_assigned": self.total_assigned,
            "preference_score": self.preference_score,
            "reassignment_count": self.reassignment_count,
            "rank_distribution": self.rank_distribution,
            "capacity_utilization": self.capacity_utilization,
            "objective_measures": self.objective_measures,
            "is_valid": self.validation_result.is_valid if self.validation_result else False,
            "baseline_run_id": self.baseline_run_id,
        }

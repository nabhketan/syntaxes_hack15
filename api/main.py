"""FAIRSHIFT FastAPI Transport Layer.

Exposes REST API endpoints connecting the React frontend to the existing
Python allocation engine, validator, scenario analyzer, and SQLite persistence.
DOES NOT IMPLEMENT OR ALTER ANY BUSINESS OR ALLOCATION RULES.
"""

from __future__ import annotations
import io
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from fairshift.models import (
    Applicant,
    Program,
    OptimizationConfig,
    SolverStatusEnum,
    AllocationResult,
    ValidationResult,
    ScenarioCondition,
)
from fairshift.optimizer import AllocationOptimizer
from fairshift.validator import AllocationValidator
from fairshift.analyzer import ScenarioAnalyzer, ImpactReport
from fairshift.database import AllocationDatabase, DEFAULT_DB_PATH
from fairshift.data_manager import (
    generate_sample_dataset,
    validate_dataset,
    export_applicants_to_dataframe,
    export_programs_to_dataframe,
    import_applicants_from_file,
    import_programs_from_file,
    add_program,
    replace_program,
    remove_program,
    add_applicant,
    replace_applicant,
    remove_applicant,
    prune_invalid_preferences,
    reconcile_applicant_preferences,
    auto_assign_valid_preferences,
    SAMPLE_PROGRAMS,
)

app = FastAPI(
    title="FAIRSHIFT API",
    description="Transport API for FAIRSHIFT Training Program Seat Allocation Engine",
    version="2.0.0",
)

# Configure local development CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins for local Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Persistent database instance using standard path
db = AllocationDatabase(DEFAULT_DB_PATH)


# --- Helper Functions ---

def get_current_dataset():
    """Retrieve current applicants and programs from SQLite database."""
    if not db.has_active_dataset():
        apps, progs = generate_sample_dataset(applicant_count=200, seed=42)
        db.save_active_dataset(applicants=apps, programs=progs)
        db.log_audit_event("DATASET_INITIALIZED", "Seeded default dataset into SQLite.")
        return apps, progs
    return db.load_active_dataset()


def serialize_allocation_result(res: AllocationResult) -> Dict[str, Any]:
    d = asdict(res)
    d["solver_status"] = res.solver_status.value
    if res.validation_result:
        d["validation_result"] = asdict(res.validation_result)
    return d


def serialize_impact_report(rep: ImpactReport) -> Dict[str, Any]:
    d = asdict(rep)
    d["solver_status"] = rep.solver_status.value
    return d


def reconstruct_allocation_result_from_dict(data: Dict[str, Any]) -> AllocationResult:
    solver_status = SolverStatusEnum(data.get("solver_status", "Optimal"))
    val_data = data.get("validation_result")
    val_res = None
    if val_data:
        val_res = ValidationResult(
            is_valid=val_data.get("is_valid", True),
            checked_rules=val_data.get("checked_rules", {}),
            errors=val_data.get("errors", []),
            warnings=val_data.get("warnings", []),
            metrics=val_data.get("metrics", {}),
        )

    rank_dist = {}
    for k, v in data.get("rank_distribution", {}).items():
        try:
            rank_dist[int(k)] = int(v)
        except (ValueError, TypeError):
            pass

    return AllocationResult(
        run_id=data.get("run_id", ""),
        timestamp=data.get("timestamp", ""),
        scenario_type=data.get("scenario_type", "custom"),
        scenario_description=data.get("scenario_description", ""),
        solver_status=solver_status,
        wall_time_seconds=float(data.get("wall_time_seconds", 0.0)),
        assignments=data.get("assignments", {}),
        unassigned_applicants=data.get("unassigned_applicants", []),
        total_assigned=int(data.get("total_assigned", len(data.get("assignments", {})))),
        preference_score=int(data.get("preference_score", 0)),
        reassignment_count=int(data.get("reassignment_count", 0)),
        rank_distribution=rank_dist,
        capacity_utilization=data.get("capacity_utilization", {}),
        objective_measures=data.get("objective_measures", {}),
        validation_result=val_res,
        baseline_run_id=data.get("baseline_run_id"),
    )


def get_active_baseline_result() -> Optional[AllocationResult]:
    run_id = db.get_active_baseline_run_id()
    if not run_id:
        return None
    run_data = db.get_run(run_id)
    if not run_data:
        return None
    return reconstruct_allocation_result_from_dict({
        "run_id": run_data["run_id"],
        "timestamp": run_data["timestamp"],
        "scenario_type": run_data["scenario_type"],
        "scenario_description": run_data["scenario_description"],
        "solver_status": run_data["solver_status"],
        "wall_time_seconds": run_data["wall_time_seconds"],
        "assignments": run_data.get("assignments_map", {}),
        "total_assigned": run_data["total_assigned"],
        "preference_score": run_data["preference_score"],
        "reassignment_count": run_data["reassignment_count"],
        "rank_distribution": run_data.get("rank_distribution", {}),
        "capacity_utilization": run_data.get("capacity_utilization", {}),
        "objective_measures": run_data.get("objective_measures", {}),
        "validation_result": run_data.get("validation", {}),
    })


# --- Pydantic Request Models ---

class ProgramCreateRequest(BaseModel):
    program_id: str
    name: str
    capacity: int
    eligibility_criteria: str = "ALL"
    description: str = ""


class ProgramUpdateRequest(BaseModel):
    name: str
    capacity: int
    eligibility_criteria: str = "ALL"
    description: str = ""
    new_program_id: Optional[str] = None
    cascade_preference_rename: bool = True


class ApplicantCreateRequest(BaseModel):
    applicant_id: str
    name: str
    eligibility: List[str] = Field(default_factory=lambda: ["ALL"])
    preferences: List[str] = Field(default_factory=list)
    status: str = "active"
    notes: str = ""


class ApplicantUpdateRequest(BaseModel):
    name: str
    eligibility: List[str] = Field(default_factory=lambda: ["ALL"])
    preferences: List[str] = Field(default_factory=list)
    status: str = "active"
    notes: str = ""
    new_applicant_id: Optional[str] = None


class ConfigModel(BaseModel):
    priority_mode: str = "lexicographic"
    only_assign_preferred: bool = True
    time_limit_seconds: float = 15.0
    points_per_rank: List[int] = Field(default_factory=lambda: [100, 70, 45, 25, 10])
    weight_assigned: int = 100000
    weight_preference: int = 1000
    weight_stability: int = 50000


class SolveRequest(BaseModel):
    config: ConfigModel = Field(default_factory=ConfigModel)
    scenario_type: str = "initial"
    scenario_description: str = "Initial full allocation run"


class SaveBaselineRequest(BaseModel):
    result: Dict[str, Any]


class WithdrawalScenarioRequest(BaseModel):
    applicant_id: str
    config: ConfigModel = Field(default_factory=ConfigModel)


class CommitWithdrawalRequest(BaseModel):
    applicant_id: str
    scenario_result: Dict[str, Any]


class CapacityScenarioRequest(BaseModel):
    program_id: str
    new_capacity: int
    config: ConfigModel = Field(default_factory=ConfigModel)


class CommitCapacityRequest(BaseModel):
    program_id: str
    new_capacity: int
    scenario_result: Dict[str, Any]


class AppealScenarioRequest(BaseModel):
    applicant_id: str
    requested_program_id: str
    config: ConfigModel = Field(default_factory=ConfigModel)


class GrantAppealRequest(BaseModel):
    scenario_result: Dict[str, Any]


# =========================================================================
# 1. System, Status, Baseline & Dashboard
# =========================================================================

@app.get("/api/status")
def get_system_status():
    apps, progs = get_current_dataset()
    active_count = sum(1 for a in apps if a.is_active)
    withdrawn_count = sum(1 for a in apps if a.is_withdrawn)
    total_capacity = sum(p.capacity for p in progs)
    baseline = get_active_baseline_result()

    return {
        "total_applicants": len(apps),
        "active_applicants": active_count,
        "withdrawn_applicants": withdrawn_count,
        "total_programs": len(progs),
        "total_capacity": total_capacity,
        "has_baseline": baseline is not None,
        "baseline_summary": {
            "run_id": baseline.run_id if baseline else None,
            "total_assigned": baseline.total_assigned if baseline else 0,
            "solver_status": baseline.solver_status.value if baseline else None,
            "wall_time_seconds": baseline.wall_time_seconds if baseline else 0.0,
            "preference_score": baseline.preference_score if baseline else 0,
        } if baseline else None,
    }


@app.get("/api/baseline")
def get_baseline():
    baseline = get_active_baseline_result()
    if not baseline:
        return {"baseline": None}
    return {"baseline": serialize_allocation_result(baseline)}


@app.post("/api/baseline/set")
def set_active_baseline(run_id: str = Query(...)):
    success = db.set_active_baseline(run_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found.")
    db.log_audit_event("BASELINE_RESTORED", f"Restored run '{run_id}' as active baseline.")
    return {"success": True, "active_baseline_run_id": run_id}


@app.post("/api/dataset/reset")
def reset_dataset():
    apps, progs = generate_sample_dataset(200, seed=42)
    db.save_active_dataset(applicants=apps, programs=progs)
    db.log_audit_event("SAMPLE_DATA_RESET", "Reset dataset to 200 sample applicants and 10 programs.")
    return {"success": True, "message": "Sample data reset successfully and permanently saved."}


# =========================================================================
# 2. Programs Management
# =========================================================================

@app.get("/api/programs")
def get_programs():
    _, progs = get_current_dataset()
    return {"programs": [asdict(p) for p in progs]}


@app.post("/api/programs")
def create_program(req: ProgramCreateRequest):
    apps, progs = get_current_dataset()
    new_p = Program(
        program_id=req.program_id.strip(),
        name=req.name.strip(),
        capacity=req.capacity,
        eligibility_criteria=req.eligibility_criteria.strip() or "ALL",
        description=req.description.strip(),
    )

    db.push_undo_state(
        action_type="ADD_PROGRAM",
        action_description=f"Added program '{new_p.program_id}' ({new_p.name})",
        applicants=apps,
        programs=progs,
    )

    success, msg = add_program(progs, new_p)
    if not success:
        db.pop_undo_state()
        raise HTTPException(status_code=400, detail=msg)

    db.save_programs(progs)
    db.log_audit_event("PROGRAM_ADDED", msg)
    return {"success": True, "message": msg, "program": asdict(new_p)}


@app.put("/api/programs/{program_id}")
def update_program(program_id: str, req: ProgramUpdateRequest):
    apps, progs = get_current_dataset()
    target_id = req.new_program_id.strip() if req.new_program_id else program_id
    new_p = Program(
        program_id=target_id,
        name=req.name.strip(),
        capacity=req.capacity,
        eligibility_criteria=req.eligibility_criteria.strip() or "ALL",
        description=req.description.strip(),
    )

    db.push_undo_state(
        action_type="REPLACE_PROGRAM",
        action_description=f"Replaced program '{program_id}'",
        applicants=apps,
        programs=progs,
    )

    success, msg = replace_program(
        programs=progs,
        old_program_id=program_id,
        new_program=new_p,
        applicants=apps,
        update_applicant_preferences=req.cascade_preference_rename,
    )

    if not success:
        db.pop_undo_state()
        raise HTTPException(status_code=400, detail=msg)

    db.save_programs(progs)
    if req.cascade_preference_rename:
        db.save_applicants(apps)
    db.log_audit_event("PROGRAM_REPLACED", msg)
    return {"success": True, "message": msg, "program": asdict(new_p)}


@app.delete("/api/programs/{program_id}")
def delete_program(program_id: str, clean_preferences: bool = Query(True)):
    apps, progs = get_current_dataset()

    target_prog = next((p for p in progs if p.program_id == program_id), None)
    if not target_prog:
        raise HTTPException(status_code=404, detail=f"Program '{program_id}' not found.")

    db.push_undo_state(
        action_type="REMOVE_PROGRAM",
        action_description=f"Removed program '{program_id}' ({target_prog.name})",
        applicants=apps,
        programs=progs,
    )

    success, msg, affected = remove_program(
        programs=progs,
        program_id=program_id,
        applicants=apps,
        clean_preferences=clean_preferences,
    )

    if not success:
        db.pop_undo_state()
        raise HTTPException(status_code=400, detail=msg)

    db.save_programs(progs)
    if clean_preferences:
        db.save_applicants(apps)
    db.log_audit_event("PROGRAM_REMOVED", msg)
    return {"success": True, "message": msg, "affected_applicants": affected}


@app.post("/api/programs/import")
async def import_programs(
    file: UploadFile = File(...),
    import_mode: str = Form("replace"),  # "replace" or "merge"
    reconcile_preferences: bool = Form(True),
    clear_applicants: bool = Form(False),
):
    apps, progs = get_current_dataset()
    contents = await file.read()
    filename = file.filename or "programs.xlsx"

    new_progs, errors = import_programs_from_file(contents, filename)
    if errors:
        raise HTTPException(status_code=400, detail={"errors": errors})

    file_ext = ".xlsx" if filename.endswith((".xlsx", ".xls")) else ".csv"
    action_type = "IMPORT_PROGRAMS_XLSX" if file_ext == ".xlsx" else "IMPORT_PROGRAMS_CSV"
    desc_mode = "Replace all" if import_mode == "replace" else "Merge"
    db.push_undo_state(
        action_type=action_type,
        action_description=f"Imported programs from {filename} ({desc_mode})",
        applicants=apps,
        programs=progs,
    )

    old_progs = list(progs)
    if import_mode == "replace":
        progs = new_progs
        if clear_applicants:
            apps = []
            db.save_applicants([])
            desc = f"Replaced all programs with {len(new_progs)} imported programs from {filename} and cleared applicants."
        elif reconcile_preferences:
            remapped_cnt, pruned_cnt = reconcile_applicant_preferences(
                applicants=apps,
                old_programs=old_progs,
                new_programs=new_progs,
            )
            extra_pruned = prune_invalid_preferences(apps, new_progs)
            db.save_applicants(apps)
            desc = (
                f"Replaced all programs with {len(new_progs)} imported programs from {filename} "
                f"(reconciled {remapped_cnt} applicants, pruned {pruned_cnt + extra_pruned} obsolete preferences)."
            )
        else:
            desc = f"Replaced all programs with {len(new_progs)} imported programs from {filename}."
    else:
        count_added = 0
        count_replaced = 0
        for np in new_progs:
            existing_idx = next((i for i, p in enumerate(progs) if p.program_id == np.program_id), None)
            if existing_idx is not None:
                progs[existing_idx] = np
                count_replaced += 1
            else:
                progs.append(np)
                count_added += 1
        if reconcile_preferences:
            pruned_cnt = prune_invalid_preferences(apps, progs)
            if pruned_cnt > 0:
                db.save_applicants(apps)
        desc = f"Imported from {filename}: Added {count_added}, updated/replaced {count_replaced} programs."

    db.save_programs(progs)
    db.log_audit_event("PROGRAMS_IMPORTED", desc)
    return {"success": True, "message": desc, "programs_count": len(progs)}


@app.get("/api/programs/export/csv")
def export_programs_csv():
    _, progs = get_current_dataset()
    df = export_programs_to_dataframe(progs)
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return PlainTextResponse(
        buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=programs.csv"},
    )


# =========================================================================
# 3. Applicants Management
# =========================================================================

@app.get("/api/applicants")
def get_applicants(
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
):
    apps, _ = get_current_dataset()
    result = apps
    if status == "active":
        result = [a for a in result if a.is_active]
    elif status == "withdrawn":
        result = [a for a in result if a.is_withdrawn]

    if search:
        s = search.strip().lower()
        result = [
            a for a in result
            if s in a.applicant_id.lower()
            or s in a.name.lower()
            or any(s in p.lower() for p in a.preferences)
            or any(s in e.lower() for e in a.eligibility)
        ]

    return {"applicants": [asdict(a) for a in result], "total": len(apps)}


@app.post("/api/applicants")
def create_applicant(req: ApplicantCreateRequest):
    apps, progs = get_current_dataset()
    new_a = Applicant(
        applicant_id=req.applicant_id.strip(),
        name=req.name.strip(),
        eligibility=[e.strip() for e in req.eligibility if e.strip()] or ["ALL"],
        preferences=[p.strip() for p in req.preferences if p.strip()],
        status=req.status.strip().lower() or "active",
        notes=req.notes.strip(),
    )

    db.push_undo_state(
        action_type="ADD_APPLICANT",
        action_description=f"Added applicant '{new_a.applicant_id}' ({new_a.name})",
        applicants=apps,
        programs=progs,
    )

    success, msg = add_applicant(apps, new_a)
    if not success:
        db.pop_undo_state()
        raise HTTPException(status_code=400, detail=msg)

    db.save_applicants(apps)
    db.log_audit_event("APPLICANT_ADDED", msg)
    return {"success": True, "message": msg, "applicant": asdict(new_a)}


@app.put("/api/applicants/{applicant_id}")
def update_applicant(applicant_id: str, req: ApplicantUpdateRequest):
    apps, progs = get_current_dataset()
    target_id = req.new_applicant_id.strip() if req.new_applicant_id else applicant_id
    replacement_a = Applicant(
        applicant_id=target_id,
        name=req.name.strip(),
        eligibility=[e.strip() for e in req.eligibility if e.strip()] or ["ALL"],
        preferences=[p.strip() for p in req.preferences if p.strip()],
        status=req.status.strip().lower() or "active",
        notes=req.notes.strip(),
    )

    db.push_undo_state(
        action_type="REPLACE_APPLICANT",
        action_description=f"Replaced applicant '{applicant_id}' ({req.name})",
        applicants=apps,
        programs=progs,
    )

    success, msg = replace_applicant(
        applicants=apps,
        old_applicant_id=applicant_id,
        new_applicant=replacement_a,
    )

    if not success:
        db.pop_undo_state()
        raise HTTPException(status_code=400, detail=msg)

    db.save_applicants(apps)
    db.log_audit_event("APPLICANT_REPLACED", msg)
    return {"success": True, "message": msg, "applicant": asdict(replacement_a)}


@app.delete("/api/applicants/{applicant_id}")
def delete_applicant(applicant_id: str):
    apps, progs = get_current_dataset()

    target_app = next((a for a in apps if a.applicant_id == applicant_id), None)
    if not target_app:
        raise HTTPException(status_code=404, detail=f"Applicant '{applicant_id}' not found.")

    db.push_undo_state(
        action_type="REMOVE_APPLICANT",
        action_description=f"Removed applicant '{applicant_id}' ({target_app.name})",
        applicants=apps,
        programs=progs,
    )

    success, msg = remove_applicant(apps, applicant_id)
    if not success:
        db.pop_undo_state()
        raise HTTPException(status_code=400, detail=msg)

    db.save_applicants(apps)
    db.log_audit_event("APPLICANT_REMOVED", msg)
    return {"success": True, "message": msg}


@app.post("/api/applicants/import")
async def import_applicants(
    file: UploadFile = File(...),
    import_mode: str = Form("replace"),  # "replace" or "merge"
    clean_invalid_preferences: bool = Form(True),
):
    apps, progs = get_current_dataset()
    contents = await file.read()
    filename = file.filename or "applicants.xlsx"

    new_apps, errors = import_applicants_from_file(contents, filename)
    if errors:
        raise HTTPException(status_code=400, detail={"errors": errors})

    file_ext = ".xlsx" if filename.endswith((".xlsx", ".xls")) else ".csv"
    action_type = "IMPORT_APPLICANTS_XLSX" if file_ext == ".xlsx" else "IMPORT_APPLICANTS_CSV"
    desc_mode = "Replace all" if import_mode == "replace" else "Merge"

    db.push_undo_state(
        action_type=action_type,
        action_description=f"Imported applicants from {filename} ({desc_mode})",
        applicants=apps,
        programs=progs,
    )

    if import_mode == "replace":
        apps = new_apps
        desc = f"Replaced all applicants with {len(new_apps)} imported applicants from {filename}."
    else:
        count_added = 0
        count_replaced = 0
        for na in new_apps:
            existing_idx = next((i for i, a in enumerate(apps) if a.applicant_id == na.applicant_id), None)
            if existing_idx is not None:
                apps[existing_idx] = na
                count_replaced += 1
            else:
                apps.append(na)
                count_added += 1
        desc = f"Imported from {filename}: Added {count_added}, updated/replaced {count_replaced} applicants."

    if clean_invalid_preferences:
        pruned_cnt = prune_invalid_preferences(apps, progs)
        if pruned_cnt > 0:
            desc += f" (pruned {pruned_cnt} unlisted program preferences)."

    db.save_applicants(apps)
    db.log_audit_event("APPLICANTS_IMPORTED", desc)
    return {"success": True, "message": desc, "applicants_count": len(apps)}


@app.get("/api/applicants/export/csv")
def export_applicants_csv():
    apps, _ = get_current_dataset()
    df = export_applicants_to_dataframe(apps)
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return PlainTextResponse(
        buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=applicants.csv"},
    )


# =========================================================================
# 4. Dataset Validation & Repair Actions
# =========================================================================

@app.get("/api/validation")
def get_validation_status():
    apps, progs = get_current_dataset()
    is_valid, errors, warnings = validate_dataset(apps, progs)
    unlisted_pref_count = sum(1 for e in errors if "ranks non-existent program" in e or "ranks unlisted" in e)

    return {
        "is_valid": is_valid,
        "errors": errors,
        "warnings": warnings,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "unlisted_pref_count": unlisted_pref_count,
    }


@app.post("/api/validation/auto-reconcile")
def action_auto_reconcile():
    apps, progs = get_current_dataset()
    db.push_undo_state(
        action_type="AUTO_RECONCILE",
        action_description="Auto-reconciled applicant preferences and eligibility",
        applicants=apps,
        programs=progs,
    )
    sample_p = [Program(**sp) for sp in SAMPLE_PROGRAMS]
    remapped, pruned = reconcile_applicant_preferences(apps, old_programs=sample_p, new_programs=progs)
    extra_pruned = prune_invalid_preferences(apps, progs)

    db.save_applicants(apps)
    msg = f"Reconciled {remapped} applicants, pruned {pruned + extra_pruned} invalid preferences."
    db.log_audit_event("AUTO_RECONCILE", msg)
    return {"success": True, "message": msg}


@app.post("/api/validation/prune-preferences")
def action_prune_preferences():
    apps, progs = get_current_dataset()
    db.push_undo_state(
        action_type="PRUNE_PREFERENCES",
        action_description="Pruned invalid program preferences",
        applicants=apps,
        programs=progs,
    )
    pruned = prune_invalid_preferences(apps, progs)
    db.save_applicants(apps)
    msg = f"Pruned {pruned} invalid preferences."
    db.log_audit_event("PREFERENCES_PRUNED", msg)
    return {"success": True, "message": msg, "pruned_count": pruned}


@app.post("/api/validation/auto-assign-preferences")
def action_auto_assign_preferences():
    apps, progs = get_current_dataset()
    db.push_undo_state(
        action_type="AUTO_ASSIGN_PREFS",
        action_description="Generated valid preferences for all applicants",
        applicants=apps,
        programs=progs,
    )
    updated = auto_assign_valid_preferences(apps, progs)
    db.save_applicants(apps)
    msg = f"Assigned valid preferences to {updated} applicants."
    db.log_audit_event("PREFERENCES_ASSIGNED", msg)
    return {"success": True, "message": msg, "updated_count": updated}


@app.post("/api/validation/clear-applicants")
def action_clear_applicants():
    apps, progs = get_current_dataset()
    db.push_undo_state(
        action_type="CLEAR_APPLICANTS",
        action_description="Cleared all applicants",
        applicants=apps,
        programs=progs,
    )
    db.save_applicants([])
    db.log_audit_event("APPLICANTS_CLEARED", "Cleared all applicants.")
    return {"success": True, "message": "Cleared all applicants."}


# =========================================================================
# 5. Multi-Level Undo
# =========================================================================

@app.get("/api/undo/status")
def get_undo_status():
    return {
        "can_undo": db.can_undo(),
        "undo_count": db.get_undo_count(),
        "last_action": db.get_last_undo_state(),
        "history": db.get_undo_history(limit=15),
    }


@app.post("/api/undo")
def trigger_undo():
    pop_res = db.pop_undo_state()
    if not pop_res:
        raise HTTPException(status_code=400, detail="Undo stack is empty.")
    apps, progs, undone_text = pop_res
    return {
        "success": True,
        "undone_action": undone_text,
        "applicants_count": len(apps),
        "programs_count": len(progs),
    }


# =========================================================================
# 6. Initial Allocation Engine
# =========================================================================

@app.post("/api/allocation/solve")
def solve_allocation(req: SolveRequest):
    apps, progs = get_current_dataset()
    opt_config = OptimizationConfig(
        priority_mode=req.config.priority_mode,
        points_per_rank=req.config.points_per_rank,
        only_assign_preferred=req.config.only_assign_preferred,
        time_limit_seconds=req.config.time_limit_seconds,
        weight_assigned=req.config.weight_assigned,
        weight_preference=req.config.weight_preference,
        weight_stability=req.config.weight_stability,
    )

    optimizer = AllocationOptimizer(applicants=apps, programs=progs, config=opt_config)
    res = optimizer.solve(
        scenario_type=req.scenario_type,
        scenario_description=req.scenario_description,
    )

    return {"result": serialize_allocation_result(res)}


@app.post("/api/allocation/save-baseline")
def save_allocation_as_baseline(req: SaveBaselineRequest):
    apps, progs = get_current_dataset()
    res = reconstruct_allocation_result_from_dict(req.result)

    db.save_allocation_run(
        result=res,
        applicants=apps,
        programs=progs,
        set_as_baseline=True,
    )
    run_id = res.run_id

    return {"success": True, "run_id": run_id, "message": f"Saved {run_id} as current active baseline."}


# =========================================================================
# 7. Scenario Analysis (Withdrawals, Capacities, Appeals)
# =========================================================================

@app.post("/api/scenarios/withdrawal")
def analyze_withdrawal(req: WithdrawalScenarioRequest):
    apps, progs = get_current_dataset()
    baseline = get_active_baseline_result()
    if not baseline:
        raise HTTPException(status_code=400, detail="No active baseline allocation set. Run and save an Initial Allocation first.")

    opt_config = OptimizationConfig(
        priority_mode=req.config.priority_mode,
        points_per_rank=req.config.points_per_rank,
        only_assign_preferred=req.config.only_assign_preferred,
        time_limit_seconds=req.config.time_limit_seconds,
    )

    analyzer = ScenarioAnalyzer(applicants=apps, programs=progs, baseline_result=baseline)
    scen_res, report = analyzer.analyze_withdrawal(req.applicant_id, config=opt_config)

    return {
        "scenario_result": serialize_allocation_result(scen_res),
        "impact_report": serialize_impact_report(report),
    }


@app.post("/api/scenarios/withdrawal/commit")
def commit_withdrawal(req: CommitWithdrawalRequest):
    apps, progs = get_current_dataset()
    withdrawn_id = req.applicant_id

    for a in apps:
        if a.applicant_id == withdrawn_id:
            a.status = "withdrawn"

    db.save_applicants(apps)
    scen_res = reconstruct_allocation_result_from_dict(req.scenario_result)
    db.save_allocation_run(
        result=scen_res,
        applicants=apps,
        programs=progs,
        set_as_baseline=True,
    )
    run_id = scen_res.run_id

    return {"success": True, "message": f"Applicant {withdrawn_id} permanently withdrawn. New baseline saved as {run_id}."}


@app.post("/api/scenarios/capacity")
def analyze_capacity_change(req: CapacityScenarioRequest):
    apps, progs = get_current_dataset()
    baseline = get_active_baseline_result()
    if not baseline:
        raise HTTPException(status_code=400, detail="No active baseline allocation set. Run and save an Initial Allocation first.")

    opt_config = OptimizationConfig(
        priority_mode=req.config.priority_mode,
        points_per_rank=req.config.points_per_rank,
        only_assign_preferred=req.config.only_assign_preferred,
        time_limit_seconds=req.config.time_limit_seconds,
    )

    analyzer = ScenarioAnalyzer(applicants=apps, programs=progs, baseline_result=baseline)
    scen_res, report = analyzer.analyze_capacity_change(
        program_id=req.program_id,
        new_capacity=req.new_capacity,
        config=opt_config,
    )

    return {
        "scenario_result": serialize_allocation_result(scen_res),
        "impact_report": serialize_impact_report(report),
    }


@app.post("/api/scenarios/capacity/commit")
def commit_capacity_change(req: CommitCapacityRequest):
    apps, progs = get_current_dataset()

    for p in progs:
        if p.program_id == req.program_id:
            p.capacity = req.new_capacity

    db.save_programs(progs)
    scen_res = reconstruct_allocation_result_from_dict(req.scenario_result)
    db.save_allocation_run(
        result=scen_res,
        applicants=apps,
        programs=progs,
        set_as_baseline=True,
    )
    run_id = scen_res.run_id

    return {"success": True, "message": f"Program {req.program_id} capacity permanently updated to {req.new_capacity}. New baseline {run_id}."}


@app.post("/api/scenarios/appeal")
def analyze_appeal(req: AppealScenarioRequest):
    apps, progs = get_current_dataset()
    baseline = get_active_baseline_result()
    if not baseline:
        raise HTTPException(status_code=400, detail="No active baseline allocation set. Run and save an Initial Allocation first.")

    opt_config = OptimizationConfig(
        priority_mode=req.config.priority_mode,
        points_per_rank=req.config.points_per_rank,
        only_assign_preferred=req.config.only_assign_preferred,
        time_limit_seconds=req.config.time_limit_seconds,
    )

    # DOES NOT OVERWRITE BASELINE
    analyzer = ScenarioAnalyzer(applicants=apps, programs=progs, baseline_result=baseline)
    scen_res, report = analyzer.analyze_appeal(
        applicant_id=req.applicant_id,
        requested_program_id=req.requested_program_id,
        config=opt_config,
    )

    return {
        "scenario_result": serialize_allocation_result(scen_res),
        "impact_report": serialize_impact_report(report),
    }


@app.post("/api/scenarios/appeal/grant")
def grant_appeal(req: GrantAppealRequest):
    apps, progs = get_current_dataset()
    scen_res = reconstruct_allocation_result_from_dict(req.scenario_result)
    db.save_allocation_run(
        result=scen_res,
        applicants=apps,
        programs=progs,
        set_as_baseline=True,
    )
    run_id = scen_res.run_id
    return {"success": True, "message": f"Appeal granted! New baseline saved as {run_id}."}


# =========================================================================
# 8. Allocation History & Audit Trail
# =========================================================================

@app.get("/api/history/runs")
def get_runs():
    runs = db.get_all_runs(limit=100)
    return {"runs": runs}


@app.get("/api/history/runs/{run_id}")
def get_run_detail(run_id: str):
    run_data = db.get_run(run_id)
    if not run_data:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found.")
    return {"run": run_data}


@app.get("/api/history/audit")
def get_audit_trail():
    events = db.get_audit_trail(limit=200)
    return {"audit_events": events}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)

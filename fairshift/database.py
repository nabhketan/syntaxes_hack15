"""SQLite database layer for FAIRSHIFT.

Persists:
- Allocation runs with solver status, wall times, objective measures, and validation results.
- Detailed assignments per run.
- Exact dataset snapshots for full auditability.
- Event audit trail for changes, approvals, and scenario evaluations.
"""

from __future__ import annotations
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

from .models import AllocationResult, Applicant, Program, SolverStatusEnum, ValidationResult


DEFAULT_DB_PATH = Path("fairshift_data.db")


class AllocationDatabase:
    """Manages SQLite persistence for FAIRSHIFT runs, assignments, and audit logs."""

    def __init__(self, db_path: Path = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self._init_db()

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Create necessary database tables if they do not exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Allocation Runs
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS allocation_runs (
                    run_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    scenario_type TEXT NOT NULL,
                    scenario_description TEXT NOT NULL,
                    solver_status TEXT NOT NULL,
                    wall_time_seconds REAL NOT NULL,
                    total_assigned INTEGER NOT NULL,
                    preference_score INTEGER NOT NULL,
                    reassignment_count INTEGER NOT NULL,
                    is_valid INTEGER NOT NULL,
                    validation_json TEXT,
                    objective_measures_json TEXT,
                    rank_distribution_json TEXT,
                    capacity_utilization_json TEXT,
                    baseline_run_id TEXT,
                    is_active_baseline INTEGER DEFAULT 0
                )
            """)

            # Assignments per run
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS assignments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    applicant_id TEXT NOT NULL,
                    applicant_name TEXT,
                    program_id TEXT NOT NULL,
                    preference_rank INTEGER,
                    FOREIGN KEY(run_id) REFERENCES allocation_runs(run_id)
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_assignments_run ON assignments(run_id)")

            # Snapshots of input data for exact reproducibility
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS dataset_snapshots (
                    run_id TEXT PRIMARY KEY,
                    applicants_json TEXT NOT NULL,
                    programs_json TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES allocation_runs(run_id)
                )
            """)

            # Audit events log
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    run_id TEXT,
                    description TEXT NOT NULL,
                    metadata_json TEXT
                )
            """)

            # Persistent active dataset tables for programs and applicants
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS active_programs (
                    program_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    capacity INTEGER NOT NULL,
                    eligibility_criteria TEXT DEFAULT 'ALL',
                    description TEXT DEFAULT ''
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS active_applicants (
                    applicant_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    status TEXT DEFAULT 'active',
                    eligibility TEXT DEFAULT 'ALL',
                    preferences TEXT DEFAULT '',
                    notes TEXT DEFAULT ''
                )
            """)

            # Undo history stack for reversing dataset additions, edits, removals, and imports
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS undo_stack (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    action_description TEXT NOT NULL,
                    applicants_json TEXT NOT NULL,
                    programs_json TEXT NOT NULL
                )
            """)
            conn.commit()

    def has_active_dataset(self) -> bool:
        """Check if persistent active programs and applicants tables have records."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM active_programs")
            prog_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM active_applicants")
            app_count = cursor.fetchone()[0]
            return prog_count > 0 or app_count > 0

    def load_active_dataset(self) -> Tuple[List[Applicant], List[Program]]:
        """Load persistent applicants and programs from SQLite."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM active_programs ORDER BY program_id ASC")
            prog_rows = cursor.fetchall()
            programs = [
                Program(
                    program_id=r["program_id"],
                    name=r["name"],
                    capacity=int(r["capacity"]),
                    eligibility_criteria=r["eligibility_criteria"] or "ALL",
                    description=r["description"] or "",
                )
                for r in prog_rows
            ]

            cursor.execute("SELECT * FROM active_applicants ORDER BY applicant_id ASC")
            app_rows = cursor.fetchall()
            applicants = []
            for r in app_rows:
                elig_raw = r["eligibility"] or ""
                elig = [x.strip() for x in elig_raw.split(",") if x.strip()]
                pref_raw = r["preferences"] or ""
                pref = [x.strip() for x in pref_raw.split(",") if x.strip()]
                applicants.append(
                    Applicant(
                        applicant_id=r["applicant_id"],
                        name=r["name"],
                        eligibility=elig,
                        preferences=pref,
                        status=r["status"] or "active",
                        notes=r["notes"] or "",
                    )
                )

            return applicants, programs

    def save_active_dataset(self, applicants: List[Applicant], programs: List[Program]) -> None:
        """Persist entire active applicants and programs dataset into SQLite."""
        self.save_programs(programs)
        self.save_applicants(applicants)

    def save_programs(self, programs: List[Program]) -> None:
        """Replace all rows in active_programs with given list of programs."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM active_programs")
            for p in programs:
                cursor.execute(
                    """
                    INSERT INTO active_programs (program_id, name, capacity, eligibility_criteria, description)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (p.program_id, p.name, p.capacity, p.eligibility_criteria, p.description),
                )
            conn.commit()

    def save_applicants(self, applicants: List[Applicant]) -> None:
        """Replace all rows in active_applicants with given list of applicants."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM active_applicants")
            for a in applicants:
                cursor.execute(
                    """
                    INSERT INTO active_applicants (applicant_id, name, status, eligibility, preferences, notes)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        a.applicant_id,
                        a.name,
                        a.status,
                        ",".join(a.eligibility),
                        ",".join(a.preferences),
                        a.notes,
                    ),
                )
            conn.commit()

    def push_undo_state(
        self,
        action_type: str,
        action_description: str,
        applicants: List[Applicant],
        programs: List[Program],
        max_depth: int = 30,
    ) -> None:
        """Save a snapshot of the current applicants and programs before a mutation occurs."""
        apps_data = [a.to_dict() for a in applicants]
        progs_data = [p.to_dict() for p in programs]
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO undo_stack (timestamp, action_type, action_description, applicants_json, programs_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    datetime.now().isoformat(),
                    action_type,
                    action_description,
                    json.dumps(apps_data),
                    json.dumps(progs_data),
                ),
            )
            # Prune old states beyond max_depth
            cursor.execute("SELECT COUNT(*) FROM undo_stack")
            count = cursor.fetchone()[0]
            if count > max_depth:
                cursor.execute(
                    """
                    DELETE FROM undo_stack WHERE id IN (
                        SELECT id FROM undo_stack ORDER BY id ASC LIMIT ?
                    )
                    """,
                    (count - max_depth,),
                )
            conn.commit()

    def can_undo(self) -> bool:
        """Check if an undo action is available."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM undo_stack")
            return cursor.fetchone()[0] > 0

    def get_undo_count(self) -> int:
        """Return the count of available undo steps."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM undo_stack")
            return cursor.fetchone()[0]

    def get_last_undo_state(self) -> Optional[Dict[str, Any]]:
        """Return metadata of the most recent undo point without popping it."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, timestamp, action_type, action_description
                FROM undo_stack
                ORDER BY id DESC
                LIMIT 1
                """
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_undo_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return recent undo history items."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, timestamp, action_type, action_description
                FROM undo_stack
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            )
            return [dict(r) for r in cursor.fetchall()]

    def pop_undo_state(self) -> Optional[Tuple[List[Applicant], List[Program], str]]:
        """Revert to the most recent snapshot in the undo stack.
        
        Restores both active_applicants and active_programs in SQLite and returns
        (restored_applicants, restored_programs, action_description).
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, action_type, action_description, applicants_json, programs_json
                FROM undo_stack
                ORDER BY id DESC
                LIMIT 1
                """
            )
            row = cursor.fetchone()
            if not row:
                return None

            undo_id = row["id"]
            action_desc = row["action_description"]
            apps_raw = json.loads(row["applicants_json"])
            progs_raw = json.loads(row["programs_json"])

            # Delete this state from the stack
            cursor.execute("DELETE FROM undo_stack WHERE id = ?", (undo_id,))
            conn.commit()

        # Reconstruct objects
        restored_programs = [Program.from_dict(p) for p in progs_raw]
        restored_applicants = [Applicant.from_dict(a) for a in apps_raw]

        # Save to active SQLite tables
        self.save_programs(restored_programs)
        self.save_applicants(restored_applicants)

        # Log audit event
        self.log_audit_event(
            event_type="ACTION_UNDONE",
            description=f"Undid action: {action_desc}. Dataset restored to previous state.",
            metadata={"undo_id": undo_id, "programs_count": len(restored_programs), "applicants_count": len(restored_applicants)},
        )

        return restored_applicants, restored_programs, action_desc

    def log_audit_event(
        self,
        event_type: str,
        description: str,
        run_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Append an entry to the audit log."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO audit_events (timestamp, event_type, run_id, description, metadata_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    datetime.now().isoformat(),
                    event_type,
                    run_id,
                    description,
                    json.dumps(metadata or {}, default=str),
                ),
            )
            conn.commit()

    def save_allocation_run(
        self,
        result: AllocationResult,
        applicants: Optional[List[Applicant]] = None,
        programs: Optional[List[Program]] = None,
        set_as_baseline: bool = False,
    ) -> None:
        """Save allocation run, assignments, input snapshot, and audit event."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # If setting as baseline, clear other baselines
            if set_as_baseline:
                cursor.execute("UPDATE allocation_runs SET is_active_baseline = 0")

            val_dict = {}
            if result.validation_result:
                val_dict = {
                    "is_valid": result.validation_result.is_valid,
                    "errors": result.validation_result.errors,
                    "warnings": result.validation_result.warnings,
                    "checked_rules": result.validation_result.checked_rules,
                }

            cursor.execute(
                """
                INSERT OR REPLACE INTO allocation_runs (
                    run_id, timestamp, scenario_type, scenario_description,
                    solver_status, wall_time_seconds, total_assigned,
                    preference_score, reassignment_count, is_valid,
                    validation_json, objective_measures_json, rank_distribution_json,
                    capacity_utilization_json, baseline_run_id, is_active_baseline
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result.run_id,
                    result.timestamp,
                    result.scenario_type,
                    result.scenario_description,
                    result.solver_status.value,
                    result.wall_time_seconds,
                    result.total_assigned,
                    result.preference_score,
                    result.reassignment_count,
                    1 if (result.validation_result and result.validation_result.is_valid) else 0,
                    json.dumps(val_dict),
                    json.dumps(result.objective_measures),
                    json.dumps(result.rank_distribution),
                    json.dumps(result.capacity_utilization),
                    result.baseline_run_id,
                    1 if set_as_baseline else 0,
                ),
            )

            # Insert assignments
            app_map = {a.applicant_id: a for a in applicants} if applicants else {}
            cursor.execute("DELETE FROM assignments WHERE run_id = ?", (result.run_id,))
            for app_id, prog_id in result.assignments.items():
                app = app_map.get(app_id)
                rank = app.preference_rank(prog_id) if app else None
                name = app.name if app else app_id
                cursor.execute(
                    """
                    INSERT INTO assignments (run_id, applicant_id, applicant_name, program_id, preference_rank)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (result.run_id, app_id, name, prog_id, rank),
                )

            # Insert dataset snapshot
            if applicants and programs:
                app_data = [a.to_dict() for a in applicants]
                prog_data = [p.to_dict() for p in programs]
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO dataset_snapshots (run_id, applicants_json, programs_json)
                    VALUES (?, ?, ?)
                    """,
                    (result.run_id, json.dumps(app_data), json.dumps(prog_data)),
                )

            conn.commit()

        # Audit event
        self.log_audit_event(
            event_type="RUN_SAVED",
            description=f"Saved run {result.run_id} ({result.scenario_type}): {result.scenario_description}. Status: {result.solver_status.value}",
            run_id=result.run_id,
            metadata={"set_as_baseline": set_as_baseline, "total_assigned": result.total_assigned},
        )

    def set_active_baseline(self, run_id: str) -> bool:
        """Mark a specific saved run as the current active baseline."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT run_id FROM allocation_runs WHERE run_id = ?", (run_id,))
            row = cursor.fetchone()
            if not row:
                return False
            cursor.execute("UPDATE allocation_runs SET is_active_baseline = 0")
            cursor.execute("UPDATE allocation_runs SET is_active_baseline = 1 WHERE run_id = ?", (run_id,))
            conn.commit()

        self.log_audit_event(
            event_type="BASELINE_SET",
            description=f"Run {run_id} set as active baseline allocation.",
            run_id=run_id,
        )
        return True

    def get_active_baseline_run_id(self) -> Optional[str]:
        """Fetch the run_id of current active baseline allocation."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT run_id FROM allocation_runs WHERE is_active_baseline = 1 LIMIT 1")
            row = cursor.fetchone()
            return row["run_id"] if row else None

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve full details of a saved run."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM allocation_runs WHERE run_id = ?", (run_id,))
            row = cursor.fetchone()
            if not row:
                return None
            res = dict(row)
            res["validation"] = json.loads(res.get("validation_json") or "{}")
            res["objective_measures"] = json.loads(res.get("objective_measures_json") or "{}")
            res["rank_distribution"] = json.loads(res.get("rank_distribution_json") or "{}")
            res["capacity_utilization"] = json.loads(res.get("capacity_utilization_json") or "{}")

            # Fetch assignments
            cursor.execute("SELECT * FROM assignments WHERE run_id = ?", (run_id,))
            res["assignments_list"] = [dict(r) for r in cursor.fetchall()]
            res["assignments_map"] = {r["applicant_id"]: r["program_id"] for r in res["assignments_list"]}
            return res

    def get_all_runs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """List past allocation runs for audit/history view."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT run_id, timestamp, scenario_type, scenario_description,
                       solver_status, wall_time_seconds, total_assigned,
                       preference_score, reassignment_count, is_valid,
                       is_active_baseline, baseline_run_id
                FROM allocation_runs
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (limit,),
            )
            return [dict(r) for r in cursor.fetchall()]

    def get_audit_trail(self, limit: int = 200) -> List[Dict[str, Any]]:
        """Retrieve system audit event history."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, timestamp, event_type, run_id, description, metadata_json
                FROM audit_events
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = []
            for r in cursor.fetchall():
                d = dict(r)
                d["metadata"] = json.loads(d.get("metadata_json") or "{}")
                rows.append(d)
            return rows


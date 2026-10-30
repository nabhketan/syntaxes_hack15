"""Tests for SQLite active dataset persistence across application reloads/refreshes."""

import tempfile
from pathlib import Path
import pytest
from fairshift.models import Applicant, Program
from fairshift.database import AllocationDatabase
from fairshift.data_manager import add_program, replace_applicant, remove_program


def test_active_dataset_persistence_across_reloads():
    """Verify that any addition, replacement, or removal is permanently saved in SQLite and survives reloads."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_fairshift.db"
        db = AllocationDatabase(db_path=db_path)

        # 1. Initially, no active dataset
        assert db.has_active_dataset() is False

        # 2. Seed initial programs and applicants
        initial_progs = [
            Program("P_AI", "Artificial Intelligence", capacity=10, eligibility_criteria="ALL"),
            Program("P_DEV", "Software Dev", capacity=15, eligibility_criteria="ALL"),
        ]
        initial_apps = [
            Applicant("APP001", "Alice Smith", preferences=["P_AI", "P_DEV"], eligibility=["ALL"]),
            Applicant("APP002", "Bob Jones", preferences=["P_DEV"], eligibility=["ALL"]),
        ]
        db.save_active_dataset(applicants=initial_apps, programs=initial_progs)
        assert db.has_active_dataset() is True

        # 3. Simulate refreshing the app: create a new DB instance connecting to the same SQLite file
        db_reload1 = AllocationDatabase(db_path=db_path)
        assert db_reload1.has_active_dataset() is True
        loaded_apps, loaded_progs = db_reload1.load_active_dataset()
        assert len(loaded_progs) == 2
        assert len(loaded_apps) == 2
        assert loaded_progs[0].program_id == "P_AI"
        assert loaded_apps[0].name == "Alice Smith"

        # 4. Add a new program and replace an applicant
        new_prog = Program("P_CLOUD", "Cloud DevOps", capacity=8, eligibility_criteria="CLOUD_TAG")
        add_program(loaded_progs, new_prog)
        db_reload1.save_programs(loaded_progs)

        replacement_alice = Applicant(
            applicant_id="APP001",
            name="Alice Cooper (Renamed)",
            status="active",
            preferences=["P_CLOUD", "P_AI"],
            eligibility=["ALL", "CLOUD_TAG"],
            notes="Updated profile permanently",
        )
        replace_applicant(loaded_apps, "APP001", replacement_alice)
        db_reload1.save_applicants(loaded_apps)

        # 5. Simulate another browser refresh (new DB connection)
        db_reload2 = AllocationDatabase(db_path=db_path)
        refreshed_apps, refreshed_progs = db_reload2.load_active_dataset()

        # The new program P_CLOUD must still be there permanently
        prog_ids = [p.program_id for p in refreshed_progs]
        assert "P_CLOUD" in prog_ids
        assert len(refreshed_progs) == 3

        # Alice's updated name, preferences, and eligibility must be preserved permanently
        alice = next(a for a in refreshed_apps if a.applicant_id == "APP001")
        assert alice.name == "Alice Cooper (Renamed)"
        assert alice.preferences == ["P_CLOUD", "P_AI"]
        assert "CLOUD_TAG" in alice.eligibility
        assert alice.notes == "Updated profile permanently"

        # 6. Remove a program and verify permanent removal after another refresh
        remove_program(refreshed_progs, "P_DEV")
        db_reload2.save_programs(refreshed_progs)

        db_reload3 = AllocationDatabase(db_path=db_path)
        final_apps, final_progs = db_reload3.load_active_dataset()
        final_prog_ids = [p.program_id for p in final_progs]
        assert "P_DEV" not in final_prog_ids
        assert len(final_progs) == 2


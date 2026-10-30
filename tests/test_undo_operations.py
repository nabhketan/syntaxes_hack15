"""Tests for Undo functionality reversing additions, edits, removals, and .xlsx imports."""

import io
import tempfile
from pathlib import Path
import pandas as pd
import pytest

from fairshift.models import Applicant, Program
from fairshift.database import AllocationDatabase
from fairshift.data_manager import (
    add_program,
    replace_program,
    remove_program,
    add_applicant,
    replace_applicant,
    remove_applicant,
    import_programs_from_file,
    import_applicants_from_file,
)


def test_undo_add_and_edit_program():
    """Verify undo reverses program additions and edits."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = AllocationDatabase(db_path=Path(tmpdir) / "test.db")
        programs = [Program("P1", "Original Prog 1", capacity=10)]
        applicants = [Applicant("A1", "Alice", preferences=["P1"])]
        db.save_active_dataset(applicants, programs)

        # 1. Add program with undo state pushed
        db.push_undo_state("ADD_PROGRAM", "Added P2", applicants, programs)
        new_p = Program("P2", "Program 2", capacity=15)
        add_program(programs, new_p)
        db.save_programs(programs)
        assert len(programs) == 2
        assert db.can_undo() is True

        # 2. Undo addition
        res = db.pop_undo_state()
        assert res is not None
        restored_apps, restored_progs, desc = res
        assert "Added P2" in desc
        assert len(restored_progs) == 1
        assert restored_progs[0].program_id == "P1"

        # 3. Edit/replace program with undo state pushed
        db.push_undo_state("REPLACE_PROGRAM", "Replaced P1", restored_apps, restored_progs)
        replace_program(restored_progs, "P1", Program("P1", "Edited Name", capacity=99))
        db.save_programs(restored_progs)
        assert restored_progs[0].capacity == 99

        # 4. Undo replacement
        res2 = db.pop_undo_state()
        assert res2 is not None
        apps2, progs2, desc2 = res2
        assert progs2[0].capacity == 10
        assert progs2[0].name == "Original Prog 1"


def test_undo_remove_program():
    """Verify undo restores a removed program and its applicant preference links."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = AllocationDatabase(db_path=Path(tmpdir) / "test.db")
        programs = [Program("P1", "Prog 1", capacity=10), Program("P2", "Prog 2", capacity=20)]
        applicants = [Applicant("A1", "Alice", preferences=["P1", "P2"])]
        db.save_active_dataset(applicants, programs)

        # Remove P1 with undo state pushed
        db.push_undo_state("REMOVE_PROGRAM", "Removed P1", applicants, programs)
        remove_program(programs, "P1", applicants=applicants, clean_preferences=True)
        db.save_programs(programs)
        db.save_applicants(applicants)
        assert len(programs) == 1
        assert applicants[0].preferences == ["P2"]

        # Undo removal
        restored_apps, restored_progs, desc = db.pop_undo_state()
        assert len(restored_progs) == 2
        assert [p.program_id for p in restored_progs] == ["P1", "P2"]
        assert restored_apps[0].preferences == ["P1", "P2"]


def test_undo_xlsx_import_programs():
    """Verify undo completely reverses adding or replacing datasets from .xlsx format."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = AllocationDatabase(db_path=Path(tmpdir) / "test.db")
        programs = [Program("P_BASE", "Base Program", capacity=5)]
        applicants = [Applicant("A1", "Alice", preferences=["P_BASE"])]
        db.save_active_dataset(applicants, programs)

        # Create sample Excel bytes in .xlsx format
        excel_buffer = io.BytesIO()
        df = pd.DataFrame([
            {"program_id": "P_EXCEL_1", "name": "Excel Program 1", "capacity": 30, "eligibility_criteria": "ALL"},
            {"program_id": "P_EXCEL_2", "name": "Excel Program 2", "capacity": 25, "eligibility_criteria": "ALL"},
        ])
        df.to_excel(excel_buffer, index=False, engine="openpyxl")
        xlsx_bytes = excel_buffer.getvalue()

        # Parse Excel
        imported_progs, errors = import_programs_from_file(xlsx_bytes, "new_programs.xlsx")
        assert len(errors) == 0
        assert len(imported_progs) == 2

        # Push undo before applying imported dataset
        db.push_undo_state("IMPORT_PROGRAMS_XLSX", "Imported programs from new_programs.xlsx", applicants, programs)

        # Apply import (replace entire list)
        programs = imported_progs
        db.save_programs(programs)
        assert len(programs) == 2
        assert programs[0].program_id == "P_EXCEL_1"

        # Undo import!
        restored_apps, restored_progs, desc = db.pop_undo_state()
        assert "new_programs.xlsx" in desc
        assert len(restored_progs) == 1
        assert restored_progs[0].program_id == "P_BASE"


def test_undo_xlsx_import_applicants():
    """Verify undo completely reverses importing applicants from .xlsx format."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = AllocationDatabase(db_path=Path(tmpdir) / "test.db")
        programs = [Program("P1", "Program 1", capacity=10)]
        applicants = [Applicant("APP_ORIGINAL", "Original Candidate", preferences=["P1"])]
        db.save_active_dataset(applicants, programs)

        # Create sample Excel bytes
        excel_buf = io.BytesIO()
        df = pd.DataFrame([
            {"applicant_id": "APP_XLSX_1", "name": "Candidate 1", "status": "active", "preferences": "P1", "eligibility": "ALL"},
            {"applicant_id": "APP_XLSX_2", "name": "Candidate 2", "status": "active", "preferences": "P1", "eligibility": "ALL"},
        ])
        df.to_excel(excel_buf, index=False, engine="openpyxl")
        xlsx_bytes = excel_buf.getvalue()

        imported_apps, errors = import_applicants_from_file(xlsx_bytes, "batch_candidates.xlsx")
        assert len(errors) == 0

        # Push undo state before applying
        db.push_undo_state("IMPORT_APPLICANTS_XLSX", "Imported applicants from batch_candidates.xlsx", applicants, programs)

        # Merge imported applicants
        applicants.extend(imported_apps)
        db.save_applicants(applicants)
        assert len(applicants) == 3

        # Undo import!
        restored_apps, restored_progs, desc = db.pop_undo_state()
        assert "batch_candidates.xlsx" in desc
        assert len(restored_apps) == 1
        assert restored_apps[0].applicant_id == "APP_ORIGINAL"


def test_sequential_multi_level_undo():
    """Verify undoing multiple steps back through the history stack in reverse order."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = AllocationDatabase(db_path=Path(tmpdir) / "test.db")
        programs = [Program("P1", "Prog 1", capacity=10)]
        applicants = [Applicant("A1", "Alice")]
        db.save_active_dataset(applicants, programs)

        # Step 1: Add P2
        db.push_undo_state("ADD_PROGRAM", "Step 1: Add P2", applicants, programs)
        programs.append(Program("P2", "Prog 2", capacity=10))

        # Step 2: Add A2
        db.push_undo_state("ADD_APPLICANT", "Step 2: Add A2", applicants, programs)
        applicants.append(Applicant("A2", "Bob"))

        # Step 3: Add P3
        db.push_undo_state("ADD_PROGRAM", "Step 3: Add P3", applicants, programs)
        programs.append(Program("P3", "Prog 3", capacity=10))

        assert db.get_undo_count() == 3

        # Undo Step 3
        apps, progs, d3 = db.pop_undo_state()
        assert "Step 3" in d3
        assert len(progs) == 2  # P3 removed

        # Undo Step 2
        apps, progs, d2 = db.pop_undo_state()
        assert "Step 2" in d2
        assert len(apps) == 1  # A2 removed

        # Undo Step 1
        apps, progs, d1 = db.pop_undo_state()
        assert "Step 1" in d1
        assert len(progs) == 1  # P2 removed

        assert db.can_undo() is False


"""Tests for applicant-program reconciliation and dataset validation during Excel/CSV imports."""

import io
import pytest
import pandas as pd

from fairshift.models import Applicant, Program, SolverStatusEnum
from fairshift.optimizer import AllocationOptimizer
from fairshift.validator import AllocationValidator
from fairshift.data_manager import (
    prune_invalid_preferences,
    reconcile_applicant_preferences,
    auto_assign_valid_preferences,
    validate_dataset,
    import_programs_from_file,
)


def test_prune_invalid_preferences():
    """Verify that unlisted program IDs are cleanly removed from applicant preference lists."""
    progs = [
        Program("P1", "Program 1", capacity=10),
        Program("P2", "Program 2", capacity=10),
    ]
    apps = [
        Applicant("A1", "Alice", preferences=["P1", "P_NON_EXISTENT_1", "P2", "P_NON_EXISTENT_2"]),
        Applicant("A2", "Bob", preferences=["P_NON_EXISTENT_1"]),
        Applicant("A3", "Charlie", preferences=["P1", "P2"]),
    ]

    pruned = prune_invalid_preferences(apps, progs)
    assert pruned == 3
    assert apps[0].preferences == ["P1", "P2"]
    assert apps[1].preferences == []
    assert apps[2].preferences == ["P1", "P2"]

    # Validate dataset
    is_valid, errs, warns = validate_dataset(apps, progs)
    assert is_valid is True
    assert len(errs) == 0


def test_reconcile_applicant_preferences_by_description_and_name():
    """Verify that program renames map cleanly by description or name."""
    old_progs = [
        Program("PROG_OLD_AI", "AI Program", capacity=20, description="Deep Learning Fellowship"),
        Program("PROG_OLD_CLOUD", "Cloud Program", capacity=15, description="AWS and DevOps"),
    ]
    new_progs = [
        Program("PROG_1", "AI Program", capacity=20, description="Deep Learning Fellowship"),
        Program("PROG_2", "Cloud Infrastructure", capacity=15, description="AWS and DevOps"),
    ]
    apps = [
        Applicant("A1", "Alice", eligibility=["ALL", "PROG_OLD_AI"], preferences=["PROG_OLD_AI", "PROG_OLD_CLOUD"]),
        Applicant("A2", "Bob", eligibility=["ALL"], preferences=["PROG_OLD_CLOUD"]),
    ]

    remapped, pruned = reconcile_applicant_preferences(apps, old_progs, new_progs)
    assert remapped == 2
    assert pruned == 0
    assert apps[0].preferences == ["PROG_1", "PROG_2"]
    assert apps[1].preferences == ["PROG_2"]
    assert "PROG_1" in apps[0].eligibility

    is_valid, errs, warns = validate_dataset(apps, new_progs)
    assert is_valid is True
    assert len(errs) == 0


def test_reconcile_applicant_preferences_positional_fallback():
    """Verify that when program IDs and names are entirely replaced, positional order maintains integrity."""
    old_progs = [
        Program("P_ALPHA", "Alpha Track", capacity=10, description="Desc A"),
        Program("P_BETA", "Beta Track", capacity=10, description="Desc B"),
    ]
    new_progs = [
        Program("NEW_1", "Track 1", capacity=10, description="Totally new desc 1"),
        Program("NEW_2", "Track 2", capacity=10, description="Totally new desc 2"),
    ]
    apps = [
        Applicant("A1", "Alice", preferences=["P_ALPHA", "P_BETA"]),
        Applicant("A2", "Bob", preferences=["P_BETA"]),
    ]

    remapped, pruned = reconcile_applicant_preferences(apps, old_progs, new_progs)
    assert remapped == 2
    assert apps[0].preferences == ["NEW_1", "NEW_2"]
    assert apps[1].preferences == ["NEW_2"]

    is_valid, errs, warns = validate_dataset(apps, new_progs)
    assert is_valid is True


def test_auto_assign_valid_preferences():
    """Verify that auto_assign_valid_preferences creates 100% valid preferences and eligibility."""
    progs = [
        Program("P1", "Program 1", capacity=5, eligibility_criteria="CRIT_1"),
        Program("P2", "Program 2", capacity=5, eligibility_criteria="CRIT_2"),
        Program("P3", "Program 3", capacity=5, eligibility_criteria="ALL"),
    ]
    apps = [
        Applicant(f"A{i}", f"Applicant {i}", eligibility=[], preferences=[])
        for i in range(1, 10)
    ]

    updated = auto_assign_valid_preferences(apps, progs, min_prefs=2, max_prefs=3)
    assert updated == 9
    for a in apps:
        assert len(a.preferences) >= 2
        for p in a.preferences:
            assert p in ["P1", "P2", "P3"]

    is_valid, errs, warns = validate_dataset(apps, progs)
    assert is_valid is True
    assert len(errs) == 0


def test_xlsx_import_and_reconciliation_workflow():
    """Simulate importing programs from an Excel file and reconciling applicant dataset without 799 errors."""
    old_progs = [
        Program(f"OLD_P{i}", f"Old Program {i}", capacity=10, description=f"Description {i}")
        for i in range(1, 11)
    ]
    apps = [
        Applicant(f"APP{i:03d}", f"Candidate {i}", preferences=[f"OLD_P{(i + j) % 10 + 1}" for j in range(4)])
        for i in range(1, 201)
    ]

    # Create Excel bytes simulating user upload of new programs
    new_df = pd.DataFrame([
        {
            "program_id": f"PROG_{i}",
            "name": f"PROG_{i}",
            "capacity": 20,
            "eligibility_criteria": f"CRIT_{i}",
            "description": f"Description {i}",
        }
        for i in range(1, 11)
    ])
    buf = io.BytesIO()
    new_df.to_excel(buf, index=False)
    file_bytes = buf.getvalue()

    # Import programs
    imported_progs, errors = import_programs_from_file(file_bytes, "new_programs.xlsx")
    assert len(errors) == 0
    assert len(imported_progs) == 10

    # Before reconciliation: applicants reference old program IDs
    is_valid_before, errs_before, _ = validate_dataset(apps, imported_progs)
    assert is_valid_before is False
    assert len(errs_before) > 500

    # Reconcile dataset
    remapped, pruned = reconcile_applicant_preferences(apps, old_progs, imported_progs)
    assert remapped == 200

    # After reconciliation: dataset is 100% valid
    is_valid_after, errs_after, _ = validate_dataset(apps, imported_progs)
    assert is_valid_after is True
    assert len(errs_after) == 0

    # Ensure optimizer runs optimally
    opt = AllocationOptimizer(apps, imported_progs)
    res = opt.solve()
    assert res.solver_status == SolverStatusEnum.OPTIMAL
    assert res.total_assigned > 0


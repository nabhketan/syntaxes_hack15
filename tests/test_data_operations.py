"""Tests for adding, replacing, and removing entries in Program and Applicant datasets."""

import pytest
from fairshift.models import Applicant, Program
from fairshift.data_manager import (
    add_program,
    replace_program,
    remove_program,
    add_applicant,
    replace_applicant,
    remove_applicant,
)


def test_add_program():
    programs = [
        Program("P1", "Program 1", capacity=10),
    ]
    new_prog = Program("P2", "Program 2", capacity=15)
    success, msg = add_program(programs, new_prog)
    assert success is True
    assert len(programs) == 2
    assert programs[1].program_id == "P2"

    # Test duplicate ID
    dup_prog = Program("P1", "Duplicate P1", capacity=5)
    success, msg = add_program(programs, dup_prog)
    assert success is False
    assert "already exists" in msg

    # Test negative capacity
    neg_prog = Program("P3", "Program 3", capacity=-1)
    success, msg = add_program(programs, neg_prog)
    assert success is False
    assert "non-negative" in msg


def test_replace_program_and_cascade():
    programs = [
        Program("P_OLD", "Old Program Name", capacity=10, eligibility_criteria="ALL"),
        Program("P_KEEP", "Keeping this", capacity=5, eligibility_criteria="ALL"),
    ]
    applicants = [
        Applicant("A1", "Alice", preferences=["P_OLD", "P_KEEP"]),
        Applicant("A2", "Bob", preferences=["P_KEEP", "P_OLD"]),
    ]

    # Replace P_OLD with P_NEW and rename
    replacement = Program("P_NEW", "Brand New Program Name", capacity=25, eligibility_criteria="NEW_TAG")
    success, msg = replace_program(
        programs=programs,
        old_program_id="P_OLD",
        new_program=replacement,
        applicants=applicants,
        update_applicant_preferences=True,
    )

    assert success is True
    assert programs[0].program_id == "P_NEW"
    assert programs[0].name == "Brand New Program Name"
    assert programs[0].capacity == 25

    # Check that applicant preferences cascaded from P_OLD to P_NEW
    assert applicants[0].preferences == ["P_NEW", "P_KEEP"]
    assert applicants[1].preferences == ["P_KEEP", "P_NEW"]


def test_remove_program_and_clean_references():
    programs = [
        Program("P1", "Program 1", capacity=10),
        Program("P2", "Program 2", capacity=10),
    ]
    applicants = [
        Applicant("A1", "Alice", preferences=["P1", "P2"]),
        Applicant("A2", "Bob", preferences=["P2"]),
    ]

    success, msg, affected = remove_program(
        programs=programs,
        program_id="P1",
        applicants=applicants,
        clean_preferences=True,
    )
    assert success is True
    assert affected == 1
    assert len(programs) == 1
    assert programs[0].program_id == "P2"
    # P1 removed from Alice's preferences
    assert applicants[0].preferences == ["P2"]
    assert applicants[1].preferences == ["P2"]


def test_add_applicant():
    applicants = [
        Applicant("APP001", "Alice", preferences=["P1"]),
    ]
    new_app = Applicant("APP002", "Bob", preferences=["P1", "P2"])
    success, msg = add_applicant(applicants, new_app)
    assert success is True
    assert len(applicants) == 2

    # Duplicate ID
    dup_app = Applicant("APP001", "Imposter Alice")
    success, msg = add_applicant(applicants, dup_app)
    assert success is False
    assert "already exists" in msg

    # Invalid status
    bad_app = Applicant("APP003", "Bad Status", status="invalid_status")
    success, msg = add_applicant(applicants, bad_app)
    assert success is False


def test_replace_applicant():
    applicants = [
        Applicant("APP001", "Alice", status="active", preferences=["P1"]),
        Applicant("APP002", "Bob", status="active", preferences=["P2"]),
    ]
    replacement = Applicant(
        applicant_id="APP001",
        name="Alice Cooper",
        status="withdrawn",
        preferences=["P2", "P1"],
        eligibility=["SPEC_ELIGIBLE"],
        notes="Replaced entry",
    )
    success, msg = replace_applicant(applicants, old_applicant_id="APP001", new_applicant=replacement)
    assert success is True
    assert applicants[0].name == "Alice Cooper"
    assert applicants[0].status == "withdrawn"
    assert applicants[0].preferences == ["P2", "P1"]
    assert applicants[0].eligibility == ["SPEC_ELIGIBLE"]


def test_remove_applicant():
    applicants = [
        Applicant("APP001", "Alice"),
        Applicant("APP002", "Bob"),
    ]
    success, msg = remove_applicant(applicants, "APP001")
    assert success is True
    assert len(applicants) == 1
    assert applicants[0].applicant_id == "APP002"

    # Not found
    success, msg = remove_applicant(applicants, "APP999")
    assert success is False
    assert "not found" in msg


"""Data management module for FAIRSHIFT.

Provides:
- Realistic default dataset generation (~200 applicants, 10 programs).
- CSV and Excel data import/export.
- Strict data validation checking for missing fields, duplicate IDs, invalid preferences,
  negative capacities, and malformed inputs with actionable error messages.
"""

from __future__ import annotations
import io
import random
from typing import Dict, List, Tuple, Any, Optional
import pandas as pd

from .models import Applicant, Program


SAMPLE_PROGRAMS: List[Dict[str, Any]] = [
    {
        "program_id": "PROG_AI",
        "name": "Artificial Intelligence & ML Fellowship",
        "capacity": 22,
        "eligibility_criteria": "ALL",
        "description": "Advanced training in deep learning, LLMs, and computer vision.",
    },
    {
        "program_id": "PROG_CLOUD",
        "name": "Cloud Architecture & DevOps Track",
        "capacity": 20,
        "eligibility_criteria": "ALL",
        "description": "Enterprise cloud infrastructure, Kubernetes, and CI/CD pipelines.",
    },
    {
        "program_id": "PROG_CYBER",
        "name": "Cybersecurity Defense Operations",
        "capacity": 18,
        "eligibility_criteria": "CYBER_ELIGIBLE",
        "description": "Threat hunting, penetration testing, and security compliance.",
    },
    {
        "program_id": "PROG_DATA",
        "name": "Data Science & Big Data Analytics",
        "capacity": 25,
        "eligibility_criteria": "ALL",
        "description": "Statistical modeling, predictive analytics, and data pipeline design.",
    },
    {
        "program_id": "PROG_DEV",
        "name": "Full-Stack Software Engineering",
        "capacity": 28,
        "eligibility_criteria": "ALL",
        "description": "Modern web development with React, Python, and scalable backends.",
    },
    {
        "program_id": "PROG_HEALTH",
        "name": "Healthcare Informatics Specialization",
        "capacity": 15,
        "eligibility_criteria": "HEALTH_ELIGIBLE",
        "description": "Biomedical data systems, clinical analytics, and HIPAA compliance.",
    },
    {
        "program_id": "PROG_LEAD",
        "name": "Tech Leadership & Product Management",
        "capacity": 16,
        "eligibility_criteria": "LEAD_ELIGIBLE",
        "description": "Product roadmap strategy, engineering leadership, and agile methodologies.",
    },
    {
        "program_id": "PROG_MOBILE",
        "name": "Mobile Application Development",
        "capacity": 18,
        "eligibility_criteria": "ALL",
        "description": "Cross-platform mobile apps using Flutter and native Android/iOS tooling.",
    },
    {
        "program_id": "PROG_QUANT",
        "name": "Financial Engineering & Quantitative Modeling",
        "capacity": 12,
        "eligibility_criteria": "QUANT_ELIGIBLE",
        "description": "Algorithmic trading models, risk management, and stochastic calculus.",
    },
    {
        "program_id": "PROG_ROBOT",
        "name": "Robotics & Autonomous Systems",
        "capacity": 14,
        "eligibility_criteria": "ROBOT_ELIGIBLE",
        "description": "ROS2, SLAM navigation, sensor fusion, and micro-controller automation.",
    },
]

FIRST_NAMES = [
    "Aiden", "Amara", "Carlos", "Chloe", "David", "Elena", "Fatima", "Gabriel",
    "Hana", "Isaac", "Jasmine", "Kaito", "Layla", "Marcus", "Nadia", "Oliver",
    "Priya", "Quinn", "Rohan", "Sofia", "Tariq", "Uma", "Vikram", "Wendy",
    "Xavier", "Yasmin", "Zane", "Ananya", "Brian", "Camila", "Darius", "Evelyn",
    "Farhan", "Grace", "Hiroshi", "Isla", "Jamal", "Kiara", "Leo", "Maya"
]

LAST_NAMES = [
    "Adler", "Bhatnagar", "Chen", "Diallo", "Espinoza", "Fischer", "Gupta", "Hassan",
    "Ibrahim", "Johansson", "Kowalski", "Larsson", "Morales", "Nguyen", "O'Connor",
    "Patel", "Qureshi", "Rodriguez", "Sharma", "Tanaka", "Uchida", "Vargas", "Wong",
    "Xiao", "Yamamoto", "Zimmerman", "Al-Mansoor", "Bakari", "Costa", "Dubois"
]


def generate_sample_dataset(applicant_count: int = 200, seed: int = 42) -> Tuple[List[Applicant], List[Program]]:
    """Generate reproducible sample dataset with ~200 applicants and 10 programs."""
    rng = random.Random(seed)
    programs = [Program.from_dict(p) for p in SAMPLE_PROGRAMS]
    prog_ids = [p.program_id for p in programs]
    specialized_tags = ["CYBER_ELIGIBLE", "HEALTH_ELIGIBLE", "LEAD_ELIGIBLE", "QUANT_ELIGIBLE", "ROBOT_ELIGIBLE"]

    applicants: List[Applicant] = []
    
    for i in range(1, applicant_count + 1):
        app_id = f"APP{i:03d}"
        fname = FIRST_NAMES[(i * 7 + 3) % len(FIRST_NAMES)]
        lname = LAST_NAMES[(i * 11 + 5) % len(LAST_NAMES)]
        name = f"{fname} {lname}"

        # Assign eligibility tags
        # Everyone qualifies for 'ALL' programs; some qualify for specialized tags
        elig = ["ALL"]
        # Add 1-2 specialized tags with certain probability
        for tag in specialized_tags:
            if rng.random() < 0.40:
                elig.append(tag)

        # Generate 3 to 5 distinct preferred programs
        pref_len = rng.randint(3, 5)
        # Weight popular programs slightly higher
        shuffled_progs = list(prog_ids)
        rng.shuffle(shuffled_progs)
        prefs = shuffled_progs[:pref_len]

        # Status: ~5% withdrawn to provide immediate withdrawal workflow examples
        status = "withdrawn" if i in (14, 38, 77, 112, 145, 180) else "active"

        applicants.append(
            Applicant(
                applicant_id=app_id,
                name=name,
                eligibility=elig,
                preferences=prefs,
                status=status,
                notes=f"Sample candidate {i}",
            )
        )

    return applicants, programs


def validate_dataset(
    applicants: List[Applicant],
    programs: List[Program]
) -> Tuple[bool, List[str], List[str]]:
    """Validate dataset integrity.
    
    Returns:
    - is_valid: bool
    - errors: list of blocking validation errors
    - warnings: list of non-blocking warnings
    """
    errors: List[str] = []
    warnings: List[str] = []

    # 1. Check Programs
    prog_id_seen = set()
    total_capacity = 0
    if not programs:
        errors.append("No programs defined. At least one program is required.")

    for p in programs:
        p_id = p.program_id.strip()
        if not p_id:
            errors.append(f"Program has empty ID: '{p.name}'.")
        elif p_id in prog_id_seen:
            errors.append(f"Duplicate program ID '{p_id}' detected.")
        else:
            prog_id_seen.add(p_id)

        if not p.name.strip():
            warnings.append(f"Program '{p_id}' has an empty name.")

        if p.capacity < 0:
            errors.append(f"Program '{p_id}' has negative capacity ({p.capacity}). Capacity must be >= 0.")
        else:
            total_capacity += p.capacity

    # 2. Check Applicants
    app_id_seen = set()
    active_count = 0
    withdrawn_count = 0

    if not applicants:
        errors.append("No applicants provided. At least one applicant is required.")

    for a in applicants:
        a_id = a.applicant_id.strip()
        if not a_id:
            errors.append(f"Applicant has empty ID: '{a.name}'.")
        elif a_id in app_id_seen:
            errors.append(f"Duplicate applicant ID '{a_id}' detected.")
        else:
            app_id_seen.add(a_id)

        if not a.name.strip():
            warnings.append(f"Applicant '{a_id}' has empty name.")

        if a.status not in ("active", "withdrawn"):
            errors.append(f"Applicant '{a_id}' has invalid status '{a.status}'. Must be 'active' or 'withdrawn'.")

        if a.is_active:
            active_count += 1
        else:
            withdrawn_count += 1

        # Check preferences
        if not a.preferences and a.is_active:
            warnings.append(f"Applicant '{a_id}' has no program preferences ranked.")

        seen_prefs = set()
        for pref in a.preferences:
            pref_clean = pref.strip()
            if not pref_clean:
                continue
            if pref_clean not in prog_id_seen:
                errors.append(
                    f"Applicant '{a_id}' ranks non-existent program '{pref_clean}'."
                )
            if pref_clean in seen_prefs:
                warnings.append(f"Applicant '{a_id}' lists duplicate preference '{pref_clean}'.")
            seen_prefs.add(pref_clean)

    if total_capacity < active_count:
        warnings.append(
            f"Total seat capacity ({total_capacity}) is less than active applicant count ({active_count}). "
            f"At least {active_count - total_capacity} active applicants will necessarily remain unassigned."
        )

    is_valid = len(errors) == 0
    return is_valid, errors, warnings


def prune_invalid_preferences(applicants: List[Applicant], programs: List[Program]) -> int:
    """Prunes any preference from applicants that does not exist in the programs list.

    Returns:
        The total count of invalid preference entries removed across all applicants.
    """
    valid_prog_ids = {p.program_id.strip() for p in programs if p.program_id.strip()}
    pruned_count = 0
    for a in applicants:
        orig_len = len(a.preferences)
        a.preferences = [p.strip() for p in a.preferences if p.strip() in valid_prog_ids]
        pruned_count += (orig_len - len(a.preferences))
    return pruned_count


def reconcile_applicant_preferences(
    applicants: List[Applicant],
    old_programs: List[Program],
    new_programs: List[Program],
) -> Tuple[int, int]:
    """Smartly reconciles applicant preferences and eligibility when programs are replaced or modified.

    Matching strategies:
    1. Direct Program ID identity match.
    2. Exact or normalized Program Description match.
    3. Case-insensitive Program Name match.
    4. Positional row-order fallback if both program lists share the same non-zero count.

    Also:
    - Transfers eligibility: if an applicant was eligible for an old program, they receive the new
      program's eligibility criteria tags and ID.
    - Prunes any remaining preference pointing to a program not in new_programs.

    Returns:
        (remapped_applicants_count, pruned_preferences_count)
    """
    new_prog_ids = {p.program_id.strip() for p in new_programs if p.program_id.strip()}
    old_to_new_prog: Dict[str, Program] = {}

    # Map by description
    new_by_desc: Dict[str, Program] = {
        p.description.strip().lower(): p for p in new_programs if p.description.strip()
    }
    # Map by name
    new_by_name: Dict[str, Program] = {
        p.name.strip().lower(): p for p in new_programs if p.name.strip()
    }
    # Map by ID
    new_by_id: Dict[str, Program] = {
        p.program_id.strip(): p for p in new_programs if p.program_id.strip()
    }

    for op in old_programs:
        op_id = op.program_id.strip()
        # 1. Direct ID match
        if op_id in new_by_id:
            old_to_new_prog[op_id] = new_by_id[op_id]
            continue
        # 2. Description match
        op_desc = op.description.strip().lower()
        if op_desc and op_desc in new_by_desc:
            old_to_new_prog[op_id] = new_by_desc[op_desc]
            continue
        # 3. Name match
        op_name = op.name.strip().lower()
        if op_name and op_name in new_by_name:
            old_to_new_prog[op_id] = new_by_name[op_name]
            continue

    # 4. Positional fallback if equal count and some have not matched
    if len(old_programs) == len(new_programs) and len(old_programs) > 0:
        for idx, op in enumerate(old_programs):
            op_id = op.program_id.strip()
            if op_id not in old_to_new_prog:
                old_to_new_prog[op_id] = new_programs[idx]

    remapped_apps_count = 0
    pruned_prefs_count = 0

    for a in applicants:
        new_prefs: List[str] = []
        app_modified = False

        for pref in a.preferences:
            pref_clean = pref.strip()
            if not pref_clean:
                continue
            if pref_clean in old_to_new_prog:
                target_prog = old_to_new_prog[pref_clean]
                if target_prog.program_id not in new_prefs:
                    new_prefs.append(target_prog.program_id)
                if target_prog.program_id != pref_clean:
                    app_modified = True
            elif pref_clean in new_prog_ids:
                if pref_clean not in new_prefs:
                    new_prefs.append(pref_clean)
            else:
                # Obsolete reference pruned
                pruned_prefs_count += 1
                app_modified = True

        if app_modified or len(new_prefs) != len(a.preferences):
            a.preferences = new_prefs
            remapped_apps_count += 1

        # Transfer eligibility for any old program applicant was eligible for
        elig_set = set(a.eligibility)
        for op in old_programs:
            op_id = op.program_id.strip()
            if op_id in old_to_new_prog:
                np = old_to_new_prog[op_id]
                if a.is_eligible_for(op):
                    # Add new criteria tag and new program ID
                    if np.eligibility_criteria.strip() and np.eligibility_criteria.strip().upper() != "ALL":
                        elig_set.add(np.eligibility_criteria.strip())
                    elig_set.add(np.program_id)
        a.eligibility = list(elig_set)

    return remapped_apps_count, pruned_prefs_count


def auto_assign_valid_preferences(
    applicants: List[Applicant],
    programs: List[Program],
    min_prefs: int = 3,
    max_prefs: int = 5,
    seed: int = 42,
) -> int:
    """Assigns balanced, valid preferences and matching eligibility tags to active applicants based on active programs.

    Returns:
        The number of applicants updated.
    """
    if not programs:
        return 0

    rng = random.Random(seed)
    valid_p_ids = [p.program_id for p in programs]
    updated = 0

    for idx, a in enumerate(applicants):
        if not a.is_active:
            continue
        p_count = min(len(valid_p_ids), rng.randint(min_prefs, max(min_prefs, max_prefs)))
        shuffled = list(valid_p_ids)
        rng.shuffle(shuffled)
        a.preferences = shuffled[:p_count]

        # Grant general eligibility and criteria tags for chosen programs
        elig = {"ALL"}
        for p in programs:
            if p.program_id in a.preferences:
                if p.eligibility_criteria.strip() and p.eligibility_criteria.strip().upper() != "ALL":
                    elig.add(p.eligibility_criteria.strip())
                elig.add(p.program_id)
        a.eligibility = list(elig)
        updated += 1

    return updated


def export_applicants_to_dataframe(applicants: List[Applicant]) -> pd.DataFrame:
    """Export applicants list to a pandas DataFrame."""
    rows = []
    for a in applicants:
        rows.append({
            "applicant_id": a.applicant_id,
            "name": a.name,
            "status": a.status,
            "eligibility": ", ".join(a.eligibility),
            "preferences": ", ".join(a.preferences),
            "notes": a.notes,
        })
    return pd.DataFrame(rows)


def export_programs_to_dataframe(programs: List[Program]) -> pd.DataFrame:
    """Export programs list to a pandas DataFrame."""
    rows = []
    for p in programs:
        rows.append({
            "program_id": p.program_id,
            "name": p.name,
            "capacity": p.capacity,
            "eligibility_criteria": p.eligibility_criteria,
            "description": p.description,
        })
    return pd.DataFrame(rows)


def import_applicants_from_file(file_bytes: bytes, filename: str) -> Tuple[List[Applicant], List[str]]:
    """Parse CSV or Excel file into a list of Applicant objects with errors reported."""
    errors: List[str] = []
    try:
        if filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(file_bytes))
        elif filename.endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(file_bytes))
        else:
            return [], [f"Unsupported file format '{filename}'. Please upload a .csv or .xlsx file."]
    except Exception as e:
        return [], [f"Failed to parse file '{filename}': {str(e)}"]

    # Normalize column names
    col_map = {c.strip().lower().replace(" ", "_"): c for c in df.columns}
    required = ["applicant_id"]
    for req in required:
        if req not in col_map:
            errors.append(f"Missing mandatory column: '{req}'.")
    if errors:
        return [], errors

    applicants: List[Applicant] = []
    for idx, row in df.iterrows():
        try:
            a_id = str(row[col_map["applicant_id"]]).strip()
            if not a_id or a_id == "nan":
                continue
            name = str(row.get(col_map.get("name", ""), a_id)).strip()
            status = str(row.get(col_map.get("status", ""), "active")).strip().lower()
            elig_val = str(row.get(col_map.get("eligibility", ""), "ALL"))
            pref_val = str(row.get(col_map.get("preferences", ""), ""))
            notes = str(row.get(col_map.get("notes", ""), "")).strip()
            if notes == "nan":
                notes = ""

            elig = [x.strip() for x in elig_val.split(",") if x.strip() and x.strip() != "nan"]
            pref = [x.strip() for x in pref_val.split(",") if x.strip() and x.strip() != "nan"]

            applicants.append(
                Applicant(
                    applicant_id=a_id,
                    name=name,
                    eligibility=elig,
                    preferences=pref,
                    status=status if status in ("active", "withdrawn") else "active",
                    notes=notes,
                )
            )
        except Exception as e:
            errors.append(f"Error parsing row {idx + 1}: {str(e)}")

    return applicants, errors


def import_programs_from_file(file_bytes: bytes, filename: str) -> Tuple[List[Program], List[str]]:
    """Parse CSV or Excel file into a list of Program objects with errors reported."""
    errors: List[str] = []
    try:
        if filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(file_bytes))
        elif filename.endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(file_bytes))
        else:
            return [], [f"Unsupported file format '{filename}'. Please upload a .csv or .xlsx file."]
    except Exception as e:
        return [], [f"Failed to parse file '{filename}': {str(e)}"]

    col_map = {c.strip().lower().replace(" ", "_"): c for c in df.columns}
    if "program_id" not in col_map or "capacity" not in col_map:
        return [], ["File must contain at least 'program_id' and 'capacity' columns."]

    programs: List[Program] = []
    for idx, row in df.iterrows():
        try:
            p_id = str(row[col_map["program_id"]]).strip()
            if not p_id or p_id == "nan":
                continue
            name = str(row.get(col_map.get("name", ""), p_id)).strip()
            cap_val = row[col_map["capacity"]]
            try:
                cap = int(cap_val)
            except Exception:
                errors.append(f"Row {idx + 1}: Invalid capacity '{cap_val}' for program '{p_id}'. Must be an integer.")
                continue

            crit = str(row.get(col_map.get("eligibility_criteria", ""), "ALL")).strip()
            if crit == "nan":
                crit = "ALL"
            desc = str(row.get(col_map.get("description", ""), "")).strip()
            if desc == "nan":
                desc = ""

            programs.append(
                Program(
                    program_id=p_id,
                    name=name,
                    capacity=cap,
                    eligibility_criteria=crit,
                    description=desc,
                )
            )
        except Exception as e:
            errors.append(f"Error parsing row {idx + 1}: {str(e)}")

    return programs, errors


def add_program(programs: List[Program], new_program: Program) -> Tuple[bool, str]:
    """Add a new program to the dataset after validating unique ID and positive capacity."""
    p_id = new_program.program_id.strip()
    if not p_id:
        return False, "Program ID cannot be empty."
    if not new_program.name.strip():
        return False, "Program Name cannot be empty."
    if new_program.capacity < 0:
        return False, f"Capacity must be non-negative (got {new_program.capacity})."
    if any(p.program_id == p_id for p in programs):
        return False, f"Program with ID '{p_id}' already exists."

    programs.append(new_program)
    return True, f"Program '{p_id}' ({new_program.name}) added successfully."


def replace_program(
    programs: List[Program],
    old_program_id: str,
    new_program: Program,
    applicants: Optional[List[Applicant]] = None,
    update_applicant_preferences: bool = True,
) -> Tuple[bool, str]:
    """Replace an existing program entry.
    
    If the program_id is renamed, optionally cascades the rename across all applicant preferences
    and eligibility lists to prevent orphan references.
    """
    old_id = old_program_id.strip()
    new_id = new_program.program_id.strip()

    if not new_id:
        return False, "New Program ID cannot be empty."
    if not new_program.name.strip():
        return False, "Program Name cannot be empty."
    if new_program.capacity < 0:
        return False, f"Capacity must be non-negative (got {new_program.capacity})."

    idx = next((i for i, p in enumerate(programs) if p.program_id == old_id), None)
    if idx is None:
        return False, f"Existing program with ID '{old_id}' was not found."

    if new_id != old_id and any(p.program_id == new_id for p in programs):
        return False, f"Cannot rename to '{new_id}': another program with this ID already exists."

    # Replace program
    programs[idx] = new_program

    # Cascade ID update to applicant preferences and eligibility if ID changed
    updated_apps_count = 0
    if new_id != old_id and update_applicant_preferences and applicants:
        for app in applicants:
            changed = False
            if old_id in app.preferences:
                app.preferences = [new_id if pref == old_id else pref for pref in app.preferences]
                changed = True
            if old_id in app.eligibility:
                app.eligibility = [new_id if elig == old_id else elig for elig in app.eligibility]
                changed = True
            if changed:
                updated_apps_count += 1

    cascade_note = f" (Cascaded ID change to {updated_apps_count} applicant preferences)." if updated_apps_count > 0 else ""
    return True, f"Program '{old_id}' successfully replaced with '{new_id}'{cascade_note}."


def remove_program(
    programs: List[Program],
    program_id: str,
    applicants: Optional[List[Applicant]] = None,
    clean_preferences: bool = True,
) -> Tuple[bool, str, int]:
    """Remove an existing program from the dataset.
    
    Optionally removes references to this program from applicant preferences.
    Returns (success, message, affected_applicants_count).
    """
    p_id = program_id.strip()
    idx = next((i for i, p in enumerate(programs) if p.program_id == p_id), None)
    if idx is None:
        return False, f"Program '{p_id}' not found.", 0

    # Count affected applicants
    affected_count = 0
    if applicants:
        for app in applicants:
            if p_id in app.preferences or p_id in app.eligibility:
                affected_count += 1
                if clean_preferences:
                    app.preferences = [pref for pref in app.preferences if pref != p_id]
                    app.eligibility = [elig for elig in app.eligibility if elig != p_id]

    removed_prog = programs.pop(idx)
    clean_note = f" (Cleaned references in {affected_count} applicant preference lists)." if clean_preferences and affected_count > 0 else ""
    return True, f"Program '{removed_prog.program_id}' ({removed_prog.name}) removed successfully{clean_note}.", affected_count


def add_applicant(applicants: List[Applicant], new_applicant: Applicant) -> Tuple[bool, str]:
    """Add a new applicant to the dataset after validating unique ID and valid status."""
    a_id = new_applicant.applicant_id.strip()
    if not a_id:
        return False, "Applicant ID cannot be empty."
    if not new_applicant.name.strip():
        return False, "Applicant Name cannot be empty."
    if new_applicant.status not in ("active", "withdrawn"):
        return False, f"Status must be 'active' or 'withdrawn' (got '{new_applicant.status}')."
    if any(a.applicant_id == a_id for a in applicants):
        return False, f"Applicant with ID '{a_id}' already exists."

    applicants.append(new_applicant)
    return True, f"Applicant '{a_id}' ({new_applicant.name}) added successfully."


def replace_applicant(
    applicants: List[Applicant],
    old_applicant_id: str,
    new_applicant: Applicant,
) -> Tuple[bool, str]:
    """Replace an existing applicant entry with new details."""
    old_id = old_applicant_id.strip()
    new_id = new_applicant.applicant_id.strip()

    if not new_id:
        return False, "New Applicant ID cannot be empty."
    if not new_applicant.name.strip():
        return False, "Applicant Name cannot be empty."
    if new_applicant.status not in ("active", "withdrawn"):
        return False, f"Status must be 'active' or 'withdrawn' (got '{new_applicant.status}')."

    idx = next((i for i, a in enumerate(applicants) if a.applicant_id == old_id), None)
    if idx is None:
        return False, f"Existing applicant with ID '{old_id}' was not found."

    if new_id != old_id and any(a.applicant_id == new_id for a in applicants):
        return False, f"Cannot rename to '{new_id}': another applicant with this ID already exists."

    applicants[idx] = new_applicant
    return True, f"Applicant '{old_id}' successfully replaced with '{new_id}' ({new_applicant.name})."


def remove_applicant(applicants: List[Applicant], applicant_id: str) -> Tuple[bool, str]:
    """Remove an existing applicant from the dataset."""
    a_id = applicant_id.strip()
    idx = next((i for i, a in enumerate(applicants) if a.applicant_id == a_id), None)
    if idx is None:
        return False, f"Applicant '{a_id}' not found."

    removed_app = applicants.pop(idx)
    return True, f"Applicant '{removed_app.applicant_id}' ({removed_app.name}) removed successfully."



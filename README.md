# FAIRSHIFT ⚖️
### Training-Program Seat Allocation & Counterfactual Impact Analysis Engine

FAIRSHIFT is an enterprise-grade web application built to allocate limited training-program seats and evaluate the ripple effects of applicant withdrawals, capacity changes, and appeals.

The core allocation engine uses **mathematical optimization** with **Python** and **Google OR-Tools CP-SAT** (Constraint Programming / Satisfiability). **No AI or stochastic heuristic is used to make allocation decisions.** Every result is exact, deterministic, explainable, and independently audited.

---

## Key Features

1. **Mathematical Allocation Engine (Google OR-Tools CP-SAT)**:
   - **Multi-Stage Lexicographic Optimization**:
     - **Stage 1:** Maximizes total active eligible applicants assigned ($Z_1^*$).
     - **Stage 2:** Maximizes applicant preference satisfaction score subject to $Z_1 \ge Z_1^*$.
     - **Stage 3:** Maximizes stability / minimizes unnecessary reassignments from baseline ($Z_3$) subject to $Z_1 \ge Z_1^*$ and $Z_2 \ge Z_2^*$.
   - **Alternative Configurable Single-Stage Weighted Optimization** with explicit, customizable priority weights.
2. **Mandatory Hard Constraints**:
   - At most one program assignment per applicant.
   - Program seat capacities are strict upper bounds.
   - Strict eligibility enforcement (criteria matching or prerequisite tags).
   - Zero assignments for withdrawn applicants.
   - Enforced placement for appeal scenarios when mathematically feasible.
3. **Withdrawal Ripple Analysis**:
   - Holds the prior allocation as the baseline.
   - Releases the withdrawn applicant's seat and re-optimizes with stability constraints.
   - Tracks every promoted, demoted, newly assigned, or displaced applicant.
   - Generates factual, evidence-based chains of explanation grounded strictly in inputs and solver output.
4. **Capacity Change Analysis**:
   - Simulates seat increases or decreases.
   - Illustrates waitlist admissions or bumping effects with full before/after diffs.
5. **Counterfactual Appeal Analysis**:
   - Solves counterfactual placement scenarios without mutating or overwriting the active baseline.
   - Distinguishes feasible appeals from impossible/ineligible ones.
6. **Independent Validator**:
   - Built completely isolated from the solver in `fairshift/validator.py`.
   - Audits every proposed allocation against business rules, capacities, eligibility, and scenario conditions before results can be accepted.
7. **Strict Solver Status Distinctions**:
   - Accurately reports:
     - `Optimal`: Optimality mathematically proven.
     - `Feasible, not proven optimal`: Valid solution found within time limit.
     - `Infeasible`: Proven that no valid allocation exists.
     - `Unknown or timed out`: Could not prove feasibility within time limit.
   - **Timeouts are never reported as infeasible.**
8. **Persistent SQLite Database & Audit History**:
   - Stores active applicants and training programs permanently in SQLite (`active_applicants` & `active_programs` tables); any addition, removal, or replacement survives browser refreshes and session restarts.
   - Stores runs, assignments, input data snapshots, and a chronological audit log.
9. **Multi-Level Undo System (Including `.xlsx` / `.csv` File Imports)**:
   - Maintains an `undo_stack` in SQLite capturing complete transactional snapshots of the program and applicant datasets before every modification.
   - Reverts additions, field edits, replacements, and deletions step-by-step.
   - Safely rolls back large dataset replacements or merges triggered from Excel (`.xlsx`) or CSV uploads.
   - Undo history is preserved across page refreshes and browser reloads.

---

## Directory Structure

```
syntaxes/
├── fairshift/
│   ├── __init__.py
│   ├── models.py           # Dataclasses (Applicant, Program, AllocationResult, ValidationResult)
│   ├── optimizer.py        # Google OR-Tools CP-SAT multi-stage allocation engine
│   ├── validator.py        # Independent auditor enforcing rules & scenario checks
│   ├── analyzer.py         # Withdrawal, capacity change, and appeal scenario analysis
│   ├── data_manager.py     # Sample data generation (200 applicants, 10 programs), CSV/Excel I/O
│   └── database.py         # SQLite persistence for runs, snapshots, audit events, and undo stack
├── tests/
│   ├── __init__.py
│   ├── test_eligibility_capacity.py
│   ├── test_at_most_one.py
│   ├── test_withdrawals.py
│   ├── test_capacity_changes.py
│   ├── test_preferences_reassignments.py
│   ├── test_appeals.py
│   ├── test_validator.py
│   ├── test_solver_statuses.py
│   ├── test_data_operations.py
│   ├── test_database_persistence.py
│   └── test_undo_operations.py
├── app.py                  # Streamlit web application
├── requirements.txt        # Python package dependencies
└── README.md
```

---

## Installation & Setup

### Prerequisites
- Python 3.10, 3.11, or 3.12 (64-bit). *(Python 3.12 recommended for OR-Tools pre-built wheels)*.

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

If running with a specific Python installation (such as the Python 3.12 environment):
```powershell
& "C:\Users\ASUS\Python312\python.exe" -m pip install -r requirements.txt
```

---

## Running the Application

Launch the Streamlit web application:
```bash
streamlit run app.py
```
Or via the Python executable:
```powershell
& "C:\Users\ASUS\Python312\python.exe" -m streamlit run app.py
```

The application will open in your browser at `http://localhost:8501`.

---

## Running Automated Tests

Run the complete test suite with `pytest`:
```bash
pytest -v
```
Or via the Python executable:
```powershell
& "C:\Users\ASUS\Python312\python.exe" -m pytest -v
```

All 34 automated unit and integration tests will execute, verifying:
- Eligibility and capacity constraints
- At-most-one assignment
- Withdrawals and seat release cascades
- Capacity increases and decreases
- Preference rank scoring and stability reassignment counts
- Appeal scenarios (feasible and infeasible)
- Independent validator detecting all violations
- Solver statuses (Optimal, Infeasible, Unknown/Timeout distinction)
- Add, Replace, and Remove operations on Programs and Applicants
- Permanent database persistence across page refreshes and reboots
- Multi-level Undo operations for single modifications and bulk `.xlsx` imports
- Smart reconciliation and auto-pruning for Excel (`.xlsx`) program imports without validation blowups

---

## Workflows Guide

### 1. Data Management
- Preloaded with **200 applicants** and **10 training programs** (188 total seats).
- **Persistent SQLite Storage**:
  - All additions, edits, removals, and dataset imports are permanently stored in `fairshift_data.db`. Refreshing the browser preserves all customized data.
- **Add, Replace, and Remove Entries**:
  - **Programs**: Add new programs, replace/edit existing programs (with automatic cascading of ID updates across applicant preference lists), and safely remove programs (with automatic reference cleanup).
  - **Applicants**: Add new applicants, replace/edit existing applicant profiles (updating ID, status, eligibility tags, or ranked preferences), and remove applicants.
- **Smart Spreadsheet Import & Reconcile (`.xlsx` / `.csv`)**:
  - Automatically reconciles applicant preferences and criteria when a new program sheet is imported, mapping matching programs and pruning obsolete IDs.
  - Optional one-click switch to clear existing applicants when uploading a new set of programs.
- **Multi-Level Undo**:
  - Revert any inadvertent mutation with the **"↺ Undo Last Action"** button at the top of the Data Management tab.
  - Displays the exact description and timestamp of the action about to be reversed.
  - Fully supports reversing bulk imports from Excel (`.xlsx`) or CSV, restoring the exact dataset that existed before the import occurred.
- **Compact, Actionable Error Handling**:
  - Live dataset validator immediately catches missing fields, duplicate IDs, invalid preferences, and negative capacities.
  - When errors occur, FAIRSHIFT displays a compact summary banner with 1-click auto-fix actions (`🔄 Auto-Reconcile Dataset`, `🧹 Prune Invalid Preferences`, `🎲 Auto-Assign Valid Prefs`, `👥 Clear All Applicants`) and keeps detailed logs neatly collapsible so the UI layout never breaks.

### 2. Initial Allocation
- Click **"Compute Optimal Allocation"** to run CP-SAT.
- View assignments, unassigned applicants, preference ranks, capacity usage, and solver wall-clock metrics.
- Click **"Save as Current Baseline Allocation"** to establish the foundation for scenario comparisons.

### 3. Withdrawal Impact Analysis
- Select an applicant currently holding a program seat.
- Click **"Analyze Withdrawal Ripple Effect"**.
- View before/after metrics: assigned delta, preference score delta, reassignment count, and affected applicants.
- Read the factual solver chain of events explaining who was promoted into the released seat and who filled downstream openings.
- Optionally commit the withdrawal to update the baseline.

### 4. Capacity Change Analysis
- Select any program and modify its seat capacity.
- Click **"Analyze Capacity Change"** to view ripple effects on waitlisted or displaced applicants.
- Compare remaining seats and fill rates.

### 5. Counterfactual Appeal Analysis
- Select an appellant applicant and their requested program.
- Click **"Evaluate Appeal"**.
- If infeasible, the model explains why (e.g. ineligible or impossible capacity constraints).
- If feasible, see how granting the appeal ripples through the system without altering the active baseline.

### 6. Allocation History & Audit Trail
- Review all past runs, solver statuses, wall-clock times, and independent validation results.
- Inspect detailed assignments for any previous run.
- Restore any historical allocation as the active baseline at any time.


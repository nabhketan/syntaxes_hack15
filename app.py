"""FAIRSHIFT - Training Program Seat Allocation & Impact Analysis System.

Streamlit Web Application.
"""

from __future__ import annotations
import io
import json
import pandas as pd
import streamlit as st

from fairshift.models import (
    Applicant,
    Program,
    OptimizationConfig,
    SolverStatusEnum,
    AllocationResult,
    ScenarioCondition,
)
from fairshift.optimizer import AllocationOptimizer
from fairshift.validator import AllocationValidator
from fairshift.analyzer import ScenarioAnalyzer, ImpactReport
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
)
from fairshift.database import AllocationDatabase

# Page Configuration
st.set_page_config(
    page_title="FAIRSHIFT - Seat Allocation & Impact Analysis",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling for polished UI
st.markdown(
    """
    <style>
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 16px;
        border: 1px solid #e9ecef;
        margin-bottom: 12px;
    }
    .status-optimal { color: #0f5132; background-color: #d1e7dd; padding: 4px 8px; border-radius: 4px; font-weight: 600; }
    .status-feasible { color: #664d03; background-color: #fff3cd; padding: 4px 8px; border-radius: 4px; font-weight: 600; }
    .status-infeasible { color: #842029; background-color: #f8d7da; padding: 4px 8px; border-radius: 4px; font-weight: 600; }
    .status-timeout { color: #41464b; background-color: #e2e3e5; padding: 4px 8px; border-radius: 4px; font-weight: 600; }
    .badge-promoted { background-color: #d1e7dd; color: #0f5132; padding: 2px 6px; border-radius: 4px; font-weight: 500; font-size: 0.85em; }
    .badge-demoted { background-color: #fff3cd; color: #664d03; padding: 2px 6px; border-radius: 4px; font-weight: 500; font-size: 0.85em; }
    .badge-unassigned { background-color: #f8d7da; color: #842029; padding: 2px 6px; border-radius: 4px; font-weight: 500; font-size: 0.85em; }
    .badge-new { background-color: #cfe2ff; color: #084298; padding: 2px 6px; border-radius: 4px; font-weight: 500; font-size: 0.85em; }
    .badge-withdrawn { background-color: #e2e3e5; color: #41464b; padding: 2px 6px; border-radius: 4px; font-weight: 500; font-size: 0.85em; }
    </style>
    """,
    unsafe_allow_html=True,
)

# Initialize Session State
if "db" not in st.session_state:
    st.session_state.db = AllocationDatabase()

if "applicants" not in st.session_state or "programs" not in st.session_state:
    # Load persistent active dataset from SQLite if present, else seed and save
    if st.session_state.db.has_active_dataset():
        apps, progs = st.session_state.db.load_active_dataset()
    else:
        apps, progs = generate_sample_dataset(applicant_count=200, seed=42)
        st.session_state.db.save_active_dataset(applicants=apps, programs=progs)
        st.session_state.db.log_audit_event("DATASET_INITIALIZED", "Seeded default dataset of 200 applicants and 10 programs into SQLite.")
    st.session_state.applicants = apps
    st.session_state.programs = progs

if "baseline_result" not in st.session_state:
    # Check if there is an active baseline in SQLite
    active_run_id = st.session_state.db.get_active_baseline_run_id()
    if active_run_id:
        run_data = st.session_state.db.get_run(active_run_id)
        if run_data:
            # Reconstruct result
            val_data = run_data.get("validation", {})
            st.session_state.baseline_result = AllocationResult(
                run_id=run_data["run_id"],
                timestamp=run_data["timestamp"],
                scenario_type=run_data["scenario_type"],
                scenario_description=run_data["scenario_description"],
                solver_status=SolverStatusEnum(run_data["solver_status"]),
                wall_time_seconds=run_data["wall_time_seconds"],
                assignments=run_data.get("assignments_map", {}),
                total_assigned=run_data["total_assigned"],
                preference_score=run_data["preference_score"],
                reassignment_count=run_data["reassignment_count"],
                rank_distribution={int(k): v for k, v in run_data.get("rank_distribution", {}).items()},
                capacity_utilization=run_data.get("capacity_utilization", {}),
                objective_measures=run_data.get("objective_measures", {}),
            )
    else:
        st.session_state.baseline_result = None

if "last_scenario_result" not in st.session_state:
    st.session_state.last_scenario_result = None

if "last_impact_report" not in st.session_state:
    st.session_state.last_impact_report = None


# Helper to render status badge
def render_solver_badge(status: SolverStatusEnum):
    if status == SolverStatusEnum.OPTIMAL:
        return f'<span class="status-optimal">🟢 {status.value}</span>'
    elif status == SolverStatusEnum.FEASIBLE:
        return f'<span class="status-feasible">🟡 {status.value}</span>'
    elif status == SolverStatusEnum.INFEASIBLE:
        return f'<span class="status-infeasible">🔴 {status.value}</span>'
    else:
        return f'<span class="status-timeout">⚪ {status.value}</span>'


# ==========================================
# SIDEBAR: SETTINGS & QUICK STATS
# ==========================================
with st.sidebar:
    st.title("⚖️ FAIRSHIFT")
    st.caption("Training Seat Allocation Engine")
    st.markdown("---")

    st.subheader("Solver Configuration")
    priority_mode = st.selectbox(
        "Optimization Mode",
        options=["lexicographic", "weighted"],
        index=0,
        format_func=lambda x: "Lexicographic Multi-Stage (Default)" if x == "lexicographic" else "Weighted Single-Stage",
        help="Lexicographic: Strictly prioritizes Max Assigned -> Max Preferences -> Max Stability. Weighted: Single objective with linear weights.",
    )

    only_preferred = st.checkbox(
        "Only assign preferred programs",
        value=True,
        help="Enforces that applicants are only assigned to programs explicitly ranked in their preferences.",
    )

    time_limit = st.slider("Solver Time Limit (s)", min_value=1.0, max_value=60.0, value=15.0, step=1.0)

    # Preference points
    with st.expander("Preference Score Scheme", expanded=False):
        st.caption("Points granted per ranked choice:")
        p1 = st.number_input("1st Choice", value=100, min_value=1)
        p2 = st.number_input("2nd Choice", value=70, min_value=1)
        p3 = st.number_input("3rd Choice", value=45, min_value=1)
        p4 = st.number_input("4th Choice", value=25, min_value=1)
        p5 = st.number_input("5th Choice", value=10, min_value=1)
        points_list = [int(p1), int(p2), int(p3), int(p4), int(p5)]

    opt_config = OptimizationConfig(
        priority_mode=priority_mode,
        points_per_rank=points_list,
        only_assign_preferred=only_preferred,
        time_limit_seconds=float(time_limit),
    )

    st.markdown("---")
    st.subheader("System Data Summary")
    active_apps_count = sum(1 for a in st.session_state.applicants if a.is_active)
    withdrawn_apps_count = sum(1 for a in st.session_state.applicants if a.is_withdrawn)
    total_cap = sum(p.capacity for p in st.session_state.programs)

    st.write(f"👥 **Applicants:** {len(st.session_state.applicants)} ({active_apps_count} active, {withdrawn_apps_count} withdrawn)")
    st.write(f"🏫 **Programs:** {len(st.session_state.programs)} ({total_cap} total seats)")

    if st.session_state.baseline_result:
        st.success(f"Baseline Set: {st.session_state.baseline_result.run_id} ({st.session_state.baseline_result.total_assigned} assigned)")
    else:
        st.warning("No active baseline allocation set.")

    st.markdown("---")
    if st.button("🔄 Reset to Default Sample Data (200 Applicants, 10 Programs)", use_container_width=True):
        st.session_state.applicants, st.session_state.programs = generate_sample_dataset(200, seed=42)
        st.session_state.db.save_active_dataset(applicants=st.session_state.applicants, programs=st.session_state.programs)
        st.session_state.baseline_result = None
        st.session_state.last_scenario_result = None
        st.session_state.last_impact_report = None
        st.session_state.db.log_audit_event("SAMPLE_DATA_RESET", "Reset dataset to 200 sample applicants and 10 programs.")
        st.success("Sample data reset successfully and permanently saved!")
        st.rerun()


# ==========================================
# MAIN INTERFACE TABS
# ==========================================
tabs = st.tabs([
    "📊 Dashboard",
    "👥 Applicants & Programs",
    "🚀 Initial Allocation",
    "🔄 Withdrawal Analysis",
    "⚖️ Capacity Changes",
    "📑 Appeals",
    "📜 Allocation History",
])

# ------------------------------------------
# TAB 1: DASHBOARD
# ------------------------------------------
with tabs[0]:
    st.header("FAIRSHIFT Allocation Dashboard")
    st.write(
        "FAIRSHIFT uses **Google OR-Tools CP-SAT** mathematical constraint programming to allocate limited program seats "
        "transparently, uphold strict eligibility and capacity rules, and simulate ripple effects from applicant withdrawals, "
        "capacity changes, and appeals."
    )

    # Key Metrics Row
    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        st.metric("Total Applicants", f"{len(st.session_state.applicants)}")
    with m2:
        st.metric("Active Applicants", f"{active_apps_count}")
    with m3:
        st.metric("Total Seats", f"{total_cap}")
    with m4:
        assigned_val = st.session_state.baseline_result.total_assigned if st.session_state.baseline_result else 0
        st.metric("Baseline Assigned", f"{assigned_val}")
    with m5:
        match_rate = f"{(assigned_val / active_apps_count * 100):.1f}%" if active_apps_count > 0 and assigned_val > 0 else "0%"
        st.metric("Placement Rate", match_rate)

    st.markdown("---")

    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.subheader("Current Baseline Quality Measures")
        if st.session_state.baseline_result:
            b_res = st.session_state.baseline_result
            st.markdown(f"**Run ID:** `{b_res.run_id}` | **Status:** {b_res.solver_status.value} | **Time:** {b_res.wall_time_seconds}s")
            st.markdown(f"**Total Preference Score:** `{b_res.preference_score:,}` points")

            # Rank distribution table
            rd_rows = []
            for r in range(1, 6):
                count = b_res.rank_distribution.get(r, 0)
                pct = (count / b_res.total_assigned * 100) if b_res.total_assigned > 0 else 0
                rd_rows.append({"Choice Rank": f"Choice #{r}", "Matched Applicants": count, "Share of Assigned": f"{pct:.1f}%"})
            st.dataframe(pd.DataFrame(rd_rows), use_container_width=True, hide_index=True)
        else:
            st.info("No baseline allocation calculated yet. Head to the **Initial Allocation** tab to generate the baseline.")

    with col_right:
        st.subheader("Program Capacity Utilization (Baseline)")
        if st.session_state.baseline_result:
            cap_data = []
            for p_id, p_info in st.session_state.baseline_result.capacity_utilization.items():
                cap_data.append({
                    "Program": p_info["name"],
                    "Capacity": p_info["capacity"],
                    "Assigned": p_info["assigned"],
                    "Remaining": p_info["remaining"],
                    "Fill %": f"{p_info['fill_percentage']:.1f}%",
                })
            st.dataframe(pd.DataFrame(cap_data), use_container_width=True, hide_index=True)
        else:
            progs_preview = [
                {"Program": p.name, "Capacity": p.capacity, "Criteria": p.eligibility_criteria}
                for p in st.session_state.programs
            ]
            st.dataframe(pd.DataFrame(progs_preview), use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("Core Mathematical Rules & Priority Hierarchy")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(
            """
            **Mandatory Hard Constraints (Strictly Guaranteed):**
            1. **At-Most-One Assignment:** An applicant is assigned to at most one program.
            2. **Program Capacity:** Program seat capacity is an absolute upper bound.
            3. **Strict Eligibility:** Only eligible applicants may be assigned.
            4. **Zero Withdrawn Placements:** Withdrawn applicants receive zero seats.
            5. **Appeal Conditions:** Any appeal requirement is enforced if mathematically feasible.
            """
        )
    with c2:
        st.markdown(
            """
            **Optimization Objective Hierarchy:**
            1. **Stage 1 (Max Placements):** Maximize total eligible active applicants assigned.
            2. **Stage 2 (Max Satisfaction):** Maximize sum of applicant preference points subject to Stage 1 optimum.
            3. **Stage 3 (Stability & Minimal Disruption):** Retain baseline assignments and minimize reassignments subject to Stage 1 and 2 optima.
            """
        )


# ------------------------------------------
# TAB 2: APPLICANTS & PROGRAMS
# ------------------------------------------
with tabs[1]:
    st.header("Data Management")
    st.write("Inspect, edit, import, and export applicants and training programs. Dataset integrity is audited live.")

    # Live Undo Bar
    undo_count = st.session_state.db.get_undo_count()
    last_undo = st.session_state.db.get_last_undo_state()

    if undo_count > 0 and last_undo:
        u_col1, u_col2 = st.columns([3, 1])
        with u_col1:
            st.info(f"↩️ **Undo Available ({undo_count} in history):** Reversible change: **{last_undo['action_description']}**")
        with u_col2:
            if st.button("↩️ Undo Last Action", key="tab2_main_undo_btn", type="primary", use_container_width=True):
                pop_res = st.session_state.db.pop_undo_state()
                if pop_res:
                    st.session_state.applicants, st.session_state.programs, undone_text = pop_res
                    st.toast(f"↩️ Undid: {undone_text}")
                    st.success(f"↩️ Undid: **{undone_text}**! Dataset successfully restored.")
                    st.rerun()

        with st.expander("🕒 View Undo History Stack", expanded=False):
            undo_items = st.session_state.db.get_undo_history(limit=10)
            hist_rows = []
            for item in undo_items:
                hist_rows.append({
                    "Timestamp": item["timestamp"][:19].replace("T", " "),
                    "Action Type": item["action_type"],
                    "Description": item["action_description"],
                })
            st.dataframe(pd.DataFrame(hist_rows), use_container_width=True, hide_index=True)
            st.caption("Clicking 'Undo Last Action' reverses the topmost action and steps back in history.")

    # Dataset validation banner
    is_valid_data, data_errs, data_warns = validate_dataset(st.session_state.applicants, st.session_state.programs)
    if not is_valid_data:
        pref_err_count = sum(1 for e in data_errs if "ranks non-existent program" in e or "ranks unlisted" in e)
        st.error(f"⚠️ **Dataset Validation Alert**: {len(data_errs)} integrity issue{'s' if len(data_errs) != 1 else ''} detected.")

        if pref_err_count > 0:
            st.info(
                f"ℹ️ **Cause Identified**: {pref_err_count} applicant preferences reference program IDs that do not exist in the active program list. "
                f"This typically occurs after importing a program file (.xlsx/.csv) with new or modified program IDs."
            )
            col_fix1, col_fix2, col_fix3, col_fix4 = st.columns(4)
            with col_fix1:
                if st.button("🔄 Auto-Reconcile Dataset", type="primary", help="Smartly remaps matching programs and prunes unlisted IDs so data is immediately valid.", key="val_auto_reconcile"):
                    st.session_state.db.push_undo_state(
                        action_type="AUTO_RECONCILE",
                        action_description="Auto-reconciled applicant preferences and eligibility",
                        applicants=st.session_state.applicants,
                        programs=st.session_state.programs,
                    )
                    from fairshift.data_manager import SAMPLE_PROGRAMS
                    sample_p = [Program(**sp) for sp in SAMPLE_PROGRAMS]
                    rem, prun = reconcile_applicant_preferences(st.session_state.applicants, old_programs=sample_p, new_programs=st.session_state.programs)
                    p_pruned = prune_invalid_preferences(st.session_state.applicants, st.session_state.programs)
                    st.session_state.db.save_applicants(st.session_state.applicants)
                    st.session_state.db.log_audit_event("AUTO_RECONCILE", f"Reconciled {rem} applicants, pruned {prun + p_pruned} invalid preferences.")
                    st.success("Successfully reconciled applicant preferences with current programs!")
                    st.rerun()

            with col_fix2:
                if st.button("🧹 Prune Invalid Preferences", help="Removes all unlisted program references from applicant preference lists.", key="val_prune_btn"):
                    st.session_state.db.push_undo_state(
                        action_type="PRUNE_PREFERENCES",
                        action_description="Pruned invalid program preferences",
                        applicants=st.session_state.applicants,
                        programs=st.session_state.programs,
                    )
                    pruned = prune_invalid_preferences(st.session_state.applicants, st.session_state.programs)
                    st.session_state.db.save_applicants(st.session_state.applicants)
                    st.session_state.db.log_audit_event("PREFERENCES_PRUNED", f"Pruned {pruned} invalid preferences.")
                    st.success(f"Pruned {pruned} invalid preferences!")
                    st.rerun()

            with col_fix3:
                if st.button("🎲 Auto-Assign Valid Prefs", help="Generates valid ranked preferences and criteria for active applicants based on current programs.", key="val_auto_assign_btn"):
                    st.session_state.db.push_undo_state(
                        action_type="AUTO_ASSIGN_PREFS",
                        action_description="Generated valid preferences for all applicants",
                        applicants=st.session_state.applicants,
                        programs=st.session_state.programs,
                    )
                    updated = auto_assign_valid_preferences(st.session_state.applicants, st.session_state.programs)
                    st.session_state.db.save_applicants(st.session_state.applicants)
                    st.session_state.db.log_audit_event("PREFERENCES_ASSIGNED", f"Assigned valid preferences to {updated} applicants.")
                    st.success(f"Assigned valid preferences to {updated} applicants!")
                    st.rerun()

            with col_fix4:
                if st.button("👥 Clear All Applicants", help="Clears existing applicants to start fresh with a new applicant file upload.", key="val_clear_apps_btn"):
                    st.session_state.db.push_undo_state(
                        action_type="CLEAR_APPLICANTS",
                        action_description="Cleared all applicants",
                        applicants=st.session_state.applicants,
                        programs=st.session_state.programs,
                    )
                    st.session_state.applicants = []
                    st.session_state.db.save_applicants([])
                    st.session_state.db.log_audit_event("APPLICANTS_CLEARED", "Cleared all applicants.")
                    st.success("Cleared all applicants.")
                    st.rerun()

        with st.expander(f"🔍 Inspect All {len(data_errs)} Validation Errors", expanded=False):
            preview_count = min(20, len(data_errs))
            for err in data_errs[:preview_count]:
                st.write(f"- {err}")
            if len(data_errs) > preview_count:
                st.caption(f"... and {len(data_errs) - preview_count} more errors. Use the Action buttons above to resolve them.")
    elif data_warns:
        with st.expander(f"Dataset Warnings ({len(data_warns)})", expanded=False):
            for w in data_warns:
                st.write(f"- ℹ️ {w}")
    else:
        st.success("✅ Dataset is completely valid and ready for optimization.")

    sub_t1, sub_t2 = st.tabs(["🏫 Programs", "👥 Applicants"])

    # PROGRAMS SUBTAB
    with sub_t1:
        col_p1, col_p2 = st.columns([3, 2])
        with col_p1:
            st.subheader("Training Programs")
            search_p = st.text_input("🔍 Search Programs", "", placeholder="Filter by program ID, name, or criteria...").strip().lower()
            progs_df = export_programs_to_dataframe(st.session_state.programs)
            if search_p:
                progs_df = progs_df[
                    progs_df["program_id"].str.lower().str.contains(search_p)
                    | progs_df["name"].str.lower().str.contains(search_p)
                    | progs_df["eligibility_criteria"].str.lower().str.contains(search_p)
                ]

            st.dataframe(progs_df, use_container_width=True, hide_index=True)
            st.caption(f"Total Programs: **{len(st.session_state.programs)}** | Total Capacity: **{sum(p.capacity for p in st.session_state.programs)} seats**")

            # Export buttons
            csv_buf = io.StringIO()
            progs_df.to_csv(csv_buf, index=False)
            st.download_button("📥 Export Programs (CSV)", csv_buf.getvalue(), "programs.csv", "text/csv")

        with col_p2:
            st.subheader("Manage Programs")
            p_action = st.radio(
                "Action",
                ["➕ Add Program", "🔁 Replace / Edit Program", "🗑️ Remove Program", "📥 Import Programs"],
                horizontal=True,
                key="p_action_radio",
            )

            # --- ADD PROGRAM ---
            if p_action == "➕ Add Program":
                st.markdown("##### Add New Program")
                with st.form("add_program_form"):
                    p_id = st.text_input("Program ID (Unique)", placeholder="e.g. PROG_CLOUD").strip()
                    p_name = st.text_input("Program Name", placeholder="e.g. Cloud Architecture").strip()
                    p_cap = st.number_input("Seat Capacity", min_value=0, max_value=500, value=20)
                    p_crit = st.text_input("Eligibility Criteria", value="ALL", help="'ALL' or required tags").strip()
                    p_desc = st.text_area("Description", placeholder="Program details...")
                    submitted_p = st.form_submit_button("➕ Add Program Entry", type="primary")

                    if submitted_p:
                        new_p = Program(
                            program_id=p_id,
                            name=p_name,
                            capacity=int(p_cap),
                            eligibility_criteria=p_crit,
                            description=p_desc,
                        )
                        # Push undo state BEFORE adding
                        st.session_state.db.push_undo_state(
                            action_type="ADD_PROGRAM",
                            action_description=f"Added program '{new_p.program_id}' ({new_p.name})",
                            applicants=st.session_state.applicants,
                            programs=st.session_state.programs,
                        )
                        success, msg = add_program(st.session_state.programs, new_p)
                        if success:
                            st.session_state.db.save_programs(st.session_state.programs)
                            st.session_state.db.log_audit_event("PROGRAM_ADDED", msg)
                            st.success(msg)
                            st.rerun()
                        else:
                            # Revert undo state if addition failed validation
                            st.session_state.db.pop_undo_state()
                            st.error(msg)

            # --- REPLACE / EDIT PROGRAM ---
            elif p_action == "🔁 Replace / Edit Program":
                st.markdown("##### Replace / Edit Existing Program")
                if not st.session_state.programs:
                    st.info("No programs available to replace.")
                else:
                    prog_to_replace = st.selectbox(
                        "Select Program to Replace",
                        options=st.session_state.programs,
                        format_func=lambda p: f"{p.program_id} - {p.name} (Cap: {p.capacity})",
                        key="sel_prog_to_replace",
                    )

                    with st.form("replace_program_form"):
                        st.caption(f"Currently modifying: **{prog_to_replace.program_id}**")
                        r_id = st.text_input("Program ID", value=prog_to_replace.program_id).strip()
                        r_name = st.text_input("Program Name", value=prog_to_replace.name).strip()
                        r_cap = st.number_input("Seat Capacity", min_value=0, max_value=500, value=prog_to_replace.capacity)
                        r_crit = st.text_input("Eligibility Criteria", value=prog_to_replace.eligibility_criteria).strip()
                        r_desc = st.text_area("Description", value=prog_to_replace.description).strip()
                        cascade_pref = st.checkbox("Cascade ID rename to applicant preferences & eligibility if ID changes", value=True)
                        submitted_replace = st.form_submit_button("🔁 Replace Program Entry", type="primary")

                        if submitted_replace:
                            replacement_prog = Program(
                                program_id=r_id,
                                name=r_name,
                                capacity=int(r_cap),
                                eligibility_criteria=r_crit,
                                description=r_desc,
                            )
                            # Push undo state BEFORE replacing
                            st.session_state.db.push_undo_state(
                                action_type="REPLACE_PROGRAM",
                                action_description=f"Replaced program '{prog_to_replace.program_id}'",
                                applicants=st.session_state.applicants,
                                programs=st.session_state.programs,
                            )
                            success, msg = replace_program(
                                programs=st.session_state.programs,
                                old_program_id=prog_to_replace.program_id,
                                new_program=replacement_prog,
                                applicants=st.session_state.applicants,
                                update_applicant_preferences=cascade_pref,
                            )
                            if success:
                                st.session_state.db.save_programs(st.session_state.programs)
                                if cascade_pref:
                                    st.session_state.db.save_applicants(st.session_state.applicants)
                                st.session_state.db.log_audit_event("PROGRAM_REPLACED", msg)
                                st.success(msg)
                                st.rerun()
                            else:
                                st.session_state.db.pop_undo_state()
                                st.error(msg)

            # --- REMOVE PROGRAM ---
            elif p_action == "🗑️ Remove Program":
                st.markdown("##### Remove Program")
                if not st.session_state.programs:
                    st.info("No programs available to remove.")
                else:
                    prog_to_remove = st.selectbox(
                        "Select Program to Remove",
                        options=st.session_state.programs,
                        format_func=lambda p: f"{p.program_id} - {p.name} (Cap: {p.capacity})",
                        key="sel_prog_to_remove",
                    )

                    ranked_count = sum(1 for a in st.session_state.applicants if prog_to_remove.program_id in a.preferences)
                    st.warning(
                        f"⚠️ Removing **{prog_to_remove.program_id}** will remove {prog_to_remove.capacity} seats from the system. "
                        f"Currently, **{ranked_count} applicants** rank this program in their preferences."
                    )
                    clean_refs = st.checkbox("Automatically remove this program from applicant preference lists", value=True)

                    if st.button("🗑️ Confirm Remove Program", type="primary"):
                        # Push undo state BEFORE removing
                        st.session_state.db.push_undo_state(
                            action_type="REMOVE_PROGRAM",
                            action_description=f"Removed program '{prog_to_remove.program_id}' ({prog_to_remove.name})",
                            applicants=st.session_state.applicants,
                            programs=st.session_state.programs,
                        )
                        success, msg, affected = remove_program(
                            programs=st.session_state.programs,
                            program_id=prog_to_remove.program_id,
                            applicants=st.session_state.applicants,
                            clean_preferences=clean_refs,
                        )
                        if success:
                            st.session_state.db.save_programs(st.session_state.programs)
                            if clean_refs:
                                st.session_state.db.save_applicants(st.session_state.applicants)
                            st.session_state.db.log_audit_event("PROGRAM_REMOVED", msg)
                            st.success(msg)
                            st.rerun()
                        else:
                            st.session_state.db.pop_undo_state()
                            st.error(msg)

            # --- IMPORT PROGRAMS ---
            elif p_action == "📥 Import Programs":
                st.markdown("##### Import Programs (CSV or Excel)")
                import_mode_p = st.radio("Import Mode", ["Append / Merge with existing", "Replace all existing programs"], horizontal=True, key="imp_mode_p")

                col_imp_opt1, col_imp_opt2 = st.columns(2)
                with col_imp_opt1:
                    reconcile_p = st.checkbox(
                        "Reconcile applicant preferences & eligibility",
                        value=True,
                        help="Smartly remaps matching programs and prunes unlisted IDs from applicants so data remains valid.",
                    )
                with col_imp_opt2:
                    clear_apps_p = False
                    if import_mode_p == "Replace all existing programs":
                        clear_apps_p = st.checkbox(
                            "Clear existing applicants",
                            value=False,
                            help="Check this if you plan to upload a brand new applicant sheet next.",
                        )

                up_p = st.file_uploader("Upload Programs File", type=["csv", "xlsx", "xls"], key="up_p")
                if up_p is not None:
                    if st.button("Process Programs Upload", type="primary"):
                        new_progs, p_errors = import_programs_from_file(up_p.getvalue(), up_p.name)
                        if p_errors:
                            st.error("Errors importing programs:")
                            for pe in p_errors:
                                st.write(f"- {pe}")
                        else:
                            # Push undo state BEFORE applying import
                            file_ext = ".xlsx" if up_p.name.endswith((".xlsx", ".xls")) else ".csv"
                            st.session_state.db.push_undo_state(
                                action_type="IMPORT_PROGRAMS_XLSX" if file_ext == ".xlsx" else "IMPORT_PROGRAMS_CSV",
                                action_description=f"Imported programs from {up_p.name} ({import_mode_p})",
                                applicants=st.session_state.applicants,
                                programs=st.session_state.programs,
                            )
                            old_progs = list(st.session_state.programs)
                            if import_mode_p == "Replace all existing programs":
                                st.session_state.programs = new_progs
                                if clear_apps_p:
                                    st.session_state.applicants = []
                                    st.session_state.db.save_applicants([])
                                    desc = f"Replaced all programs with {len(new_progs)} imported programs from {up_p.name} and cleared existing applicants."
                                elif reconcile_p:
                                    remapped_cnt, pruned_cnt = reconcile_applicant_preferences(
                                        applicants=st.session_state.applicants,
                                        old_programs=old_progs,
                                        new_programs=new_progs,
                                    )
                                    extra_pruned = prune_invalid_preferences(st.session_state.applicants, new_progs)
                                    st.session_state.db.save_applicants(st.session_state.applicants)
                                    desc = (
                                        f"Replaced all programs with {len(new_progs)} imported programs from {up_p.name} "
                                        f"(reconciled {remapped_cnt} applicants, pruned {pruned_cnt + extra_pruned} obsolete preferences)."
                                    )
                                else:
                                    desc = f"Replaced all programs with {len(new_progs)} imported programs from {up_p.name}."
                            else:
                                count_added = 0
                                count_replaced = 0
                                for np in new_progs:
                                    existing_idx = next((i for i, p in enumerate(st.session_state.programs) if p.program_id == np.program_id), None)
                                    if existing_idx is not None:
                                        st.session_state.programs[existing_idx] = np
                                        count_replaced += 1
                                    else:
                                        st.session_state.programs.append(np)
                                        count_added += 1
                                if reconcile_p:
                                    pruned_cnt = prune_invalid_preferences(st.session_state.applicants, st.session_state.programs)
                                    if pruned_cnt > 0:
                                        st.session_state.db.save_applicants(st.session_state.applicants)
                                desc = f"Imported from {up_p.name}: Added {count_added}, updated/replaced {count_replaced} programs."

                            st.session_state.db.save_programs(st.session_state.programs)
                            st.session_state.db.log_audit_event("PROGRAMS_IMPORTED", desc)
                            st.success(desc)
                            st.rerun()

                # Dedicated quick undo button right inside the Programs Import view
                last_u = st.session_state.db.get_last_undo_state()
                if last_u and "IMPORT_PROGRAMS" in last_u["action_type"]:
                    st.markdown("---")
                    st.info(f"Last Import: **{last_u['action_description']}**")
                    if st.button(f"↩️ Undo This Import ({last_u['action_description'][:35]}...)", key="undo_prog_imp_btn", type="secondary"):
                        pop_res = st.session_state.db.pop_undo_state()
                        if pop_res:
                            st.session_state.applicants, st.session_state.programs, undone_text = pop_res
                            st.success(f"↩️ Undid: **{undone_text}**! Dataset successfully restored.")
                            st.rerun()

    # APPLICANTS SUBTAB
    with sub_t2:
        col_a1, col_a2 = st.columns([3, 2])
        with col_a1:
            st.subheader("Applicants List")
            filter_status = st.selectbox("Filter Status", ["All", "Active Only", "Withdrawn Only"])
            search_query = st.text_input("🔍 Search Applicants", "").strip().lower()

            apps_df = export_applicants_to_dataframe(st.session_state.applicants)
            if filter_status == "Active Only":
                apps_df = apps_df[apps_df["status"] == "active"]
            elif filter_status == "Withdrawn Only":
                apps_df = apps_df[apps_df["status"] == "withdrawn"]

            if search_query:
                apps_df = apps_df[
                    apps_df["applicant_id"].str.lower().str.contains(search_query)
                    | apps_df["name"].str.lower().str.contains(search_query)
                    | apps_df["preferences"].str.lower().str.contains(search_query)
                    | apps_df["eligibility"].str.lower().str.contains(search_query)
                ]

            st.dataframe(apps_df, use_container_width=True, hide_index=True)
            st.caption(
                f"Showing **{len(apps_df)}** of **{len(st.session_state.applicants)}** applicants "
                f"({active_apps_count} active, {withdrawn_apps_count} withdrawn)"
            )

            csv_a_buf = io.StringIO()
            apps_df.to_csv(csv_a_buf, index=False)
            st.download_button("📥 Export Applicants (CSV)", csv_a_buf.getvalue(), "applicants.csv", "text/csv")

        with col_a2:
            st.subheader("Manage Applicants")
            a_action = st.radio(
                "Action",
                ["➕ Add Applicant", "🔁 Replace / Edit Applicant", "🗑️ Remove Applicant", "📥 Import Applicants"],
                horizontal=True,
                key="a_action_radio",
            )

            all_prog_ids = [p.program_id for p in st.session_state.programs]

            # --- ADD APPLICANT ---
            if a_action == "➕ Add Applicant":
                st.markdown("##### Add New Applicant")
                with st.form("add_applicant_form"):
                    a_id = st.text_input("Applicant ID (Unique)", placeholder="e.g. APP201").strip()
                    a_name = st.text_input("Full Name", placeholder="e.g. Maya Lin").strip()
                    a_status = st.selectbox("Status", ["active", "withdrawn"])
                    a_elig = st.text_input("Eligibility Tags (comma-separated)", value="ALL").strip()
                    a_prefs = st.multiselect("Ranked Preferences (Order of selection = preference rank)", options=all_prog_ids)
                    a_notes = st.text_area("Notes", placeholder="Optional candidate notes...")
                    submitted_a = st.form_submit_button("➕ Add Applicant Entry", type="primary")

                    if submitted_a:
                        elig_list = [x.strip() for x in a_elig.split(",") if x.strip()]
                        new_a = Applicant(
                            applicant_id=a_id,
                            name=a_name,
                            eligibility=elig_list,
                            preferences=list(a_prefs),
                            status=a_status,
                            notes=a_notes,
                        )
                        # Push undo state BEFORE adding
                        st.session_state.db.push_undo_state(
                            action_type="ADD_APPLICANT",
                            action_description=f"Added applicant '{new_a.applicant_id}' ({new_a.name})",
                            applicants=st.session_state.applicants,
                            programs=st.session_state.programs,
                        )
                        success, msg = add_applicant(st.session_state.applicants, new_a)
                        if success:
                            st.session_state.db.save_applicants(st.session_state.applicants)
                            st.session_state.db.log_audit_event("APPLICANT_ADDED", msg)
                            st.success(msg)
                            st.rerun()
                        else:
                            st.session_state.db.pop_undo_state()
                            st.error(msg)

            # --- REPLACE / EDIT APPLICANT ---
            elif a_action == "🔁 Replace / Edit Applicant":
                st.markdown("##### Replace / Edit Existing Applicant")
                if not st.session_state.applicants:
                    st.info("No applicants available to replace.")
                else:
                    search_app_rep = st.text_input("🔍 Quick Find Applicant", "", placeholder="Filter by ID or Name...").strip().lower()
                    filtered_apps = st.session_state.applicants
                    if search_app_rep:
                        filtered_apps = [
                            a for a in filtered_apps
                            if search_app_rep in a.applicant_id.lower() or search_app_rep in a.name.lower()
                        ]

                    if not filtered_apps:
                        st.warning("No applicants match the filter.")
                    else:
                        app_to_replace = st.selectbox(
                            "Select Applicant to Replace",
                            options=filtered_apps,
                            format_func=lambda a: f"{a.applicant_id} - {a.name} ({a.status})",
                            key="sel_app_to_replace",
                        )

                        with st.form("replace_applicant_form"):
                            st.caption(f"Currently modifying: **{app_to_replace.applicant_id}**")
                            ar_id = st.text_input("Applicant ID", value=app_to_replace.applicant_id).strip()
                            ar_name = st.text_input("Full Name", value=app_to_replace.name).strip()
                            status_idx = 0 if app_to_replace.status.lower() == "active" else 1
                            ar_status = st.selectbox("Status", ["active", "withdrawn"], index=status_idx)
                            ar_elig = st.text_input("Eligibility Tags", value=", ".join(app_to_replace.eligibility)).strip()

                            valid_defaults = [p for p in app_to_replace.preferences if p in all_prog_ids]
                            ar_prefs = st.multiselect(
                                "Ranked Preferences (Order of selection = preference rank)",
                                options=all_prog_ids,
                                default=valid_defaults,
                            )
                            ar_notes = st.text_area("Notes", value=app_to_replace.notes).strip()
                            submitted_ar = st.form_submit_button("🔁 Replace Applicant Entry", type="primary")

                            if submitted_ar:
                                elig_list = [x.strip() for x in ar_elig.split(",") if x.strip()]
                                replacement_app = Applicant(
                                    applicant_id=ar_id,
                                    name=ar_name,
                                    eligibility=elig_list,
                                    preferences=list(ar_prefs),
                                    status=ar_status,
                                    notes=ar_notes,
                                )
                                # Push undo state BEFORE replacing
                                st.session_state.db.push_undo_state(
                                    action_type="REPLACE_APPLICANT",
                                    action_description=f"Replaced applicant '{app_to_replace.applicant_id}' ({app_to_replace.name})",
                                    applicants=st.session_state.applicants,
                                    programs=st.session_state.programs,
                                )
                                success, msg = replace_applicant(
                                    applicants=st.session_state.applicants,
                                    old_applicant_id=app_to_replace.applicant_id,
                                    new_applicant=replacement_app,
                                )
                                if success:
                                    st.session_state.db.save_applicants(st.session_state.applicants)
                                    st.session_state.db.log_audit_event("APPLICANT_REPLACED", msg)
                                    st.success(msg)
                                    st.rerun()
                                else:
                                    st.session_state.db.pop_undo_state()
                                    st.error(msg)

            # --- REMOVE APPLICANT ---
            elif a_action == "🗑️ Remove Applicant":
                st.markdown("##### Remove Applicant")
                if not st.session_state.applicants:
                    st.info("No applicants available to remove.")
                else:
                    search_app_rem = st.text_input("🔍 Quick Find Applicant to Remove", "", placeholder="Filter by ID or Name...").strip().lower()
                    filtered_rem_apps = st.session_state.applicants
                    if search_app_rem:
                        filtered_rem_apps = [
                            a for a in filtered_rem_apps
                            if search_app_rem in a.applicant_id.lower() or search_app_rem in a.name.lower()
                        ]

                    if not filtered_rem_apps:
                        st.warning("No applicants match the filter.")
                    else:
                        app_to_remove = st.selectbox(
                            "Select Applicant to Remove",
                            options=filtered_rem_apps,
                            format_func=lambda a: f"{a.applicant_id} - {a.name} ({a.status})",
                            key="sel_app_to_remove",
                        )

                        st.warning(
                            f"⚠️ Are you sure you want to remove **{app_to_remove.applicant_id}** ({app_to_remove.name})? "
                            f"Status: **{app_to_remove.status}**, Preferences: {len(app_to_remove.preferences)} programs."
                        )

                        if st.button("🗑️ Confirm Remove Applicant", type="primary"):
                            # Push undo state BEFORE removing
                            st.session_state.db.push_undo_state(
                                action_type="REMOVE_APPLICANT",
                                action_description=f"Removed applicant '{app_to_remove.applicant_id}' ({app_to_remove.name})",
                                applicants=st.session_state.applicants,
                                programs=st.session_state.programs,
                            )
                            success, msg = remove_applicant(st.session_state.applicants, app_to_remove.applicant_id)
                            if success:
                                st.session_state.db.save_applicants(st.session_state.applicants)
                                st.session_state.db.log_audit_event("APPLICANT_REMOVED", msg)
                                st.success(msg)
                                st.rerun()
                            else:
                                st.session_state.db.pop_undo_state()
                                st.error(msg)

            # --- IMPORT APPLICANTS ---
            elif a_action == "📥 Import Applicants":
                st.markdown("##### Import Applicants (CSV or Excel)")
                import_mode_a = st.radio("Import Mode", ["Append / Merge with existing", "Replace all existing applicants"], horizontal=True, key="imp_mode_a")
                clean_imported_a = st.checkbox(
                    "Automatically prune preferences referencing unlisted programs",
                    value=True,
                    help="Ensures all ranked preferences strictly match active training programs.",
                )
                up_a = st.file_uploader("Upload Applicants File", type=["csv", "xlsx", "xls"], key="up_a")
                if up_a is not None:
                    if st.button("Process Applicants Upload", type="primary"):
                        new_apps, a_errors = import_applicants_from_file(up_a.getvalue(), up_a.name)
                        if a_errors:
                            st.error("Errors importing applicants:")
                            for ae in a_errors:
                                st.write(f"- {ae}")
                        else:
                            # Push undo state BEFORE applying import
                            file_ext = ".xlsx" if up_a.name.endswith((".xlsx", ".xls")) else ".csv"
                            st.session_state.db.push_undo_state(
                                action_type="IMPORT_APPLICANTS_XLSX" if file_ext == ".xlsx" else "IMPORT_APPLICANTS_CSV",
                                action_description=f"Imported applicants from {up_a.name} ({import_mode_a})",
                                applicants=st.session_state.applicants,
                                programs=st.session_state.programs,
                            )
                            if import_mode_a == "Replace all existing applicants":
                                st.session_state.applicants = new_apps
                                desc = f"Replaced all applicants with {len(new_apps)} imported applicants from {up_a.name}."
                            else:
                                count_added = 0
                                count_replaced = 0
                                for na in new_apps:
                                    existing_idx = next((i for i, a in enumerate(st.session_state.applicants) if a.applicant_id == na.applicant_id), None)
                                    if existing_idx is not None:
                                        st.session_state.applicants[existing_idx] = na
                                        count_replaced += 1
                                    else:
                                        st.session_state.applicants.append(na)
                                        count_added += 1
                                desc = f"Imported from {up_a.name}: Added {count_added}, updated/replaced {count_replaced} applicants."

                            if clean_imported_a:
                                pruned_cnt = prune_invalid_preferences(st.session_state.applicants, st.session_state.programs)
                                if pruned_cnt > 0:
                                    desc += f" (pruned {pruned_cnt} unlisted program preferences)."

                            st.session_state.db.save_applicants(st.session_state.applicants)
                            st.session_state.db.log_audit_event("APPLICANTS_IMPORTED", desc)
                            st.success(desc)
                            st.rerun()

                # Dedicated quick undo button right inside the Applicants Import view
                last_u_a = st.session_state.db.get_last_undo_state()
                if last_u_a and "IMPORT_APPLICANTS" in last_u_a["action_type"]:
                    st.markdown("---")
                    st.info(f"Last Import: **{last_u_a['action_description']}**")
                    if st.button(f"↩️ Undo This Import ({last_u_a['action_description'][:35]}...)", key="undo_app_imp_btn", type="secondary"):
                        pop_res = st.session_state.db.pop_undo_state()
                        if pop_res:
                            st.session_state.applicants, st.session_state.programs, undone_text = pop_res
                            st.success(f"↩️ Undid: **{undone_text}**! Dataset successfully restored.")
                            st.rerun()


# ------------------------------------------
# TAB 3: INITIAL ALLOCATION
# ------------------------------------------
with tabs[2]:
    st.header("Initial Program Seat Allocation")
    st.write(
        "Run the mathematical allocation optimizer on current applicants and programs. "
        "Every solution is audited by the **independent validator** before saving as the current baseline."
    )

    btn_col1, btn_col2 = st.columns([2, 3])
    with btn_col1:
        run_solver = st.button("⚡ Compute Optimal Allocation", type="primary", use_container_width=True)

    if run_solver:
        with st.spinner("Executing Google OR-Tools CP-SAT multi-stage optimization..."):
            optimizer = AllocationOptimizer(
                applicants=st.session_state.applicants,
                programs=st.session_state.programs,
                config=opt_config,
            )
            calc_result = optimizer.solve(
                scenario_type="initial",
                scenario_description="Initial full allocation run",
            )
            st.session_state.current_calc_result = calc_result

    if "current_calc_result" in st.session_state:
        res: AllocationResult = st.session_state.current_calc_result

        # Status and Validation Banner
        st.markdown("---")
        badge_html = render_solver_badge(res.solver_status)
        v_status = res.validation_result.is_valid if res.validation_result else False

        b_c1, b_c2, b_c3 = st.columns([2, 2, 2])
        with b_c1:
            st.markdown(f"**Solver Outcome:** {badge_html}", unsafe_allow_html=True)
            st.caption(f"Wall-clock solve time: **{res.wall_time_seconds}s**")
        with b_c2:
            if v_status:
                st.success("✅ Independent Validation: PASS")
            else:
                st.error("❌ Independent Validation: FAILED")
            st.caption("Audited by AllocationValidator")
        with b_c3:
            st.metric("Total Placements", f"{res.total_assigned}", f"Score: {res.preference_score:,} pts")

        # Validation Details
        if res.validation_result and res.validation_result.errors:
            st.error("Validation Violations Detected:")
            for err in res.validation_result.errors:
                st.write(f"- {err}")

        # Quality Metrics
        q_c1, q_c2, q_c3, q_c4 = st.columns(4)
        active_apps = [a for a in st.session_state.applicants if a.is_active]
        unassigned_count = len(res.unassigned_applicants)
        first_choices = res.rank_distribution.get(1, 0)
        first_choice_pct = (first_choices / res.total_assigned * 100) if res.total_assigned > 0 else 0

        with q_c1:
            st.metric("Active Applicants", f"{len(active_apps)}")
        with q_c2:
            st.metric("Unassigned Applicants", f"{unassigned_count}")
        with q_c3:
            st.metric("Matched to 1st Choice", f"{first_choices} ({first_choice_pct:.1f}%)")
        with q_c4:
            st.metric("Capacity Utilized", f"{res.total_assigned} / {total_cap}")

        # Save as Baseline Button
        st.markdown("---")
        save_col1, save_col2 = st.columns([2, 3])
        with save_col1:
            if st.button("💾 Save as Current Baseline Allocation", use_container_width=True, disabled=not v_status):
                st.session_state.db.save_allocation_run(
                    result=res,
                    applicants=st.session_state.applicants,
                    programs=st.session_state.programs,
                    set_as_baseline=True,
                )
                st.session_state.baseline_result = res
                st.success(f"Allocation `{res.run_id}` saved as current active baseline!")
                st.rerun()

        # Detailed Tables
        alloc_tab1, alloc_tab2, alloc_tab3 = st.tabs(["📋 Assigned Applicants", "⚠️ Unassigned Applicants", "🏫 Capacity Utilization"])

        app_map = {a.applicant_id: a for a in st.session_state.applicants}
        prog_map = {p.program_id: p for p in st.session_state.programs}

        with alloc_tab1:
            rows = []
            for app_id, prog_id in res.assignments.items():
                app = app_map.get(app_id)
                prog = prog_map.get(prog_id)
                rank = app.preference_rank(prog_id) if app else None
                pts = opt_config.points_per_rank[rank - 1] if rank and 1 <= rank <= len(opt_config.points_per_rank) else 1
                rows.append({
                    "Applicant ID": app_id,
                    "Name": app.name if app else app_id,
                    "Assigned Program": prog.name if prog else prog_id,
                    "Program ID": prog_id,
                    "Preference Rank": f"Choice #{rank}" if rank else "Unranked",
                    "Score Points": pts,
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        with alloc_tab2:
            unassigned_rows = []
            for app_id in res.unassigned_applicants:
                app = app_map.get(app_id)
                if app:
                    unassigned_rows.append({
                        "Applicant ID": app.applicant_id,
                        "Name": app.name,
                        "Preferences": ", ".join(app.preferences),
                        "Eligibility": ", ".join(app.eligibility),
                        "Reason": "All requested programs filled by higher-priority/better-matched candidates.",
                    })
            st.dataframe(pd.DataFrame(unassigned_rows), use_container_width=True, hide_index=True)

        with alloc_tab3:
            cap_rows = []
            for p_id, p_stats in res.capacity_utilization.items():
                cap_rows.append({
                    "Program ID": p_id,
                    "Program Name": p_stats["name"],
                    "Capacity": p_stats["capacity"],
                    "Assigned": p_stats["assigned"],
                    "Remaining Seats": p_stats["remaining"],
                    "Fill %": f"{p_stats['fill_percentage']:.1f}%",
                })
            st.dataframe(pd.DataFrame(cap_rows), use_container_width=True, hide_index=True)


# ------------------------------------------
# TAB 4: WITHDRAWAL IMPACT ANALYSIS
# ------------------------------------------
with tabs[3]:
    st.header("Applicant Withdrawal Impact Analysis")
    st.write(
        "Analyze what happens when an applicant withdraws. "
        "The solver holds the prior allocation as the baseline, releases the withdrawn applicant's seat, "
        "and optimizes the remaining allocation while strictly **minimizing unnecessary disruption** to existing assignments."
    )

    if not st.session_state.baseline_result:
        st.warning("⚠️ Please compute and save an **Initial Allocation** as the baseline first.")
    else:
        baseline: AllocationResult = st.session_state.baseline_result
        assigned_apps = [
            a for a in st.session_state.applicants
            if a.applicant_id in baseline.assignments and a.is_active
        ]

        w_col1, w_col2 = st.columns([2, 1])
        with w_col1:
            selected_app_id = st.selectbox(
                "Select Applicant to Withdraw",
                options=[a.applicant_id for a in assigned_apps],
                format_func=lambda x: f"{x} - {next((a.name for a in assigned_apps if a.applicant_id == x), x)} (Currently in: {baseline.assignments.get(x)})",
            )
        with w_col2:
            st.write("")
            st.write("")
            run_withdrawal = st.button("🔍 Analyze Withdrawal Ripple Effect", type="primary", use_container_width=True)

        if run_withdrawal and selected_app_id:
            with st.spinner("Recalculating allocation and computing ripple effects..."):
                analyzer = ScenarioAnalyzer(
                    applicants=st.session_state.applicants,
                    programs=st.session_state.programs,
                    baseline_result=baseline,
                )
                scen_res, report = analyzer.analyze_withdrawal(selected_app_id, config=opt_config)
                st.session_state.last_scenario_result = scen_res
                st.session_state.last_impact_report = report

        if st.session_state.last_impact_report and st.session_state.last_impact_report.scenario_type == "withdrawal":
            rep: ImpactReport = st.session_state.last_impact_report
            st.markdown("---")

            # Impact summary cards
            ic1, ic2, ic3, ic4 = st.columns(4)
            with ic1:
                st.metric("Total Assigned", f"{rep.total_assigned_after}", f"{rep.net_assigned_change:+d} vs baseline")
            with ic2:
                st.metric("Preference Score", f"{rep.pref_score_after:,}", f"{rep.pref_score_change:+d} pts")
            with ic3:
                st.metric("Reassignments", f"{rep.reassignment_count}")
            with ic4:
                st.metric("Applicants Affected", f"{rep.affected_count}")

            # Factual Explanation Box
            st.subheader("Factual Solver Chain of Events")
            for exp in rep.factual_explanations:
                st.info(f"📌 {exp}")

            # Changes Table
            st.subheader("Applicant Assignment Trajectories")
            change_filter = st.selectbox(
                "Filter Trajectories",
                ["All Affected", "Promoted to Better Rank", "Newly Assigned", "Stayed Unchanged", "All Applicants"],
            )

            traj_rows = []
            for c in rep.changes:
                if change_filter == "All Affected" and c.change_type == "stayed":
                    continue
                if change_filter == "Promoted to Better Rank" and c.change_type != "promoted":
                    continue
                if change_filter == "Newly Assigned" and c.change_type != "newly_assigned":
                    continue
                if change_filter == "Stayed Unchanged" and c.change_type != "stayed":
                    continue

                badge = f"badge-{c.change_type}"
                traj_rows.append({
                    "Applicant ID": c.applicant_id,
                    "Name": c.name,
                    "Status": c.status,
                    "Baseline Program": c.before_program_name or "Unassigned",
                    "Baseline Rank": f"#{c.before_rank}" if c.before_rank else "-",
                    "New Program": c.after_program_name or "Unassigned",
                    "New Rank": f"#{c.after_rank}" if c.after_rank else "-",
                    "Change Type": c.change_type.replace("_", " ").title(),
                    "Explanation": c.details,
                })

            st.dataframe(pd.DataFrame(traj_rows), use_container_width=True, hide_index=True)

            # Option to commit
            st.markdown("---")
            c_col1, c_col2 = st.columns([2, 3])
            with c_col1:
                if st.button("✅ Commit Withdrawal & Set as New Baseline", use_container_width=True):
                    # Mark applicant withdrawn in persistent list
                    withdrawn_id = selected_app_id
                    for a in st.session_state.applicants:
                        if a.applicant_id == withdrawn_id:
                            a.status = "withdrawn"

                    st.session_state.db.save_applicants(st.session_state.applicants)
                    st.session_state.db.save_allocation_run(
                        result=st.session_state.last_scenario_result,
                        applicants=st.session_state.applicants,
                        programs=st.session_state.programs,
                        set_as_baseline=True,
                    )
                    st.session_state.baseline_result = st.session_state.last_scenario_result
                    st.success(f"Applicant {withdrawn_id} permanently withdrawn. New baseline saved!")
                    st.rerun()


# ------------------------------------------
# TAB 5: CAPACITY CHANGES
# ------------------------------------------
with tabs[4]:
    st.header("Program Capacity Change Analysis")
    st.write(
        "Simulate adding or removing seats from any training program. "
        "The model recalculates assignments while preserving existing assignments wherever possible and "
        "details the ripple effect on waitlisted or displaced applicants."
    )

    if not st.session_state.baseline_result:
        st.warning("⚠️ Please compute and save an **Initial Allocation** as the baseline first.")
    else:
        baseline: AllocationResult = st.session_state.baseline_result
        prog_options = [p.program_id for p in st.session_state.programs]

        cap_col1, cap_col2, cap_col3 = st.columns([2, 1, 1])
        with cap_col1:
            sel_prog_id = st.selectbox(
                "Select Program to Adjust",
                options=prog_options,
                format_func=lambda x: f"{x} - {next((p.name for p in st.session_state.programs if p.program_id == x), x)} (Current Cap: {next((p.capacity for p in st.session_state.programs if p.program_id == x), 0)})",
            )
        target_p = next(p for p in st.session_state.programs if p.program_id == sel_prog_id)

        with cap_col2:
            new_capacity_val = st.number_input(
                "New Capacity",
                min_value=0,
                max_value=200,
                value=target_p.capacity,
                step=1,
            )

        with cap_col3:
            st.write("")
            st.write("")
            run_cap_analysis = st.button("⚖️ Analyze Capacity Change", type="primary", use_container_width=True)

        if run_cap_analysis:
            with st.spinner("Analyzing capacity adjustment impact..."):
                analyzer = ScenarioAnalyzer(
                    applicants=st.session_state.applicants,
                    programs=st.session_state.programs,
                    baseline_result=baseline,
                )
                scen_res, report = analyzer.analyze_capacity_change(
                    program_id=sel_prog_id,
                    new_capacity=int(new_capacity_val),
                    config=opt_config,
                )
                st.session_state.last_scenario_result = scen_res
                st.session_state.last_impact_report = report

        if st.session_state.last_impact_report and st.session_state.last_impact_report.scenario_type == "capacity_change":
            rep: ImpactReport = st.session_state.last_impact_report
            st.markdown("---")

            # Metrics
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric("Total Assigned", f"{rep.total_assigned_after}", f"{rep.net_assigned_change:+d}")
            with c2:
                st.metric("Preference Score", f"{rep.pref_score_after:,}", f"{rep.pref_score_change:+d} pts")
            with c3:
                st.metric("Reassignments", f"{rep.reassignment_count}")
            with c4:
                st.metric("Applicants Affected", f"{rep.affected_count}")

            # Explanations
            st.subheader("Factual Solver Impact Analysis")
            for exp in rep.factual_explanations:
                st.info(f"📌 {exp}")

            # Capacity Changes Table
            st.subheader("Program Capacity Breakdown")
            cap_diff_rows = []
            for p_id, d in rep.capacity_diffs.items():
                cap_diff_rows.append({
                    "Program": d["name"],
                    "Capacity (Before)": d["capacity_before"],
                    "Capacity (After)": d["capacity_after"],
                    "Assigned (Before)": d["assigned_before"],
                    "Assigned (After)": d["assigned_after"],
                    "Net Assigned Change": f"{d['net_assigned_change']:+d}",
                    "Remaining Seats": d["remaining_after"],
                })
            st.dataframe(pd.DataFrame(cap_diff_rows), use_container_width=True, hide_index=True)

            # Affected Applicants Table
            st.subheader("Affected Applicants")
            aff_rows = []
            for c in rep.changes:
                if c.change_type != "stayed":
                    aff_rows.append({
                        "Applicant ID": c.applicant_id,
                        "Name": c.name,
                        "Before": c.before_program_name or "Unassigned",
                        "After": c.after_program_name or "Unassigned",
                        "Change": c.change_type.replace("_", " ").title(),
                        "Details": c.details,
                    })
            if aff_rows:
                st.dataframe(pd.DataFrame(aff_rows), use_container_width=True, hide_index=True)
            else:
                st.write("No applicants were displaced or reassigned.")

            # Option to commit
            st.markdown("---")
            if st.button("✅ Commit Capacity Change as Baseline"):
                # Update program capacity
                for p in st.session_state.programs:
                    if p.program_id == sel_prog_id:
                        p.capacity = int(new_capacity_val)

                st.session_state.db.save_programs(st.session_state.programs)
                st.session_state.db.save_allocation_run(
                    result=st.session_state.last_scenario_result,
                    applicants=st.session_state.applicants,
                    programs=st.session_state.programs,
                    set_as_baseline=True,
                )
                st.session_state.baseline_result = st.session_state.last_scenario_result
                st.success(f"Program {sel_prog_id} capacity permanently updated to {new_capacity_val}. New baseline saved!")
                st.rerun()


# ------------------------------------------
# TAB 6: APPEALS (COUNTERFACTUAL ANALYSIS)
# ------------------------------------------
with tabs[5]:
    st.header("Counterfactual Appeal Analysis")
    st.write(
        "Evaluate an applicant's appeal for a specific program placement. "
        "The optimizer enforces the requested placement as a scenario condition (if feasible) and audits the ripple effect on other applicants. "
        "**The baseline allocation is never overwritten just by evaluating an appeal.**"
    )

    if not st.session_state.baseline_result:
        st.warning("⚠️ Please compute and save an **Initial Allocation** as the baseline first.")
    else:
        baseline: AllocationResult = st.session_state.baseline_result

        ap_col1, ap_col2, ap_col3 = st.columns([2, 2, 1])
        with ap_col1:
            sel_app_appeal = st.selectbox(
                "Appellant (Applicant)",
                options=[a.applicant_id for a in st.session_state.applicants if a.is_active],
                format_func=lambda x: f"{x} - {next((a.name for a in st.session_state.applicants if a.applicant_id == x), x)} (Assigned: {baseline.assignments.get(x, 'UNASSIGNED')})",
            )
        with ap_col2:
            sel_prog_appeal = st.selectbox(
                "Requested Program",
                options=[p.program_id for p in st.session_state.programs],
                format_func=lambda x: f"{x} - {next((p.name for p in st.session_state.programs if p.program_id == x), x)}",
            )
        with ap_col3:
            st.write("")
            st.write("")
            run_appeal = st.button("⚖️ Evaluate Appeal", type="primary", use_container_width=True)

        if run_appeal:
            with st.spinner("Evaluating counterfactual appeal scenario..."):
                analyzer = ScenarioAnalyzer(
                    applicants=st.session_state.applicants,
                    programs=st.session_state.programs,
                    baseline_result=baseline,
                )
                scen_res, report = analyzer.analyze_appeal(
                    applicant_id=sel_app_appeal,
                    requested_program_id=sel_prog_appeal,
                    config=opt_config,
                )
                st.session_state.last_scenario_result = scen_res
                st.session_state.last_impact_report = report

        if st.session_state.last_impact_report and st.session_state.last_impact_report.scenario_type == "appeal":
            rep: ImpactReport = st.session_state.last_impact_report
            st.markdown("---")

            # Appeal Feasibility Banner
            if rep.is_feasible:
                st.success(f"✅ Appeal Placement is Mathematically Feasible! Solver Status: {rep.solver_status.value}")
            else:
                st.error(f"❌ Appeal Placement is INFEASIBLE. Solver Status: {rep.solver_status.value}")

            # Explanations
            st.subheader("Factual Explanation of Appeal Outcome")
            for exp in rep.factual_explanations:
                if rep.is_feasible:
                    st.info(f"📌 {exp}")
                else:
                    st.warning(f"⚠️ {exp}")

            if rep.is_feasible:
                # Comparison cards
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    st.metric("Total Placements", f"{rep.total_assigned_after}", f"{rep.net_assigned_change:+d}")
                with c2:
                    st.metric("Preference Score", f"{rep.pref_score_after:,}", f"{rep.pref_score_change:+d} pts")
                with c3:
                    st.metric("Reassignments Required", f"{rep.reassignment_count}")
                with c4:
                    st.metric("Other Applicants Affected", f"{rep.affected_count}")

                st.subheader("Applicants Displaced or Reassigned by Appeal")
                appeal_changes = []
                for c in rep.changes:
                    if c.change_type != "stayed":
                        appeal_changes.append({
                            "Applicant ID": c.applicant_id,
                            "Name": c.name,
                            "Before Program": c.before_program_name or "Unassigned",
                            "After Program": c.after_program_name or "Unassigned",
                            "Rank Delta": f"#{c.before_rank or '-'} ➔ #{c.after_rank or '-'}",
                            "Action": c.change_type.replace("_", " ").title(),
                            "Details": c.details,
                        })
                st.dataframe(pd.DataFrame(appeal_changes), use_container_width=True, hide_index=True)

                st.markdown("---")
                if st.button("⚡ Apply & Grant Appeal as New Baseline Allocation"):
                    st.session_state.db.save_allocation_run(
                        result=st.session_state.last_scenario_result,
                        applicants=st.session_state.applicants,
                        programs=st.session_state.programs,
                        set_as_baseline=True,
                    )
                    st.session_state.baseline_result = st.session_state.last_scenario_result
                    st.success("Appeal officially granted! Baseline allocation updated.")
                    st.rerun()


# ------------------------------------------
# TAB 7: ALLOCATION HISTORY & AUDIT TRAIL
# ------------------------------------------
with tabs[6]:
    st.header("Audit History & Run Log")
    st.write(
        "Complete historical record of allocation runs, solver outcomes, wall-clock times, "
        "independent validation results, and system audit events persisted in SQLite."
    )

    hist_tab1, hist_tab2 = st.tabs(["📊 Saved Allocation Runs", "📝 System Audit Trail"])

    with hist_tab1:
        runs = st.session_state.db.get_all_runs(limit=50)
        if not runs:
            st.info("No runs logged in database yet.")
        else:
            runs_df = pd.DataFrame(runs)
            # Reorder & format
            st.dataframe(
                runs_df[[
                    "run_id", "timestamp", "scenario_type", "scenario_description",
                    "solver_status", "total_assigned", "preference_score",
                    "reassignment_count", "is_valid", "is_active_baseline", "wall_time_seconds"
                ]],
                use_container_width=True,
                hide_index=True,
            )

            st.markdown("---")
            st.subheader("Inspect Past Run Details")
            run_ids = [r["run_id"] for r in runs]
            sel_run_id = st.selectbox("Select Run to Inspect", options=run_ids)
            if sel_run_id:
                run_detail = st.session_state.db.get_run(sel_run_id)
                if run_detail:
                    r1, r2, r3 = st.columns(3)
                    with r1:
                        st.write(f"**Scenario:** {run_detail['scenario_description']}")
                        st.write(f"**Timestamp:** {run_detail['timestamp']}")
                    with r2:
                        st.write(f"**Solver Status:** {run_detail['solver_status']}")
                        st.write(f"**Wall Time:** {run_detail['wall_time_seconds']}s")
                    with r3:
                        st.write(f"**Total Assigned:** {run_detail['total_assigned']}")
                        st.write(f"**Preference Score:** {run_detail['preference_score']}")

                    # Restore as baseline button
                    if not run_detail["is_active_baseline"]:
                        if st.button("↺ Restore this Run as Active Baseline"):
                            st.session_state.db.set_active_baseline(sel_run_id)
                            st.session_state.baseline_result = AllocationResult(
                                run_id=run_detail["run_id"],
                                timestamp=run_detail["timestamp"],
                                scenario_type=run_detail["scenario_type"],
                                scenario_description=run_detail["scenario_description"],
                                solver_status=SolverStatusEnum(run_detail["solver_status"]),
                                wall_time_seconds=run_detail["wall_time_seconds"],
                                assignments=run_detail.get("assignments_map", {}),
                                total_assigned=run_detail["total_assigned"],
                                preference_score=run_detail["preference_score"],
                                reassignment_count=run_detail["reassignment_count"],
                                rank_distribution={int(k): v for k, v in run_detail.get("rank_distribution", {}).items()},
                                capacity_utilization=run_detail.get("capacity_utilization", {}),
                                objective_measures=run_detail.get("objective_measures", {}),
                            )
                            st.success(f"Run {sel_run_id} restored as active baseline!")
                            st.rerun()

                    st.markdown("**Assignments Sample:**")
                    st.dataframe(pd.DataFrame(run_detail["assignments_list"]), use_container_width=True, hide_index=True)

    with hist_tab2:
        audit_events = st.session_state.db.get_audit_trail(limit=100)
        if not audit_events:
            st.info("No audit events recorded.")
        else:
            audit_df = pd.DataFrame(audit_events)
            st.dataframe(
                audit_df[["id", "timestamp", "event_type", "run_id", "description"]],
                use_container_width=True,
                hide_index=True,
            )


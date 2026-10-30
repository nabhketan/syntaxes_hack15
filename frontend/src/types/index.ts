export interface Applicant {
  applicant_id: str;
  name: str;
  eligibility: string[];
  preferences: string[];
  status: 'active' | 'withdrawn' | string;
  notes?: string;
}

export type str = string;

export interface Program {
  program_id: string;
  name: string;
  capacity: number;
  eligibility_criteria: string;
  description: string;
}

export interface OptimizationConfig {
  priority_mode: 'lexicographic' | 'weighted';
  only_assign_preferred: boolean;
  time_limit_seconds: number;
  points_per_rank: number[];
  weight_assigned: number;
  weight_preference: number;
  weight_stability: number;
}

export type SolverStatus =
  | 'Optimal'
  | 'Feasible, not proven optimal'
  | 'Infeasible'
  | 'Unknown or timed out';

export interface ValidationResult {
  is_valid: boolean;
  checked_rules: Record<string, boolean>;
  errors: string[];
  warnings: string[];
  metrics?: Record<string, any>;
}

export interface CapacityUtilizationItem {
  name: string;
  capacity: number;
  assigned: number;
  remaining: number;
  fill_percentage: number;
}

export interface AllocationResult {
  run_id: string;
  timestamp: string;
  scenario_type: string;
  scenario_description: string;
  solver_status: SolverStatus;
  wall_time_seconds: number;
  assignments: Record<string, string>;
  unassigned_applicants: string[];
  total_assigned: number;
  preference_score: number;
  reassignment_count: number;
  rank_distribution: Record<number | string, number>;
  capacity_utilization: Record<string, CapacityUtilizationItem>;
  objective_measures: Record<string, any>;
  validation_result?: ValidationResult | null;
  baseline_run_id?: string | null;
}

export interface ApplicantTrajectory {
  applicant_id: string;
  name: string;
  status: string;
  before_program_id?: string | null;
  before_program_name?: string | null;
  before_rank?: number | null;
  after_program_id?: string | null;
  after_program_name?: string | null;
  after_rank?: number | null;
  change_type: 'promoted' | 'demoted' | 'stayed' | 'newly_assigned' | 'unassigned' | 'withdrawn';
  details: string;
}

export interface CapacityDiffItem {
  name: string;
  capacity_before: number;
  capacity_after: number;
  assigned_before: number;
  assigned_after: number;
  net_assigned_change: number;
  remaining_after: number;
}

export interface ImpactReport {
  scenario_type: 'withdrawal' | 'capacity_change' | 'appeal';
  scenario_description: string;
  solver_status: SolverStatus;
  is_feasible: boolean;
  total_assigned_before: number;
  total_assigned_after: number;
  net_assigned_change: number;
  pref_score_before: number;
  pref_score_after: number;
  pref_score_change: number;
  reassignment_count: number;
  affected_count: number;
  changes: ApplicantTrajectory[];
  factual_explanations: string[];
  capacity_diffs: Record<string, CapacityDiffItem>;
  timestamp: string;
}

export interface SystemStatus {
  total_applicants: number;
  active_applicants: number;
  withdrawn_applicants: number;
  total_programs: number;
  total_capacity: number;
  has_baseline: boolean;
  baseline_summary?: {
    run_id: string | null;
    total_assigned: number;
    solver_status: string | null;
    wall_time_seconds: number;
    preference_score: number;
  } | null;
}

export interface ValidationStatus {
  is_valid: boolean;
  errors: string[];
  warnings: string[];
  error_count: number;
  warning_count: number;
  unlisted_pref_count: number;
}

export interface UndoStatus {
  can_undo: boolean;
  undo_count: number;
  last_action?: {
    id: number;
    timestamp: string;
    action_type: string;
    action_description: string;
  } | null;
  history: Array<{
    id: number;
    timestamp: string;
    action_type: string;
    action_description: string;
  }>;
}

export interface RunSummary {
  run_id: string;
  timestamp: string;
  scenario_type: string;
  scenario_description: string;
  solver_status: string;
  total_assigned: number;
  preference_score: number;
  reassignment_count: number;
  is_valid: number | boolean;
  is_active_baseline: number | boolean;
  wall_time_seconds: number;
}

export interface RunDetail extends RunSummary {
  assignments_list: Array<{
    applicant_id: string;
    name: string;
    assigned_program: string;
    program_id: string;
    preference_rank: string;
    score_points: number;
  }>;
  assignments_map: Record<string, string>;
  rank_distribution: Record<string, number>;
  capacity_utilization: Record<string, CapacityUtilizationItem>;
  objective_measures: Record<string, any>;
  validation?: ValidationResult;
}

export interface AuditEvent {
  id: number;
  timestamp: string;
  event_type: string;
  run_id?: string | null;
  description: string;
}


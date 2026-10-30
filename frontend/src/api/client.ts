import {
  Applicant,
  Program,
  OptimizationConfig,
  AllocationResult,
  ImpactReport,
  SystemStatus,
  ValidationStatus,
  UndoStatus,
  RunSummary,
  RunDetail,
  AuditEvent,
} from '../types';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  const response = await fetch(url, {
    ...options,
    headers: {
      Accept: 'application/json',
      ...options?.headers,
    },
  });

  if (!response.ok) {
    let errorDetail = `Request failed: ${response.status} ${response.statusText}`;
    try {
      const errJson = await response.json();
      if (errJson.detail) {
        if (typeof errJson.detail === 'string') {
          errorDetail = errJson.detail;
        } else if (Array.isArray(errJson.detail)) {
          errorDetail = errJson.detail.map((e: any) => e.msg || JSON.stringify(e)).join(', ');
        } else if (errJson.detail.errors && Array.isArray(errJson.detail.errors)) {
          errorDetail = errJson.detail.errors.join(' | ');
        }
      }
    } catch {
      // Non-JSON error body
    }
    throw new Error(errorDetail);
  }

  return response.json();
}

export const api = {
  // System & Status
  getStatus: () => request<SystemStatus>('/api/status'),
  getBaseline: () => request<{ baseline: AllocationResult | null }>('/api/baseline'),
  setBaseline: (runId: string) =>
    request<{ success: boolean; active_baseline_run_id: string }>(`/api/baseline/set?run_id=${encodeURIComponent(runId)}`, {
      method: 'POST',
    }),
  resetSampleData: () => request<{ success: boolean; message: string }>('/api/dataset/reset', { method: 'POST' }),

  // Programs
  getPrograms: () => request<{ programs: Program[] }>('/api/programs'),
  createProgram: (prog: { program_id: string; name: string; capacity: number; eligibility_criteria: string; description: string }) =>
    request<{ success: boolean; message: string; program: Program }>('/api/programs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(prog),
    }),
  updateProgram: (
    oldId: string,
    prog: { name: string; capacity: number; eligibility_criteria: string; description: string; new_program_id?: string; cascade_preference_rename: boolean }
  ) =>
    request<{ success: boolean; message: string; program: Program }>(`/api/programs/${encodeURIComponent(oldId)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(prog),
    }),
  deleteProgram: (id: string, cleanPreferences: boolean = true) =>
    request<{ success: boolean; message: string; affected_applicants: number }>(
      `/api/programs/${encodeURIComponent(id)}?clean_preferences=${cleanPreferences}`,
      { method: 'DELETE' }
    ),
  importPrograms: (file: File, importMode: 'replace' | 'merge', reconcile: boolean, clearApps: boolean) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('import_mode', importMode);
    formData.append('reconcile_preferences', String(reconcile));
    formData.append('clear_applicants', String(clearApps));
    return request<{ success: boolean; message: string; programs_count: number }>('/api/programs/import', {
      method: 'POST',
      body: formData,
    });
  },
  getProgramsCsvUrl: () => `${API_BASE}/api/programs/export/csv`,

  // Applicants
  getApplicants: (status?: string, search?: string) => {
    const params = new URLSearchParams();
    if (status) params.append('status', status);
    if (search) params.append('search', search);
    const query = params.toString() ? `?${params.toString()}` : '';
    return request<{ applicants: Applicant[]; total: number }>(`/api/applicants${query}`);
  },
  createApplicant: (app: { applicant_id: string; name: string; eligibility: string[]; preferences: string[]; status: string; notes: string }) =>
    request<{ success: boolean; message: string; applicant: Applicant }>('/api/applicants', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(app),
    }),
  updateApplicant: (
    oldId: string,
    app: { name: string; eligibility: string[]; preferences: string[]; status: string; notes: string; new_applicant_id?: string }
  ) =>
    request<{ success: boolean; message: string; applicant: Applicant }>(`/api/applicants/${encodeURIComponent(oldId)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(app),
    }),
  deleteApplicant: (id: string) =>
    request<{ success: boolean; message: string }>(`/api/applicants/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  importApplicants: (file: File, importMode: 'replace' | 'merge', cleanInvalid: boolean) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('import_mode', importMode);
    formData.append('clean_invalid_preferences', String(cleanInvalid));
    return request<{ success: boolean; message: string; applicants_count: number }>('/api/applicants/import', {
      method: 'POST',
      body: formData,
    });
  },
  getApplicantsCsvUrl: () => `${API_BASE}/api/applicants/export/csv`,

  // Validation & Repair
  getValidation: () => request<ValidationStatus>('/api/validation'),
  autoReconcile: () => request<{ success: boolean; message: string }>('/api/validation/auto-reconcile', { method: 'POST' }),
  prunePreferences: () => request<{ success: boolean; message: string; pruned_count: number }>('/api/validation/prune-preferences', { method: 'POST' }),
  autoAssignPreferences: () =>
    request<{ success: boolean; message: string; updated_count: number }>('/api/validation/auto-assign-preferences', { method: 'POST' }),
  clearApplicants: () => request<{ success: boolean; message: string }>('/api/validation/clear-applicants', { method: 'POST' }),

  // Undo
  getUndoStatus: () => request<UndoStatus>('/api/undo/status'),
  undo: () => request<{ success: boolean; undone_action: string; applicants_count: number; programs_count: number }>('/api/undo', { method: 'POST' }),

  // Allocation
  solveAllocation: (config: OptimizationConfig, scenarioType = 'initial', scenarioDescription = 'Initial full allocation run') =>
    request<{ result: AllocationResult }>('/api/allocation/solve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ config, scenario_type: scenarioType, scenario_description: scenarioDescription }),
    }),
  saveBaseline: (result: AllocationResult) =>
    request<{ success: boolean; run_id: string; message: string }>('/api/allocation/save-baseline', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ result }),
    }),

  // Scenario Analysis
  analyzeWithdrawal: (applicantId: string, config: OptimizationConfig) =>
    request<{ scenario_result: AllocationResult; impact_report: ImpactReport }>('/api/scenarios/withdrawal', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ applicant_id: applicantId, config }),
    }),
  commitWithdrawal: (applicantId: string, scenarioResult: AllocationResult) =>
    request<{ success: boolean; message: string }>('/api/scenarios/withdrawal/commit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ applicant_id: applicantId, scenario_result: scenarioResult }),
    }),

  analyzeCapacity: (programId: string, newCapacity: number, config: OptimizationConfig) =>
    request<{ scenario_result: AllocationResult; impact_report: ImpactReport }>('/api/scenarios/capacity', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ program_id: programId, new_capacity: newCapacity, config }),
    }),
  commitCapacity: (programId: string, newCapacity: number, scenarioResult: AllocationResult) =>
    request<{ success: boolean; message: string }>('/api/scenarios/capacity/commit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ program_id: programId, new_capacity: newCapacity, scenario_result: scenarioResult }),
    }),

  analyzeAppeal: (applicantId: string, requestedProgramId: string, config: OptimizationConfig) =>
    request<{ scenario_result: AllocationResult; impact_report: ImpactReport }>('/api/scenarios/appeal', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ applicant_id: applicantId, requested_program_id: requestedProgramId, config }),
    }),
  grantAppeal: (scenarioResult: AllocationResult) =>
    request<{ success: boolean; message: string }>('/api/scenarios/appeal/grant', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scenario_result: scenarioResult }),
    }),

  // History & Audit
  getRuns: () => request<{ runs: RunSummary[] }>('/api/history/runs'),
  getRunDetail: (runId: string) => request<{ run: RunDetail }>(`/api/history/runs/${encodeURIComponent(runId)}`),
  restoreRun: (runId: string) =>
    request<{ success: boolean; active_baseline_run_id: string }>(`/api/baseline/set?run_id=${encodeURIComponent(runId)}`, {
      method: 'POST',
    }),
  getAuditTrail: () => request<{ audit_events: AuditEvent[] }>('/api/history/audit'),
};


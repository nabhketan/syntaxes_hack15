import React, { useState } from 'react';
import {
  Zap,
  CheckCircle2,
  XCircle,
  Save,
  Users,
  AlertCircle,
  Award,
  Layers,
  Clock,
} from 'lucide-react';
import {
  Applicant,
  Program,
  OptimizationConfig,
  AllocationResult,
} from '../types';
import { api } from '../api/client';

interface InitialAllocationTabProps {
  applicants: Applicant[];
  programs: Program[];
  config: OptimizationConfig;
  onBaselineUpdated: () => Promise<void>;
}

export const InitialAllocationTab: React.FC<InitialAllocationTabProps> = ({
  applicants,
  programs,
  config,
  onBaselineUpdated,
}) => {
  const [calcResult, setCalcResult] = useState<AllocationResult | null>(null);
  const [solving, setSolving] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [activeAllocTab, setActiveAllocTab] = useState<'assigned' | 'unassigned' | 'capacity'>('assigned');

  const handleSolve = async () => {
    setSolving(true);
    setMessage(null);
    try {
      const res = await api.solveAllocation(config, 'initial', 'Initial full allocation run');
      setCalcResult(res.result);
      if (res.result.validation_result && !res.result.validation_result.is_valid) {
        setMessage({
          type: 'error',
          text: `Independent validation detected ${res.result.validation_result.errors.length} violations.`,
        });
      }
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message });
    } finally {
      setSolving(false);
    }
  };

  const handleSaveBaseline = async () => {
    if (!calcResult) return;
    setSaving(true);
    try {
      const res = await api.saveBaseline(calcResult);
      setMessage({ type: 'success', text: `Allocation ${res.run_id} successfully saved as active baseline!` });
      await onBaselineUpdated();
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message });
    } finally {
      setSaving(false);
    }
  };

  const totalSeats = programs.reduce((acc, p) => acc + p.capacity, 0);
  const appMap = new Map(applicants.map((a) => [a.applicant_id, a]));
  const progMap = new Map(programs.map((p) => [p.program_id, p]));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Page Title */}
      <div className="page-header">
        <div>
          <h2 className="page-title">Initial Program Seat Allocation</h2>
          <p className="page-desc">
            Run the mathematical allocation optimizer on current applicants and programs. Every solution is audited by the{' '}
            <strong>independent validator</strong> before saving as the current baseline.
          </p>
        </div>
      </div>

      {/* Action Button */}
      <div>
        <button
          type="button"
          className="btn btn-primary"
          style={{ padding: '12px 24px', fontSize: '1rem', fontWeight: 600 }}
          onClick={handleSolve}
          disabled={solving}
        >
          {solving ? (
            <>
              <div className="spinner" />
              <span>Executing Google OR-Tools CP-SAT multi-stage optimization...</span>
            </>
          ) : (
            <>
              <Zap size={18} />
              <span>⚡ Compute Optimal Allocation</span>
            </>
          )}
        </button>
      </div>

      {message && (
        <div className={`alert alert-${message.type === 'success' ? 'success' : 'error'}`}>
          {message.type === 'success' ? <CheckCircle2 size={18} /> : <AlertCircle size={18} />}
          <span>{message.text}</span>
        </div>
      )}

      {/* Solver Outcome & Quality Metrics */}
      {calcResult && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          {/* Outcome Row */}
          <div className="card" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px' }}>
            <div>
              <div className="metric-label">Solver Outcome</div>
              <div style={{ marginTop: '8px' }}>
                <span
                  className={`badge-status badge-${
                    calcResult.solver_status === 'Optimal'
                      ? 'optimal'
                      : calcResult.solver_status === 'Infeasible'
                      ? 'infeasible'
                      : 'feasible'
                  }`}
                  style={{ fontSize: '0.9rem', padding: '6px 12px' }}
                >
                  {calcResult.solver_status}
                </span>
              </div>
              <div style={{ fontSize: '0.78rem', color: '#64748b', marginTop: '6px' }}>
                Wall-clock time: <strong>{calcResult.wall_time_seconds}s</strong>
              </div>
            </div>

            <div>
              <div className="metric-label">Independent Validation</div>
              <div style={{ marginTop: '8px' }}>
                {calcResult.validation_result?.is_valid ? (
                  <span className="badge-status badge-optimal" style={{ fontSize: '0.9rem', padding: '6px 12px' }}>
                    <CheckCircle2 size={16} /> PASS (Audited)
                  </span>
                ) : (
                  <span className="badge-status badge-infeasible" style={{ fontSize: '0.9rem', padding: '6px 12px' }}>
                    <XCircle size={16} /> FAILED
                  </span>
                )}
              </div>
              <div style={{ fontSize: '0.78rem', color: '#64748b', marginTop: '6px' }}>
                Audited by AllocationValidator
              </div>
            </div>

            <div>
              <div className="metric-label">Total Placements</div>
              <div className="metric-value">{calcResult.total_assigned}</div>
              <div style={{ fontSize: '0.78rem', color: '#2563eb', fontWeight: 600 }}>
                Score: {calcResult.preference_score.toLocaleString()} pts
              </div>
            </div>
          </div>

          {/* Validation Violations if any */}
          {calcResult.validation_result && calcResult.validation_result.errors.length > 0 && (
            <div className="alert alert-error">
              <AlertCircle size={20} />
              <div>
                <strong>Validation Violations Detected:</strong>
                <ul style={{ paddingLeft: '16px', marginTop: '6px' }}>
                  {calcResult.validation_result.errors.map((err, i) => (
                    <li key={i}>{err}</li>
                  ))}
                </ul>
              </div>
            </div>
          )}

          {/* Metrics Grid */}
          <div className="metrics-grid">
            <div className="metric-card">
              <div className="metric-label">Active Applicants</div>
              <div className="metric-value">{applicants.filter((a) => a.status === 'active').length}</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Unassigned Applicants</div>
              <div className="metric-value" style={{ color: '#dc2626' }}>
                {calcResult.unassigned_applicants.length}
              </div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Matched to 1st Choice</div>
              <div className="metric-value" style={{ color: '#059669' }}>
                {calcResult.rank_distribution[1] || 0}
              </div>
              <div className="metric-sub">
                {calcResult.total_assigned > 0
                  ? (((calcResult.rank_distribution[1] || 0) / calcResult.total_assigned) * 100).toFixed(1) + '%'
                  : '0%'}
              </div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Capacity Utilized</div>
              <div className="metric-value">
                {calcResult.total_assigned} / {totalSeats}
              </div>
              <div className="metric-sub">
                {totalSeats > 0 ? ((calcResult.total_assigned / totalSeats) * 100).toFixed(1) + '%' : '0%'}
              </div>
            </div>
          </div>

          {/* Save as Baseline Button */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <button
              type="button"
              className="btn btn-primary"
              onClick={handleSaveBaseline}
              disabled={saving || !calcResult.validation_result?.is_valid}
              style={{ padding: '10px 20px', fontWeight: 600 }}
            >
              <Save size={16} />
              <span>💾 Save as Current Baseline Allocation</span>
            </button>
            <span style={{ fontSize: '0.82rem', color: '#64748b' }}>
              Establishes this allocation as the foundation for ripple impact evaluations.
            </span>
          </div>

          {/* Detailed Tables */}
          <div className="card">
            <div className="subtabs">
              <button
                type="button"
                className={`subtab-btn ${activeAllocTab === 'assigned' ? 'active' : ''}`}
                onClick={() => setActiveAllocTab('assigned')}
              >
                📋 Assigned Applicants ({Object.keys(calcResult.assignments).length})
              </button>
              <button
                type="button"
                className={`subtab-btn ${activeAllocTab === 'unassigned' ? 'active' : ''}`}
                onClick={() => setActiveAllocTab('unassigned')}
              >
                ⚠️ Unassigned Applicants ({calcResult.unassigned_applicants.length})
              </button>
              <button
                type="button"
                className={`subtab-btn ${activeAllocTab === 'capacity' ? 'active' : ''}`}
                onClick={() => setActiveAllocTab('capacity')}
              >
                🏫 Capacity Utilization ({Object.keys(calcResult.capacity_utilization).length})
              </button>
            </div>

            {/* ASSIGNED APPLICANTS TABLE */}
            {activeAllocTab === 'assigned' && (
              <div className="table-container" style={{ maxHeight: '450px' }}>
                <table>
                  <thead>
                    <tr>
                      <th>Applicant ID</th>
                      <th>Name</th>
                      <th>Assigned Program</th>
                      <th>Program ID</th>
                      <th>Preference Rank</th>
                      <th>Score Points</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(calcResult.assignments).map(([appId, progId]) => {
                      const app = appMap.get(appId);
                      const prog = progMap.get(progId);
                      const rank = app ? app.preferences.indexOf(progId) + 1 : 0;
                      const pts = rank > 0 && rank <= config.points_per_rank.length ? config.points_per_rank[rank - 1] : 1;
                      return (
                        <tr key={appId}>
                          <td><span className="code-pill">{appId}</span></td>
                          <td style={{ fontWeight: 600 }}>{app?.name || appId}</td>
                          <td>{prog?.name || progId}</td>
                          <td><span className="code-pill">{progId}</span></td>
                          <td>
                            <span style={{ fontWeight: 600, color: rank === 1 ? '#15803d' : '#2563eb' }}>
                              Choice #{rank}
                            </span>
                          </td>
                          <td><strong>{pts}</strong> pts</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}

            {/* UNASSIGNED APPLICANTS TABLE */}
            {activeAllocTab === 'unassigned' && (
              <div className="table-container" style={{ maxHeight: '450px' }}>
                <table>
                  <thead>
                    <tr>
                      <th>Applicant ID</th>
                      <th>Name</th>
                      <th>Ranked Preferences</th>
                      <th>Eligibility</th>
                      <th>Explanation</th>
                    </tr>
                  </thead>
                  <tbody>
                    {calcResult.unassigned_applicants.map((appId) => {
                      const app = appMap.get(appId);
                      return (
                        <tr key={appId}>
                          <td><span className="code-pill">{appId}</span></td>
                          <td style={{ fontWeight: 600 }}>{app?.name || appId}</td>
                          <td>{app?.preferences.join(', ') || 'None'}</td>
                          <td>{app?.eligibility.join(', ') || 'ALL'}</td>
                          <td style={{ fontSize: '0.8rem', color: '#64748b' }}>
                            All requested programs filled by higher-priority candidates or ineligible.
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}

            {/* CAPACITY UTILIZATION TABLE */}
            {activeAllocTab === 'capacity' && (
              <div className="table-container" style={{ maxHeight: '450px' }}>
                <table>
                  <thead>
                    <tr>
                      <th>Program ID</th>
                      <th>Program Name</th>
                      <th>Capacity</th>
                      <th>Assigned</th>
                      <th>Remaining</th>
                      <th>Fill %</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(calcResult.capacity_utilization).map(([pid, pinfo]) => (
                      <tr key={pid}>
                        <td><span className="code-pill">{pid}</span></td>
                        <td style={{ fontWeight: 600 }}>{pinfo.name}</td>
                        <td>{pinfo.capacity}</td>
                        <td style={{ fontWeight: 600 }}>{pinfo.assigned}</td>
                        <td>{pinfo.remaining}</td>
                        <td>
                          <span style={{ fontWeight: 600, color: pinfo.fill_percentage >= 100 ? '#15803d' : '#2563eb' }}>
                            {pinfo.fill_percentage.toFixed(1)}%
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};


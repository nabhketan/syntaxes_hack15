import React, { useState } from 'react';
import {
  UserMinus,
  AlertTriangle,
  CheckCircle2,
  TrendingDown,
  Info,
  Check,
  Filter,
} from 'lucide-react';
import {
  Applicant,
  Program,
  OptimizationConfig,
  AllocationResult,
  ImpactReport,
} from '../types';
import { api } from '../api/client';

interface WithdrawalAnalysisTabProps {
  applicants: Applicant[];
  programs: Program[];
  baseline: AllocationResult | null;
  config: OptimizationConfig;
  onBaselineUpdated: () => Promise<void>;
}

export const WithdrawalAnalysisTab: React.FC<WithdrawalAnalysisTabProps> = ({
  applicants,
  programs,
  baseline,
  config,
  onBaselineUpdated,
}) => {
  const [selectedAppId, setSelectedAppId] = useState<string>('');
  const [scenarioResult, setScenarioResult] = useState<AllocationResult | null>(null);
  const [impactReport, setImpactReport] = useState<ImpactReport | null>(null);
  const [filterTraj, setFilterTraj] = useState<string>('All Affected');
  const [analyzing, setAnalyzing] = useState(false);
  const [committing, setCommitting] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  if (!baseline) {
    return (
      <div className="card" style={{ textAlign: 'center', padding: '48px 24px' }}>
        <AlertTriangle size={40} color="#f59e0b" style={{ margin: '0 auto 16px' }} />
        <h3 style={{ fontSize: '1.2rem', fontWeight: 700, color: '#0f172a' }}>No Baseline Allocation Available</h3>
        <p style={{ color: '#64748b', marginTop: '6px', maxWidth: '440px', margin: '6px auto 0' }}>
          Please go to the <strong>Initial Allocation</strong> tab and save an allocation as the current baseline first.
        </p>
      </div>
    );
  }

  // Filter assigned active applicants in baseline
  const assignedApplicants = applicants.filter(
    (a) => baseline.assignments[a.applicant_id] && a.status === 'active'
  );

  const activeSelectedId = selectedAppId || (assignedApplicants[0]?.applicant_id ?? '');

  const handleAnalyze = async () => {
    if (!activeSelectedId) return;
    setAnalyzing(true);
    setMessage(null);
    try {
      const res = await api.analyzeWithdrawal(activeSelectedId, config);
      setScenarioResult(res.scenario_result);
      setImpactReport(res.impact_report);
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message });
    } finally {
      setAnalyzing(false);
    }
  };

  const handleCommit = async () => {
    if (!activeSelectedId || !scenarioResult) return;
    setCommitting(true);
    try {
      const res = await api.commitWithdrawal(activeSelectedId, scenarioResult);
      setMessage({ type: 'success', text: res.message });
      setImpactReport(null);
      setScenarioResult(null);
      await onBaselineUpdated();
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message });
    } finally {
      setCommitting(false);
    }
  };

  // Filter trajectories
  const filteredChanges = impactReport?.changes.filter((c) => {
    if (filterTraj === 'All Affected') return c.change_type !== 'stayed';
    if (filterTraj === 'Promoted to Better Rank') return c.change_type === 'promoted';
    if (filterTraj === 'Newly Assigned') return c.change_type === 'newly_assigned';
    if (filterTraj === 'Stayed Unchanged') return c.change_type === 'stayed';
    return true; // 'All Applicants'
  }) ?? [];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Page Title */}
      <div className="page-header">
        <div>
          <h2 className="page-title">Applicant Withdrawal Impact Analysis</h2>
          <p className="page-desc">
            Analyze what happens when an applicant withdraws. The solver holds the prior allocation as the baseline, releases
            the withdrawn applicant's seat, and optimizes the remaining allocation while strictly{' '}
            <strong>minimizing unnecessary disruption</strong> to existing assignments.
          </p>
        </div>
      </div>

      {message && (
        <div className={`alert alert-${message.type === 'success' ? 'success' : 'error'}`}>
          {message.type === 'success' ? <CheckCircle2 size={18} /> : <AlertTriangle size={18} />}
          <span>{message.text}</span>
        </div>
      )}

      {/* Selector Card */}
      <div className="card">
        <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '20px', alignItems: 'flex-end' }}>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">Select Applicant to Withdraw</label>
            <select
              className="form-select"
              value={activeSelectedId}
              onChange={(e) => setSelectedAppId(e.target.value)}
            >
              {assignedApplicants.map((a) => (
                <option key={a.applicant_id} value={a.applicant_id}>
                  {a.applicant_id} - {a.name} (Currently in: {baseline.assignments[a.applicant_id]})
                </option>
              ))}
            </select>
          </div>

          <button
            type="button"
            className="btn btn-primary"
            onClick={handleAnalyze}
            disabled={analyzing || !activeSelectedId}
          >
            {analyzing ? (
              <>
                <div className="spinner" />
                <span>Recalculating ripple effects...</span>
              </>
            ) : (
              <>
                <UserMinus size={16} />
                <span>🔍 Analyze Withdrawal Ripple Effect</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Impact Report Results */}
      {impactReport && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          {/* Summary Metric Cards */}
          <div className="metrics-grid">
            <div className="metric-card">
              <div className="metric-label">Total Assigned</div>
              <div className="metric-value">{impactReport.total_assigned_after}</div>
              <div className={`metric-delta ${impactReport.net_assigned_change >= 0 ? 'positive' : 'negative'}`}>
                {impactReport.net_assigned_change >= 0 ? `+${impactReport.net_assigned_change}` : impactReport.net_assigned_change} vs baseline
              </div>
            </div>

            <div className="metric-card">
              <div className="metric-label">Preference Score</div>
              <div className="metric-value">{impactReport.pref_score_after.toLocaleString()}</div>
              <div className={`metric-delta ${impactReport.pref_score_change >= 0 ? 'positive' : 'negative'}`}>
                {impactReport.pref_score_change >= 0 ? `+${impactReport.pref_score_change}` : impactReport.pref_score_change} pts
              </div>
            </div>

            <div className="metric-card">
              <div className="metric-label">Reassignments</div>
              <div className="metric-value" style={{ color: '#2563eb' }}>{impactReport.reassignment_count}</div>
              <div className="metric-sub">Shifted to better programs</div>
            </div>

            <div className="metric-card">
              <div className="metric-label">Applicants Affected</div>
              <div className="metric-value" style={{ color: '#d97706' }}>{impactReport.affected_count}</div>
              <div className="metric-sub">Total trajectories changed</div>
            </div>
          </div>

          {/* Factual Solver Chain of Events */}
          <div className="card">
            <div className="card-title">
              <Info size={18} color="#2563eb" />
              <span>Factual Solver Chain of Events</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {impactReport.factual_explanations.map((exp, idx) => (
                <div key={idx} className="alert alert-info" style={{ padding: '10px 14px' }}>
                  <span>📌 {exp}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Trajectories Table */}
          <div className="card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div className="card-title" style={{ marginBottom: 0 }}>
                Applicant Assignment Trajectories
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Filter size={14} color="#64748b" />
                <select
                  className="form-select"
                  style={{ width: '220px' }}
                  value={filterTraj}
                  onChange={(e) => setFilterTraj(e.target.value)}
                >
                  <option value="All Affected">All Affected</option>
                  <option value="Promoted to Better Rank">Promoted to Better Rank</option>
                  <option value="Newly Assigned">Newly Assigned</option>
                  <option value="Stayed Unchanged">Stayed Unchanged</option>
                  <option value="All Applicants">All Applicants</option>
                </select>
              </div>
            </div>

            <div className="table-container" style={{ maxHeight: '450px' }}>
              <table>
                <thead>
                  <tr>
                    <th>Applicant ID</th>
                    <th>Name</th>
                    <th>Baseline Program</th>
                    <th>Baseline Rank</th>
                    <th>New Program</th>
                    <th>New Rank</th>
                    <th>Change Type</th>
                    <th>Explanation</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredChanges.map((c) => (
                    <tr key={c.applicant_id}>
                      <td><span className="code-pill">{c.applicant_id}</span></td>
                      <td style={{ fontWeight: 600 }}>{c.name}</td>
                      <td>{c.before_program_name || 'Unassigned'}</td>
                      <td>{c.before_rank ? `#${c.before_rank}` : '-'}</td>
                      <td><strong>{c.after_program_name || 'Unassigned'}</strong></td>
                      <td>{c.after_rank ? `#${c.after_rank}` : '-'}</td>
                      <td>
                        <span className={`badge-traj badge-${c.change_type}`}>
                          {c.change_type.replace('_', ' ')}
                        </span>
                      </td>
                      <td style={{ fontSize: '0.8rem', color: '#64748b', maxWidth: '300px' }}>{c.details}</td>
                    </tr>
                  ))}
                  {filteredChanges.length === 0 && (
                    <tr>
                      <td colSpan={8} style={{ textAlign: 'center', color: '#64748b', padding: '24px' }}>
                        No trajectories match the selected filter.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            {/* Commit Button */}
            <div style={{ marginTop: '20px', display: 'flex', alignItems: 'center', gap: '16px' }}>
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleCommit}
                disabled={committing}
              >
                <Check size={16} />
                <span>✅ Commit Withdrawal & Set as New Baseline</span>
              </button>
              <span style={{ fontSize: '0.8rem', color: '#64748b' }}>
                Permanently marks <strong>{activeSelectedId}</strong> as withdrawn and promotes cascading candidates into baseline.
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};


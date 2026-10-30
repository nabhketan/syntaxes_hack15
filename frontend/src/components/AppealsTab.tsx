import React, { useState } from 'react';
import {
  FileCheck2,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Zap,
  Info,
  Users,
} from 'lucide-react';
import {
  Applicant,
  Program,
  OptimizationConfig,
  AllocationResult,
  ImpactReport,
} from '../types';
import { api } from '../api/client';

interface AppealsTabProps {
  applicants: Applicant[];
  programs: Program[];
  baseline: AllocationResult | null;
  config: OptimizationConfig;
  onBaselineUpdated: () => Promise<void>;
}

export const AppealsTab: React.FC<AppealsTabProps> = ({
  applicants,
  programs,
  baseline,
  config,
  onBaselineUpdated,
}) => {
  const [selectedAppellant, setSelectedAppellant] = useState<string>('');
  const [selectedProgram, setSelectedProgram] = useState<string>(programs[0]?.program_id || '');
  const [scenarioResult, setScenarioResult] = useState<AllocationResult | null>(null);
  const [impactReport, setImpactReport] = useState<ImpactReport | null>(null);
  const [evaluating, setEvaluating] = useState(false);
  const [granting, setGranting] = useState(false);
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

  const activeApplicants = applicants.filter((a) => a.status === 'active');
  const activeAppellantId = selectedAppellant || (activeApplicants[0]?.applicant_id ?? '');

  const handleEvaluateAppeal = async () => {
    if (!activeAppellantId || !selectedProgram) return;
    setEvaluating(true);
    setMessage(null);
    try {
      const res = await api.analyzeAppeal(activeAppellantId, selectedProgram, config);
      setScenarioResult(res.scenario_result);
      setImpactReport(res.impact_report);
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message });
    } finally {
      setEvaluating(false);
    }
  };

  const handleGrantAppeal = async () => {
    if (!scenarioResult) return;
    setGranting(true);
    try {
      const res = await api.grantAppeal(scenarioResult);
      setMessage({ type: 'success', text: res.message });
      setImpactReport(null);
      setScenarioResult(null);
      await onBaselineUpdated();
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message });
    } finally {
      setGranting(false);
    }
  };

  const displacedChanges = impactReport?.changes.filter((c) => c.change_type !== 'stayed') ?? [];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Page Title */}
      <div className="page-header">
        <div>
          <h2 className="page-title">Counterfactual Appeal Analysis</h2>
          <p className="page-desc">
            Evaluate an applicant's appeal for a specific program placement. The optimizer enforces the requested placement as a
            scenario condition (if feasible) and audits the ripple effect on other applicants.{' '}
            <strong>The baseline allocation is never overwritten just by evaluating an appeal.</strong>
          </p>
        </div>
      </div>

      {message && (
        <div className={`alert alert-${message.type === 'success' ? 'success' : 'error'}`}>
          {message.type === 'success' ? <CheckCircle2 size={18} /> : <AlertTriangle size={18} />}
          <span>{message.text}</span>
        </div>
      )}

      {/* Selectors Card */}
      <div className="card">
        <div style={{ display: 'grid', gridTemplateColumns: '2fr 2fr 1fr', gap: '20px', alignItems: 'flex-end' }}>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">Appellant (Applicant)</label>
            <select
              className="form-select"
              value={activeAppellantId}
              onChange={(e) => setSelectedAppellant(e.target.value)}
            >
              {activeApplicants.map((a) => (
                <option key={a.applicant_id} value={a.applicant_id}>
                  {a.applicant_id} - {a.name} (Assigned: {baseline.assignments[a.applicant_id] || 'UNASSIGNED'})
                </option>
              ))}
            </select>
          </div>

          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">Requested Program</label>
            <select
              className="form-select"
              value={selectedProgram}
              onChange={(e) => setSelectedProgram(e.target.value)}
            >
              {programs.map((p) => (
                <option key={p.program_id} value={p.program_id}>
                  {p.program_id} - {p.name} (Cap: {p.capacity})
                </option>
              ))}
            </select>
          </div>

          <button
            type="button"
            className="btn btn-primary"
            onClick={handleEvaluateAppeal}
            disabled={evaluating || !activeAppellantId || !selectedProgram}
          >
            {evaluating ? (
              <>
                <div className="spinner" />
                <span>Evaluating appeal...</span>
              </>
            ) : (
              <>
                <FileCheck2 size={16} />
                <span>⚖️ Evaluate Appeal</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Appeal Evaluation Report */}
      {impactReport && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          {/* Feasibility Alert */}
          {impactReport.is_feasible ? (
            <div className="alert alert-success" style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <CheckCircle2 size={24} color="#15803d" />
              <div>
                <strong style={{ fontSize: '1rem' }}>Appeal Placement is Mathematically Feasible!</strong>
                <div style={{ fontSize: '0.8rem', color: '#166534', marginTop: '2px' }}>
                  Solver Status: <strong>{impactReport.solver_status}</strong>. All constraints and eligibility criteria can be
                  satisfied.
                </div>
              </div>
            </div>
          ) : (
            <div className="alert alert-error" style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <XCircle size={24} color="#b91c1c" />
              <div>
                <strong style={{ fontSize: '1rem' }}>Appeal Placement is INFEASIBLE.</strong>
                <div style={{ fontSize: '0.8rem', color: '#991b1b', marginTop: '2px' }}>
                  Solver Status: <strong>{impactReport.solver_status}</strong>. Cannot satisfy mandatory eligibility, capacity, or assignment rules.
                </div>
              </div>
            </div>
          )}

          {/* Factual Explanations */}
          <div className="card">
            <div className="card-title">
              <Info size={18} color="#2563eb" />
              <span>Factual Explanation of Appeal Outcome</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {impactReport.factual_explanations.map((exp, idx) => (
                <div
                  key={idx}
                  className={`alert alert-${impactReport.is_feasible ? 'info' : 'warning'}`}
                  style={{ padding: '10px 14px' }}
                >
                  <span>📌 {exp}</span>
                </div>
              ))}
            </div>
          </div>

          {/* If Feasible: Comparison Cards & Displaced Table */}
          {impactReport.is_feasible && (
            <>
              <div className="metrics-grid">
                <div className="metric-card">
                  <div className="metric-label">Total Placements</div>
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
                  <div className="metric-label">Reassignments Required</div>
                  <div className="metric-value" style={{ color: '#2563eb' }}>{impactReport.reassignment_count}</div>
                  <div className="metric-sub">Cascaded adjustments</div>
                </div>

                <div className="metric-card">
                  <div className="metric-label">Other Applicants Affected</div>
                  <div className="metric-value" style={{ color: '#d97706' }}>{impactReport.affected_count}</div>
                  <div className="metric-sub">Net impacted applicants</div>
                </div>
              </div>

              {/* Displaced Table */}
              <div className="card">
                <div className="card-title">
                  <Users size={18} color="#2563eb" />
                  <span>Applicants Displaced or Reassigned by Appeal ({displacedChanges.length})</span>
                </div>

                {displacedChanges.length > 0 ? (
                  <div className="table-container" style={{ maxHeight: '350px' }}>
                    <table>
                      <thead>
                        <tr>
                          <th>Applicant ID</th>
                          <th>Name</th>
                          <th>Before Program</th>
                          <th>After Program</th>
                          <th>Rank Delta</th>
                          <th>Action</th>
                          <th>Details</th>
                        </tr>
                      </thead>
                      <tbody>
                        {displacedChanges.map((c) => (
                          <tr key={c.applicant_id}>
                            <td><span className="code-pill">{c.applicant_id}</span></td>
                            <td style={{ fontWeight: 600 }}>{c.name}</td>
                            <td>{c.before_program_name || 'Unassigned'}</td>
                            <td><strong>{c.after_program_name || 'Unassigned'}</strong></td>
                            <td>
                              <span style={{ fontSize: '0.8rem', color: '#475569' }}>
                                #{c.before_rank || '-'} ➔ #{c.after_rank || '-'}
                              </span>
                            </td>
                            <td>
                              <span className={`badge-traj badge-${c.change_type}`}>
                                {c.change_type.replace('_', ' ')}
                              </span>
                            </td>
                            <td style={{ fontSize: '0.8rem', color: '#64748b' }}>{c.details}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p style={{ color: '#64748b', fontSize: '0.85rem' }}>No other applicants were affected by this placement.</p>
                )}

                {/* Grant Button */}
                <div style={{ marginTop: '20px', display: 'flex', alignItems: 'center', gap: '16px' }}>
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={handleGrantAppeal}
                    disabled={granting}
                  >
                    <Zap size={16} />
                    <span>⚡ Apply & Grant Appeal as New Baseline Allocation</span>
                  </button>
                  <span style={{ fontSize: '0.8rem', color: '#64748b' }}>
                    Permanently updates the baseline allocation to reflect this granted appeal.
                  </span>
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
};


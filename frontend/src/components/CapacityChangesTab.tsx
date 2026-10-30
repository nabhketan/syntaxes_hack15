import React, { useState } from 'react';
import {
  Sliders,
  AlertTriangle,
  CheckCircle2,
  Check,
  Info,
  Layers,
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

interface CapacityChangesTabProps {
  applicants: Applicant[];
  programs: Program[];
  baseline: AllocationResult | null;
  config: OptimizationConfig;
  onBaselineUpdated: () => Promise<void>;
}

export const CapacityChangesTab: React.FC<CapacityChangesTabProps> = ({
  applicants,
  programs,
  baseline,
  config,
  onBaselineUpdated,
}) => {
  const [selectedProgId, setSelectedProgId] = useState<string>(programs[0]?.program_id || '');
  const [newCapacity, setNewCapacity] = useState<number>(programs[0]?.capacity || 20);
  const [scenarioResult, setScenarioResult] = useState<AllocationResult | null>(null);
  const [impactReport, setImpactReport] = useState<ImpactReport | null>(null);
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

  const handleSelectProgram = (pid: string) => {
    setSelectedProgId(pid);
    const p = programs.find((x) => x.program_id === pid);
    if (p) setNewCapacity(p.capacity);
  };

  const handleAnalyze = async () => {
    if (!selectedProgId) return;
    setAnalyzing(true);
    setMessage(null);
    try {
      const res = await api.analyzeCapacity(selectedProgId, newCapacity, config);
      setScenarioResult(res.scenario_result);
      setImpactReport(res.impact_report);
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message });
    } finally {
      setAnalyzing(false);
    }
  };

  const handleCommit = async () => {
    if (!selectedProgId || !scenarioResult) return;
    setCommitting(true);
    try {
      const res = await api.commitCapacity(selectedProgId, newCapacity, scenarioResult);
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

  const affectedChanges = impactReport?.changes.filter((c) => c.change_type !== 'stayed') ?? [];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Page Title */}
      <div className="page-header">
        <div>
          <h2 className="page-title">Program Capacity Change Analysis</h2>
          <p className="page-desc">
            Simulate adding or removing seats from any training program. The model recalculates assignments while preserving
            existing assignments wherever possible and details the ripple effect on waitlisted or displaced applicants.
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
        <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr', gap: '20px', alignItems: 'flex-end' }}>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">Select Program to Adjust</label>
            <select
              className="form-select"
              value={selectedProgId}
              onChange={(e) => handleSelectProgram(e.target.value)}
            >
              {programs.map((p) => (
                <option key={p.program_id} value={p.program_id}>
                  {p.program_id} - {p.name} (Current Cap: {p.capacity})
                </option>
              ))}
            </select>
          </div>

          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">New Capacity</label>
            <input
              type="number"
              min="0"
              max="500"
              value={newCapacity}
              onChange={(e) => setNewCapacity(Math.max(0, parseInt(e.target.value) || 0))}
              className="form-input"
            />
          </div>

          <button
            type="button"
            className="btn btn-primary"
            onClick={handleAnalyze}
            disabled={analyzing || !selectedProgId}
          >
            {analyzing ? (
              <>
                <div className="spinner" />
                <span>Simulating capacity impact...</span>
              </>
            ) : (
              <>
                <Sliders size={16} />
                <span>⚖️ Analyze Capacity Change</span>
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
              <div className="metric-sub">Applicants shifted</div>
            </div>

            <div className="metric-card">
              <div className="metric-label">Applicants Affected</div>
              <div className="metric-value" style={{ color: '#d97706' }}>{impactReport.affected_count}</div>
              <div className="metric-sub">Total trajectories altered</div>
            </div>
          </div>

          {/* Factual Explanations */}
          <div className="card">
            <div className="card-title">
              <Info size={18} color="#2563eb" />
              <span>Factual Solver Impact Analysis</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {impactReport.factual_explanations.map((exp, idx) => (
                <div key={idx} className="alert alert-info" style={{ padding: '10px 14px' }}>
                  <span>📌 {exp}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Program Capacity Breakdown */}
          <div className="card">
            <div className="card-title">
              <Layers size={18} color="#059669" />
              <span>Program Capacity Breakdown</span>
            </div>
            <div className="table-container" style={{ maxHeight: '350px' }}>
              <table>
                <thead>
                  <tr>
                    <th>Program</th>
                    <th>Capacity (Before)</th>
                    <th>Capacity (After)</th>
                    <th>Assigned (Before)</th>
                    <th>Assigned (After)</th>
                    <th>Net Assigned Change</th>
                    <th>Remaining Seats</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(impactReport.capacity_diffs).map(([pid, d]) => (
                    <tr key={pid}>
                      <td style={{ fontWeight: 600 }}>{d.name}</td>
                      <td>{d.capacity_before}</td>
                      <td><strong>{d.capacity_after}</strong></td>
                      <td>{d.assigned_before}</td>
                      <td><strong>{d.assigned_after}</strong></td>
                      <td style={{ fontWeight: 600, color: d.net_assigned_change > 0 ? '#15803d' : d.net_assigned_change < 0 ? '#b91c1c' : '#475569' }}>
                        {d.net_assigned_change > 0 ? `+${d.net_assigned_change}` : d.net_assigned_change}
                      </td>
                      <td>{d.remaining_after}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Affected Applicants Table */}
          <div className="card">
            <div className="card-title">
              <Users size={18} color="#2563eb" />
              <span>Affected Applicants ({affectedChanges.length})</span>
            </div>
            {affectedChanges.length > 0 ? (
              <div className="table-container" style={{ maxHeight: '350px' }}>
                <table>
                  <thead>
                    <tr>
                      <th>Applicant ID</th>
                      <th>Name</th>
                      <th>Before</th>
                      <th>After</th>
                      <th>Change</th>
                      <th>Details</th>
                    </tr>
                  </thead>
                  <tbody>
                    {affectedChanges.map((c) => (
                      <tr key={c.applicant_id}>
                        <td><span className="code-pill">{c.applicant_id}</span></td>
                        <td style={{ fontWeight: 600 }}>{c.name}</td>
                        <td>{c.before_program_name || 'Unassigned'}</td>
                        <td><strong>{c.after_program_name || 'Unassigned'}</strong></td>
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
              <p style={{ color: '#64748b', fontSize: '0.85rem' }}>No applicants were displaced or reassigned.</p>
            )}

            {/* Commit Button */}
            <div style={{ marginTop: '20px', display: 'flex', alignItems: 'center', gap: '16px' }}>
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleCommit}
                disabled={committing}
              >
                <Check size={16} />
                <span>✅ Commit Capacity Change as Baseline</span>
              </button>
              <span style={{ fontSize: '0.8rem', color: '#64748b' }}>
                Permanently updates <strong>{selectedProgId}</strong> capacity to {newCapacity} and saves new baseline.
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};


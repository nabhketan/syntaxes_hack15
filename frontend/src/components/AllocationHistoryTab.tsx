import React, { useState, useEffect } from 'react';
import {
  History,
  RotateCcw,
  CheckCircle2,
  FileText,
  Clock,
  Layers,
  Award,
} from 'lucide-react';
import { RunSummary, RunDetail, AuditEvent } from '../types';
import { api } from '../api/client';

interface AllocationHistoryTabProps {
  onBaselineRestored: () => Promise<void>;
}

export const AllocationHistoryTab: React.FC<AllocationHistoryTabProps> = ({ onBaselineRestored }) => {
  const [activeSubTab, setActiveSubTab] = useState<'runs' | 'audit'>('runs');
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string>('');
  const [runDetail, setRunDetail] = useState<RunDetail | null>(null);
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [restoring, setRestoring] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const fetchHistory = async () => {
    setLoading(true);
    try {
      const [runsRes, auditRes] = await Promise.all([api.getRuns(), api.getAuditTrail()]);
      setRuns(runsRes.runs);
      setAuditEvents(auditRes.audit_events);
      if (runsRes.runs.length > 0 && !selectedRunId) {
        setSelectedRunId(runsRes.runs[0].run_id);
      }
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, []);

  useEffect(() => {
    if (selectedRunId) {
      api
        .getRunDetail(selectedRunId)
        .then((res) => setRunDetail(res.run))
        .catch((err) => setMessage({ type: 'error', text: err.message }));
    }
  }, [selectedRunId]);

  const handleRestore = async () => {
    if (!selectedRunId) return;
    setRestoring(true);
    try {
      await api.restoreRun(selectedRunId);
      setMessage({ type: 'success', text: `Run ${selectedRunId} successfully restored as active baseline!` });
      await fetchHistory();
      await onBaselineRestored();
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message });
    } finally {
      setRestoring(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Page Title */}
      <div className="page-header">
        <div>
          <h2 className="page-title">Audit History & Run Log</h2>
          <p className="page-desc">
            Complete historical record of allocation runs, solver outcomes, wall-clock times, independent validation results,
            and system audit events persisted in SQLite.
          </p>
        </div>
      </div>

      {message && (
        <div className={`alert alert-${message.type === 'success' ? 'success' : 'error'}`}>
          {message.type === 'success' ? <CheckCircle2 size={18} /> : <History size={18} />}
          <span>{message.text}</span>
        </div>
      )}

      {/* Subtabs */}
      <div className="subtabs">
        <button
          type="button"
          className={`subtab-btn ${activeSubTab === 'runs' ? 'active' : ''}`}
          onClick={() => setActiveSubTab('runs')}
        >
          📊 Saved Allocation Runs ({runs.length})
        </button>
        <button
          type="button"
          className={`subtab-btn ${activeSubTab === 'audit' ? 'active' : ''}`}
          onClick={() => setActiveSubTab('audit')}
        >
          📝 System Audit Trail ({auditEvents.length})
        </button>
      </div>

      {/* ========================================================= */}
      {/* RUNS SUBTAB */}
      {/* ========================================================= */}
      {activeSubTab === 'runs' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          {/* Runs Table */}
          <div className="card">
            <div className="card-title">Allocation Runs History</div>
            {runs.length > 0 ? (
              <div className="table-container" style={{ maxHeight: '350px' }}>
                <table>
                  <thead>
                    <tr>
                      <th>Run ID</th>
                      <th>Timestamp</th>
                      <th>Scenario</th>
                      <th>Status</th>
                      <th>Assigned</th>
                      <th>Score</th>
                      <th>Reassignments</th>
                      <th>Valid</th>
                      <th>Baseline</th>
                      <th>Wall Time</th>
                    </tr>
                  </thead>
                  <tbody>
                    {runs.map((r) => (
                      <tr
                        key={r.run_id}
                        onClick={() => setSelectedRunId(r.run_id)}
                        style={{
                          cursor: 'pointer',
                          background: selectedRunId === r.run_id ? '#eff6ff' : 'transparent',
                        }}
                      >
                        <td><span className="code-pill">{r.run_id}</span></td>
                        <td style={{ fontSize: '0.75rem', fontFamily: 'var(--font-mono)' }}>
                          {r.timestamp?.slice(0, 19).replace('T', ' ')}
                        </td>
                        <td style={{ fontSize: '0.8rem', fontWeight: 500 }}>{r.scenario_description}</td>
                        <td>
                          <span
                            className={`badge-status badge-${
                              r.solver_status.toLowerCase().includes('optimal')
                                ? 'optimal'
                                : r.solver_status.toLowerCase().includes('infeasible')
                                ? 'infeasible'
                                : 'feasible'
                            }`}
                          >
                            {r.solver_status}
                          </span>
                        </td>
                        <td><strong>{r.total_assigned}</strong></td>
                        <td>{r.preference_score.toLocaleString()}</td>
                        <td>{r.reassignment_count}</td>
                        <td>
                          {r.is_valid ? (
                            <span style={{ color: '#15803d', fontWeight: 600 }}>PASS</span>
                          ) : (
                            <span style={{ color: '#b91c1c', fontWeight: 600 }}>FAIL</span>
                          )}
                        </td>
                        <td>
                          {r.is_active_baseline ? (
                            <span className="badge-status badge-optimal" style={{ fontSize: '0.72rem' }}>
                              ACTIVE
                            </span>
                          ) : (
                            <span style={{ color: '#94a3b8' }}>-</span>
                          )}
                        </td>
                        <td>{r.wall_time_seconds}s</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p style={{ color: '#64748b', fontSize: '0.85rem' }}>No allocation runs recorded yet.</p>
            )}
          </div>

          {/* Inspect Details */}
          {runDetail && (
            <div className="card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                <div className="card-title" style={{ marginBottom: 0 }}>
                  Inspect Past Run: <span className="code-pill">{runDetail.run_id}</span>
                </div>

                {!runDetail.is_active_baseline && (
                  <button
                    type="button"
                    className="btn btn-primary btn-sm"
                    onClick={handleRestore}
                    disabled={restoring}
                  >
                    <RotateCcw size={14} />
                    <span>↺ Restore this Run as Active Baseline</span>
                  </button>
                )}
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px', marginBottom: '20px', fontSize: '0.85rem' }}>
                <div>
                  <span style={{ color: '#64748b' }}>Scenario: </span>
                  <strong>{runDetail.scenario_description}</strong>
                </div>
                <div>
                  <span style={{ color: '#64748b' }}>Timestamp: </span>
                  <span>{runDetail.timestamp}</span>
                </div>
                <div>
                  <span style={{ color: '#64748b' }}>Solver Status: </span>
                  <span className="badge-status badge-optimal">{runDetail.solver_status}</span>
                </div>
                <div>
                  <span style={{ color: '#64748b' }}>Wall-Clock Time: </span>
                  <strong>{runDetail.wall_time_seconds}s</strong>
                </div>
                <div>
                  <span style={{ color: '#64748b' }}>Total Assigned: </span>
                  <strong>{runDetail.total_assigned}</strong>
                </div>
                <div>
                  <span style={{ color: '#64748b' }}>Preference Score: </span>
                  <strong>{runDetail.preference_score.toLocaleString()} pts</strong>
                </div>
              </div>

              {/* Assignment Sample Table */}
              <div style={{ fontSize: '0.85rem', fontWeight: 600, marginBottom: '8px' }}>
                Assignments Sample ({runDetail.assignments_list.length} applicants assigned):
              </div>
              <div className="table-container" style={{ maxHeight: '350px' }}>
                <table>
                  <thead>
                    <tr>
                      <th>Applicant ID</th>
                      <th>Name</th>
                      <th>Assigned Program</th>
                      <th>Program ID</th>
                      <th>Rank</th>
                      <th>Score Points</th>
                    </tr>
                  </thead>
                  <tbody>
                    {runDetail.assignments_list.map((item) => (
                      <tr key={item.applicant_id}>
                        <td><span className="code-pill">{item.applicant_id}</span></td>
                        <td style={{ fontWeight: 600 }}>{item.name}</td>
                        <td>{item.assigned_program}</td>
                        <td><span className="code-pill">{item.program_id}</span></td>
                        <td><span style={{ fontWeight: 600, color: '#2563eb' }}>{item.preference_rank}</span></td>
                        <td><strong>{item.score_points}</strong> pts</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ========================================================= */}
      {/* AUDIT TRAIL SUBTAB */}
      {/* ========================================================= */}
      {activeSubTab === 'audit' && (
        <div className="card">
          <div className="card-title">System Audit Trail</div>
          {auditEvents.length > 0 ? (
            <div className="table-container" style={{ maxHeight: '520px' }}>
              <table>
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Timestamp</th>
                    <th>Event Type</th>
                    <th>Run ID</th>
                    <th>Description</th>
                  </tr>
                </thead>
                <tbody>
                  {auditEvents.map((evt) => (
                    <tr key={evt.id}>
                      <td>#{evt.id}</td>
                      <td style={{ fontSize: '0.75rem', fontFamily: 'var(--font-mono)' }}>
                        {evt.timestamp?.slice(0, 19).replace('T', ' ')}
                      </td>
                      <td>
                        <span className="code-pill">{evt.event_type}</span>
                      </td>
                      <td>
                        {evt.run_id ? <span className="code-pill">{evt.run_id}</span> : <span style={{ color: '#94a3b8' }}>-</span>}
                      </td>
                      <td style={{ fontSize: '0.82rem' }}>{evt.description}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p style={{ color: '#64748b', fontSize: '0.85rem' }}>No audit events recorded yet.</p>
          )}
        </div>
      )}
    </div>
  );
};


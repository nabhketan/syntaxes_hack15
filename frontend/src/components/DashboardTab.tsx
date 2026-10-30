import React from 'react';
import {
  TrendingUp,
  Award,
  Users,
  CheckCircle,
  Percent,
  Layers,
  ShieldCheck,
  Zap,
} from 'lucide-react';
import { AllocationResult, SystemStatus, Program } from '../types';

interface DashboardTabProps {
  status: SystemStatus | null;
  baseline: AllocationResult | null;
  programs: Program[];
  onNavigateToTab: (tab: string) => void;
}

export const DashboardTab: React.FC<DashboardTabProps> = ({
  status,
  baseline,
  programs,
  onNavigateToTab,
}) => {
  const totalApps = status?.total_applicants ?? 0;
  const activeApps = status?.active_applicants ?? 0;
  const totalSeats = status?.total_capacity ?? 0;
  const baselineAssigned = baseline?.total_assigned ?? 0;
  const matchRate = activeApps > 0 && baselineAssigned > 0
    ? ((baselineAssigned / activeApps) * 100).toFixed(1) + '%'
    : '0%';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Page Title */}
      <div className="page-header">
        <div>
          <h2 className="page-title">FAIRSHIFT Allocation Dashboard</h2>
          <p className="page-desc">
            FAIRSHIFT uses <strong>Google OR-Tools CP-SAT</strong> mathematical constraint programming to allocate limited
            program seats transparently, uphold strict eligibility and capacity rules, and simulate ripple effects from applicant
            withdrawals, capacity changes, and appeals.
          </p>
        </div>
      </div>

      {/* Key Metrics Row */}
      <div className="metrics-grid">
        <div className="metric-card">
          <div className="metric-label">Total Applicants</div>
          <div className="metric-value">{totalApps}</div>
          <div className="metric-sub">In database</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Active Applicants</div>
          <div className="metric-value">{activeApps}</div>
          <div className="metric-sub">Eligible for allocation</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Total Program Seats</div>
          <div className="metric-value">{totalSeats}</div>
          <div className="metric-sub">Across {programs.length} programs</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Baseline Assigned</div>
          <div className="metric-value" style={{ color: '#2563eb' }}>{baselineAssigned}</div>
          <div className="metric-sub">{baseline ? 'Active baseline' : 'No baseline computed'}</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Placement Rate</div>
          <div className="metric-value" style={{ color: '#059669' }}>{matchRate}</div>
          <div className="metric-sub">Of active applicants</div>
        </div>
      </div>

      {/* Middle Row: Baseline Quality & Program Capacity */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: '24px' }}>
        {/* Left: Quality Measures */}
        <div className="card">
          <div className="card-title">
            <Award size={18} color="#2563eb" />
            <span>Current Baseline Quality Measures</span>
          </div>

          {baseline ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px', fontSize: '0.85rem' }}>
                <div>
                  <span style={{ color: '#64748b' }}>Run ID: </span>
                  <span className="code-pill">{baseline.run_id}</span>
                </div>
                <div>
                  <span style={{ color: '#64748b' }}>Status: </span>
                  <span className={`badge-status badge-${baseline.solver_status.toLowerCase().includes('optimal') ? 'optimal' : 'feasible'}`}>
                    {baseline.solver_status}
                  </span>
                </div>
                <div>
                  <span style={{ color: '#64748b' }}>Solve Time: </span>
                  <strong>{baseline.wall_time_seconds}s</strong>
                </div>
                <div>
                  <span style={{ color: '#64748b' }}>Preference Score: </span>
                  <strong style={{ color: '#2563eb' }}>{baseline.preference_score.toLocaleString()} pts</strong>
                </div>
              </div>

              {/* Rank distribution table */}
              <div className="table-container">
                <table>
                  <thead>
                    <tr>
                      <th>Choice Rank</th>
                      <th>Matched Applicants</th>
                      <th>Share of Assigned</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[1, 2, 3, 4, 5].map((r) => {
                      const count = baseline.rank_distribution[r] || 0;
                      const pct = baseline.total_assigned > 0
                        ? ((count / baseline.total_assigned) * 100).toFixed(1) + '%'
                        : '0%';
                      return (
                        <tr key={r}>
                          <td style={{ fontWeight: 600 }}>Choice #{r}</td>
                          <td>{count}</td>
                          <td>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                              <span>{pct}</span>
                              <div style={{ flex: 1, maxWidth: '100px', height: '6px', background: '#f1f5f9', borderRadius: '3px', overflow: 'hidden' }}>
                                <div style={{ width: pct, height: '100%', background: '#2563eb' }} />
                              </div>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '32px 16px', textAlign: 'center', color: '#64748b' }}>
              <Award size={36} color="#cbd5e1" style={{ marginBottom: '12px' }} />
              <p style={{ fontWeight: 600, color: '#334155' }}>No Baseline Allocation Set</p>
              <p style={{ fontSize: '0.82rem', marginTop: '4px', maxWidth: '320px' }}>
                Run the mathematical optimizer to establish the current baseline allocation.
              </p>
              <button
                type="button"
                className="btn btn-primary btn-sm"
                style={{ marginTop: '16px' }}
                onClick={() => onNavigateToTab('initial-allocation')}
              >
                Go to Initial Allocation ➔
              </button>
            </div>
          )}
        </div>

        {/* Right: Program Capacity Utilization */}
        <div className="card">
          <div className="card-title">
            <Layers size={18} color="#059669" />
            <span>Program Capacity Utilization (Baseline)</span>
          </div>

          <div className="table-container" style={{ maxHeight: '340px' }}>
            <table>
              <thead>
                <tr>
                  <th>Program</th>
                  <th>Capacity</th>
                  <th>Assigned</th>
                  <th>Remaining</th>
                  <th>Fill %</th>
                </tr>
              </thead>
              <tbody>
                {baseline && baseline.capacity_utilization ? (
                  Object.entries(baseline.capacity_utilization).map(([pid, pinfo]) => (
                    <tr key={pid}>
                      <td style={{ fontWeight: 500 }}>{pinfo.name}</td>
                      <td>{pinfo.capacity}</td>
                      <td style={{ fontWeight: 600 }}>{pinfo.assigned}</td>
                      <td>{pinfo.remaining}</td>
                      <td>
                        <span style={{ fontWeight: 600, color: pinfo.fill_percentage >= 100 ? '#15803d' : '#2563eb' }}>
                          {pinfo.fill_percentage.toFixed(1)}%
                        </span>
                      </td>
                    </tr>
                  ))
                ) : (
                  programs.map((p) => (
                    <tr key={p.program_id}>
                      <td style={{ fontWeight: 500 }}>{p.name}</td>
                      <td>{p.capacity}</td>
                      <td style={{ color: '#94a3b8' }}>-</td>
                      <td>{p.capacity}</td>
                      <td style={{ color: '#94a3b8' }}>0.0%</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Rules & Priority Hierarchy */}
      <div className="card" style={{ background: '#f8fafc' }}>
        <div className="card-title">
          <ShieldCheck size={18} color="#475569" />
          <span>Core Mathematical Rules & Priority Hierarchy</span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '24px', fontSize: '0.85rem' }}>
          <div style={{ background: '#ffffff', padding: '16px', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
            <h4 style={{ fontWeight: 700, color: '#0f172a', marginBottom: '8px' }}>Mandatory Hard Constraints:</h4>
            <ol style={{ paddingLeft: '20px', display: 'flex', flexDirection: 'column', gap: '6px', color: '#475569' }}>
              <li><strong>At-Most-One Assignment:</strong> Every applicant receives at most one seat.</li>
              <li><strong>Capacity Limits:</strong> Seats assigned never exceed program capacity.</li>
              <li><strong>Strict Eligibility:</strong> Candidates only match programs they are eligible for.</li>
              <li><strong>Zero Withdrawn Placements:</strong> Withdrawn applicants receive zero seats.</li>
              <li><strong>Appeal Conditions:</strong> Enforces appeal requirement if mathematically feasible.</li>
            </ol>
          </div>

          <div style={{ background: '#ffffff', padding: '16px', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
            <h4 style={{ fontWeight: 700, color: '#0f172a', marginBottom: '8px' }}>Lexicographic Hierarchy:</h4>
            <ol style={{ paddingLeft: '20px', display: 'flex', flexDirection: 'column', gap: '6px', color: '#475569' }}>
              <li><strong>Stage 1 (Max Placements):</strong> Maximize total eligible active applicants assigned.</li>
              <li><strong>Stage 2 (Max Satisfaction):</strong> Maximize preference points subject to Stage 1.</li>
              <li><strong>Stage 3 (Stability):</strong> Retain baseline assignments and minimize reassignments subject to Stages 1 & 2.</li>
            </ol>
          </div>
        </div>
      </div>
    </div>
  );
};


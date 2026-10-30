import React, { useState } from 'react';
import {
  Scale,
  Settings,
  Database,
  ChevronDown,
  ChevronRight,
  RotateCcw,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Check,
} from 'lucide-react';
import { OptimizationConfig, SystemStatus } from '../types';

interface SidebarProps {
  config: OptimizationConfig;
  onConfigChange: (newConfig: OptimizationConfig) => void;
  status: SystemStatus | null;
  onResetData: () => Promise<void>;
  loading: boolean;
}

export const Sidebar: React.FC<SidebarProps> = ({
  config,
  onConfigChange,
  status,
  onResetData,
  loading,
}) => {
  const [showScoreScheme, setShowScoreScheme] = useState(false);
  const [showWeights, setShowWeights] = useState(false);
  const [confirmReset, setConfirmReset] = useState(false);

  const handlePointChange = (index: number, val: number) => {
    const updated = [...config.points_per_rank];
    updated[index] = Math.max(1, val);
    onConfigChange({ ...config, points_per_rank: updated });
  };

  return (
    <aside className="sidebar">
      {/* Brand */}
      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{ background: '#2563eb', color: '#fff', borderRadius: '8px', padding: '6px 8px', display: 'flex' }}>
            <Scale size={22} />
          </div>
          <div>
            <h1 style={{ fontSize: '1.25rem', fontWeight: 800, color: '#0f172a', letterSpacing: '-0.02em' }}>FAIRSHIFT</h1>
            <p style={{ fontSize: '0.75rem', color: '#64748b', fontWeight: 500 }}>Training Seat Allocation Engine</p>
          </div>
        </div>
      </div>

      <hr style={{ border: 'none', borderTop: '1px solid #e2e8f0' }} />

      {/* Solver Configuration */}
      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '14px' }}>
          <Settings size={16} color="#2563eb" />
          <h2 style={{ fontSize: '0.9rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em', color: '#475569' }}>
            Solver Configuration
          </h2>
        </div>

        <div className="form-group">
          <label className="form-label">Optimization Mode</label>
          <select
            className="form-select"
            value={config.priority_mode}
            onChange={(e) => onConfigChange({ ...config, priority_mode: e.target.value as any })}
          >
            <option value="lexicographic">Lexicographic Multi-Stage (Default)</option>
            <option value="weighted">Weighted Single-Stage</option>
          </select>
          <span style={{ fontSize: '0.72rem', color: '#64748b', marginTop: '2px' }}>
            {config.priority_mode === 'lexicographic'
              ? 'Stage 1: Max Placements ➔ Stage 2: Max Preference Score ➔ Stage 3: Minimal Disruption'
              : 'Single objective scalarization using customizable priority weights.'}
          </span>
        </div>

        <div className="form-group" style={{ marginTop: '8px' }}>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={config.only_assign_preferred}
              onChange={(e) => onConfigChange({ ...config, only_assign_preferred: e.target.checked })}
            />
            <span>Only assign preferred programs</span>
          </label>
          <span style={{ fontSize: '0.72rem', color: '#64748b', marginLeft: '24px' }}>
            Strictly restricts assignments to programs in applicant's ranked choices.
          </span>
        </div>

        <div className="form-group" style={{ marginTop: '10px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <label className="form-label">Solver Time Limit</label>
            <span style={{ fontSize: '0.8rem', fontWeight: 600, color: '#2563eb' }}>{config.time_limit_seconds}s</span>
          </div>
          <input
            type="range"
            min="1"
            max="60"
            step="1"
            value={config.time_limit_seconds}
            onChange={(e) => onConfigChange({ ...config, time_limit_seconds: parseFloat(e.target.value) })}
            style={{ width: '100%', cursor: 'pointer' }}
          />
        </div>

        {/* Preference Points Scheme Collapsible */}
        <div style={{ border: '1px solid #e2e8f0', borderRadius: '6px', overflow: 'hidden', marginTop: '12px' }}>
          <button
            type="button"
            onClick={() => setShowScoreScheme(!showScoreScheme)}
            style={{
              width: '100%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '8px 12px',
              background: '#f8fafc',
              border: 'none',
              cursor: 'pointer',
              fontSize: '0.8rem',
              fontWeight: 600,
              color: '#334155',
            }}
          >
            <span>Preference Score Scheme</span>
            {showScoreScheme ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          </button>
          {showScoreScheme && (
            <div style={{ padding: '12px', background: '#ffffff', display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <span style={{ fontSize: '0.75rem', color: '#64748b' }}>Points granted per ranked choice:</span>
              {[0, 1, 2, 3, 4].map((idx) => (
                <div key={idx} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: '0.8rem', color: '#475569' }}>Choice #{idx + 1}:</span>
                  <input
                    type="number"
                    min="1"
                    max="1000"
                    value={config.points_per_rank[idx] || 10}
                    onChange={(e) => handlePointChange(idx, parseInt(e.target.value) || 1)}
                    className="form-input"
                    style={{ width: '80px', padding: '4px 8px', fontSize: '0.8rem' }}
                  />
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Weighted Mode Parameters */}
        {config.priority_mode === 'weighted' && (
          <div style={{ border: '1px solid #e2e8f0', borderRadius: '6px', overflow: 'hidden', marginTop: '10px' }}>
            <button
              type="button"
              onClick={() => setShowWeights(!showWeights)}
              style={{
                width: '100%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '8px 12px',
                background: '#f8fafc',
                border: 'none',
                cursor: 'pointer',
                fontSize: '0.8rem',
                fontWeight: 600,
                color: '#334155',
              }}
            >
              <span>Linear Weights</span>
              {showWeights ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            </button>
            {showWeights && (
              <div style={{ padding: '12px', background: '#ffffff', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: '0.8rem', color: '#475569' }}>Weight Assigned:</span>
                  <input
                    type="number"
                    value={config.weight_assigned}
                    onChange={(e) => onConfigChange({ ...config, weight_assigned: parseInt(e.target.value) || 1000 })}
                    className="form-input"
                    style={{ width: '100px', padding: '4px 8px', fontSize: '0.8rem' }}
                  />
                </div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: '0.8rem', color: '#475569' }}>Weight Preference:</span>
                  <input
                    type="number"
                    value={config.weight_preference}
                    onChange={(e) => onConfigChange({ ...config, weight_preference: parseInt(e.target.value) || 10 })}
                    className="form-input"
                    style={{ width: '100px', padding: '4px 8px', fontSize: '0.8rem' }}
                  />
                </div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: '0.8rem', color: '#475569' }}>Weight Stability:</span>
                  <input
                    type="number"
                    value={config.weight_stability}
                    onChange={(e) => onConfigChange({ ...config, weight_stability: parseInt(e.target.value) || 500 })}
                    className="form-input"
                    style={{ width: '100px', padding: '4px 8px', fontSize: '0.8rem' }}
                  />
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      <hr style={{ border: 'none', borderTop: '1px solid #e2e8f0' }} />

      {/* System Data Summary */}
      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '12px' }}>
          <Database size={16} color="#059669" />
          <h2 style={{ fontSize: '0.9rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em', color: '#475569' }}>
            System Data
          </h2>
        </div>

        {status ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '0.84rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#64748b' }}>👥 Applicants:</span>
              <span style={{ fontWeight: 600 }}>
                {status.total_applicants} ({status.active_applicants} active, {status.withdrawn_applicants} withdrawn)
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#64748b' }}>🏫 Programs:</span>
              <span style={{ fontWeight: 600 }}>
                {status.total_programs} ({status.total_capacity} seats)
              </span>
            </div>

            <div style={{ marginTop: '4px' }}>
              {status.has_baseline && status.baseline_summary ? (
                <div className="alert alert-success" style={{ padding: '8px 12px', fontSize: '0.78rem' }}>
                  <CheckCircle2 size={16} style={{ flexShrink: 0 }} />
                  <div>
                    <strong>Baseline Active:</strong>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.72rem' }}>{status.baseline_summary.run_id}</div>
                    <div>{status.baseline_summary.total_assigned} seats assigned</div>
                  </div>
                </div>
              ) : (
                <div className="alert alert-warning" style={{ padding: '8px 12px', fontSize: '0.78rem' }}>
                  <AlertTriangle size={16} style={{ flexShrink: 0 }} />
                  <span>No active baseline allocation set.</span>
                </div>
              )}
            </div>
          </div>
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#64748b', fontSize: '0.8rem' }}>
            <div className="spinner" />
            <span>Loading database status...</span>
          </div>
        )}
      </div>

      <hr style={{ border: 'none', borderTop: '1px solid #e2e8f0' }} />

      {/* Reset to Default Sample Data Button */}
      <div style={{ marginTop: 'auto' }}>
        {confirmReset ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <span style={{ fontSize: '0.8rem', color: '#dc2626', fontWeight: 600 }}>Reset dataset to 200 sample candidates and 10 programs?</span>
            <div style={{ display: 'flex', gap: '8px' }}>
              <button
                type="button"
                className="btn btn-danger btn-sm"
                style={{ flex: 1 }}
                onClick={async () => {
                  setConfirmReset(false);
                  await onResetData();
                }}
                disabled={loading}
              >
                Confirm Reset
              </button>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                style={{ flex: 1 }}
                onClick={() => setConfirmReset(false)}
              >
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <button
            type="button"
            className="btn btn-secondary"
            style={{ width: '100%', fontSize: '0.8rem', padding: '8px' }}
            onClick={() => setConfirmReset(true)}
            disabled={loading}
          >
            <RotateCcw size={14} />
            <span>Reset to Sample Data</span>
          </button>
        )}
      </div>
    </aside>
  );
};


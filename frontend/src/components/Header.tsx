import React from 'react';
import {
  LayoutDashboard,
  Users,
  Rocket,
  UserMinus,
  Sliders,
  FileCheck2,
  History,
  CheckCircle2,
} from 'lucide-react';
import { SystemStatus } from '../types';

export type TabKey =
  | 'dashboard'
  | 'data-management'
  | 'initial-allocation'
  | 'withdrawal-analysis'
  | 'capacity-changes'
  | 'appeals'
  | 'history';

interface HeaderProps {
  activeTab: TabKey;
  onTabChange: (tab: TabKey) => void;
  status: SystemStatus | null;
}

export const Header: React.FC<HeaderProps> = ({ activeTab, onTabChange, status }) => {
  const tabs = [
    { key: 'dashboard' as TabKey, label: 'Dashboard', icon: LayoutDashboard },
    { key: 'data-management' as TabKey, label: 'Applicants & Programs', icon: Users },
    { key: 'initial-allocation' as TabKey, label: 'Initial Allocation', icon: Rocket },
    { key: 'withdrawal-analysis' as TabKey, label: 'Withdrawal Analysis', icon: UserMinus },
    { key: 'capacity-changes' as TabKey, label: 'Capacity Changes', icon: Sliders },
    { key: 'appeals' as TabKey, label: 'Appeals', icon: FileCheck2 },
    { key: 'history' as TabKey, label: 'Allocation History', icon: History },
  ];

  return (
    <header className="top-navbar">
      <nav className="nav-tabs">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              type="button"
              className={`nav-tab-btn ${isActive ? 'active' : ''}`}
              onClick={() => onTabChange(tab.key)}
            >
              <Icon size={16} />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </nav>

      {/* Baseline pill badge on top right */}
      {status?.has_baseline && status.baseline_summary && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            background: '#f0fdf4',
            border: '1px solid #bbf7d0',
            color: '#15803d',
            padding: '6px 12px',
            borderRadius: '9999px',
            fontSize: '0.78rem',
            fontWeight: 600,
          }}
        >
          <CheckCircle2 size={14} />
          <span>
            Baseline: {status.baseline_summary.total_assigned} / {status.total_capacity} seats
          </span>
        </div>
      )}
    </header>
  );
};


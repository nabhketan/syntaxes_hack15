import React, { useState, useEffect, useCallback } from 'react';
import { Sidebar } from './components/Sidebar';
import { Header, TabKey } from './components/Header';
import { DashboardTab } from './components/DashboardTab';
import { DataManagementTab } from './components/DataManagementTab';
import { InitialAllocationTab } from './components/InitialAllocationTab';
import { WithdrawalAnalysisTab } from './components/WithdrawalAnalysisTab';
import { CapacityChangesTab } from './components/CapacityChangesTab';
import { AppealsTab } from './components/AppealsTab';
import { AllocationHistoryTab } from './components/AllocationHistoryTab';
import {
  Applicant,
  Program,
  OptimizationConfig,
  AllocationResult,
  SystemStatus,
  ValidationStatus,
  UndoStatus,
} from './types';
import { api } from './api/client';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabKey>('dashboard');

  // Shared Config
  const [config, setConfig] = useState<OptimizationConfig>({
    priority_mode: 'lexicographic',
    only_assign_preferred: true,
    time_limit_seconds: 15.0,
    points_per_rank: [100, 70, 45, 25, 10],
    weight_assigned: 100000,
    weight_preference: 1000,
    weight_stability: 50000,
  });

  // Server state
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [baseline, setBaseline] = useState<AllocationResult | null>(null);
  const [programs, setPrograms] = useState<Program[]>([]);
  const [applicants, setApplicants] = useState<Applicant[]>([]);
  const [validation, setValidation] = useState<ValidationStatus | null>(null);
  const [undoStatus, setUndoStatus] = useState<UndoStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [apiError, setApiError] = useState<string | null>(null);

  const refreshAllData = useCallback(async () => {
    try {
      const [statusRes, baselineRes, progsRes, appsRes, valRes, undoRes] = await Promise.all([
        api.getStatus(),
        api.getBaseline(),
        api.getPrograms(),
        api.getApplicants(),
        api.getValidation(),
        api.getUndoStatus(),
      ]);

      setStatus(statusRes);
      setBaseline(baselineRes.baseline);
      setPrograms(progsRes.programs);
      setApplicants(appsRes.applicants);
      setValidation(valRes);
      setUndoStatus(undoRes);
      setApiError(null);
    } catch (err: any) {
      console.error('Failed to load application data:', err);
      setApiError(`Could not connect to FAIRSHIFT API: ${err.message}. Ensure the FastAPI server is running at http://localhost:8000.`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshAllData();
  }, [refreshAllData]);

  const handleResetData = async () => {
    setLoading(true);
    try {
      await api.resetSampleData();
      await refreshAllData();
    } catch (err: any) {
      setApiError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-container">
      {/* Sidebar with settings and data summary */}
      <Sidebar
        config={config}
        onConfigChange={setConfig}
        status={status}
        onResetData={handleResetData}
        loading={loading}
      />

      {/* Main Content Area */}
      <div className="main-content">
        <Header activeTab={activeTab} onTabChange={setActiveTab} status={status} />

        <main className="content-body">
          {apiError && (
            <div className="alert alert-error">
              <span>⚠️ {apiError}</span>
            </div>
          )}

          {activeTab === 'dashboard' && (
            <DashboardTab
              status={status}
              baseline={baseline}
              programs={programs}
              onNavigateToTab={(tab) => setActiveTab(tab as TabKey)}
            />
          )}

          {activeTab === 'data-management' && (
            <DataManagementTab
              programs={programs}
              applicants={applicants}
              validation={validation}
              undoStatus={undoStatus}
              onRefreshData={refreshAllData}
              loading={loading}
            />
          )}

          {activeTab === 'initial-allocation' && (
            <InitialAllocationTab
              applicants={applicants}
              programs={programs}
              config={config}
              onBaselineUpdated={refreshAllData}
            />
          )}

          {activeTab === 'withdrawal-analysis' && (
            <WithdrawalAnalysisTab
              applicants={applicants}
              programs={programs}
              baseline={baseline}
              config={config}
              onBaselineUpdated={refreshAllData}
            />
          )}

          {activeTab === 'capacity-changes' && (
            <CapacityChangesTab
              applicants={applicants}
              programs={programs}
              baseline={baseline}
              config={config}
              onBaselineUpdated={refreshAllData}
            />
          )}

          {activeTab === 'appeals' && (
            <AppealsTab
              applicants={applicants}
              programs={programs}
              baseline={baseline}
              config={config}
              onBaselineUpdated={refreshAllData}
            />
          )}

          {activeTab === 'history' && (
            <AllocationHistoryTab onBaselineRestored={refreshAllData} />
          )}
        </main>
      </div>
    </div>
  );
};


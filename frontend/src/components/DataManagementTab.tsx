import React, { useState } from 'react';
import {
  RotateCcw,
  AlertTriangle,
  CheckCircle2,
  Download,
  Plus,
  RefreshCw,
  Trash2,
  Upload,
  Search,
  Filter,
  Wand2,
  History,
  ChevronDown,
  ChevronRight,
  Sparkles,
} from 'lucide-react';
import {
  Applicant,
  Program,
  ValidationStatus,
  UndoStatus,
} from '../types';
import { api } from '../api/client';

interface DataManagementTabProps {
  programs: Program[];
  applicants: Applicant[];
  validation: ValidationStatus | null;
  undoStatus: UndoStatus | null;
  onRefreshData: () => Promise<void>;
  loading: boolean;
}

export const DataManagementTab: React.FC<DataManagementTabProps> = ({
  programs,
  applicants,
  validation,
  undoStatus,
  onRefreshData,
  loading,
}) => {
  const [activeSubTab, setActiveSubTab] = useState<'programs' | 'applicants'>('programs');

  // Program Management State
  const [progSearch, setProgSearch] = useState('');
  const [progAction, setProgAction] = useState<'add' | 'replace' | 'remove' | 'import'>('add');
  const [newProgId, setNewProgId] = useState('');
  const [newProgName, setNewProgName] = useState('');
  const [newProgCap, setNewProgCap] = useState(20);
  const [newProgCrit, setNewProgCrit] = useState('ALL');
  const [newProgDesc, setNewProgDesc] = useState('');

  // Replace Program State
  const [replaceProgId, setReplaceProgId] = useState<string>(programs[0]?.program_id || '');
  const [replaceName, setReplaceName] = useState('');
  const [replaceCap, setReplaceCap] = useState(20);
  const [replaceCrit, setReplaceCrit] = useState('ALL');
  const [replaceDesc, setReplaceDesc] = useState('');
  const [cascadeProgId, setCascadeProgId] = useState(true);

  // Remove Program State
  const [removeProgId, setRemoveProgId] = useState<string>(programs[0]?.program_id || '');
  const [cleanProgRefs, setCleanProgRefs] = useState(true);

  // Import Program State
  const [progImportFile, setProgImportFile] = useState<File | null>(null);
  const [progImportMode, setProgImportMode] = useState<'merge' | 'replace'>('replace');
  const [progReconcile, setProgReconcile] = useState(true);
  const [progClearApps, setProgClearApps] = useState(false);

  // Applicant Management State
  const [appSearch, setAppSearch] = useState('');
  const [appStatusFilter, setAppStatusFilter] = useState<'all' | 'active' | 'withdrawn'>('all');
  const [appAction, setAppAction] = useState<'add' | 'replace' | 'remove' | 'import'>('add');
  const [newAppId, setNewAppId] = useState('');
  const [newAppName, setNewAppName] = useState('');
  const [newAppStatus, setNewAppStatus] = useState('active');
  const [newAppElig, setNewAppElig] = useState('ALL');
  const [newAppPrefs, setNewAppPrefs] = useState<string[]>([]);
  const [newAppNotes, setNewAppNotes] = useState('');

  // Replace Applicant State
  const [replaceAppId, setReplaceAppId] = useState<string>(applicants[0]?.applicant_id || '');
  const [replaceAppName, setReplaceAppName] = useState('');
  const [replaceAppStatus, setReplaceAppStatus] = useState('active');
  const [replaceAppElig, setReplaceAppElig] = useState('ALL');
  const [replaceAppPrefs, setReplaceAppPrefs] = useState<string[]>([]);
  const [replaceAppNotes, setReplaceAppNotes] = useState('');

  // Remove Applicant State
  const [removeAppId, setRemoveAppId] = useState<string>(applicants[0]?.applicant_id || '');

  // Import Applicant State
  const [appImportFile, setAppImportFile] = useState<File | null>(null);
  const [appImportMode, setAppImportMode] = useState<'merge' | 'replace'>('replace');
  const [appCleanInvalid, setAppCleanInvalid] = useState(true);

  // UI state
  const [actionMessage, setActionMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [showUndoHistory, setShowUndoHistory] = useState(false);
  const [showErrorLog, setShowErrorLog] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const showMsg = (text: string, type: 'success' | 'error' = 'success') => {
    setActionMessage({ text, type });
    setTimeout(() => setActionMessage(null), 6000);
  };

  // Populate replace program form when selection changes
  const handleSelectProgramToReplace = (pid: string) => {
    setReplaceProgId(pid);
    const p = programs.find((x) => x.program_id === pid);
    if (p) {
      setReplaceName(p.name);
      setReplaceCap(p.capacity);
      setReplaceCrit(p.eligibility_criteria);
      setReplaceDesc(p.description);
    }
  };

  // Populate replace applicant form when selection changes
  const handleSelectApplicantToReplace = (aid: string) => {
    setReplaceAppId(aid);
    const a = applicants.find((x) => x.applicant_id === aid);
    if (a) {
      setReplaceAppName(a.name);
      setReplaceAppStatus(a.status);
      setReplaceAppElig(a.eligibility.join(', '));
      setReplaceAppPrefs(a.preferences);
      setReplaceAppNotes(a.notes || '');
    }
  };

  // --- Actions ---

  const handleUndo = async () => {
    setSubmitting(true);
    try {
      const res = await api.undo();
      showMsg(`Undid: ${res.undone_action}! Dataset restored.`);
      await onRefreshData();
    } catch (err: any) {
      showMsg(err.message, 'error');
    } finally {
      setSubmitting(false);
    }
  };

  const handleAddProgram = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newProgId.trim() || !newProgName.trim()) {
      showMsg('Program ID and Name are required.', 'error');
      return;
    }
    setSubmitting(true);
    try {
      const res = await api.createProgram({
        program_id: newProgId.trim(),
        name: newProgName.trim(),
        capacity: newProgCap,
        eligibility_criteria: newProgCrit.trim() || 'ALL',
        description: newProgDesc.trim(),
      });
      showMsg(res.message);
      setNewProgId('');
      setNewProgName('');
      setNewProgDesc('');
      await onRefreshData();
    } catch (err: any) {
      showMsg(err.message, 'error');
    } finally {
      setSubmitting(false);
    }
  };

  const handleReplaceProgram = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!replaceProgId) return;
    setSubmitting(true);
    try {
      const res = await api.updateProgram(replaceProgId, {
        name: replaceName.trim(),
        capacity: replaceCap,
        eligibility_criteria: replaceCrit.trim() || 'ALL',
        description: replaceDesc.trim(),
        cascade_preference_rename: cascadeProgId,
      });
      showMsg(res.message);
      await onRefreshData();
    } catch (err: any) {
      showMsg(err.message, 'error');
    } finally {
      setSubmitting(false);
    }
  };

  const handleRemoveProgram = async () => {
    if (!removeProgId) return;
    setSubmitting(true);
    try {
      const res = await api.deleteProgram(removeProgId, cleanProgRefs);
      showMsg(res.message);
      await onRefreshData();
    } catch (err: any) {
      showMsg(err.message, 'error');
    } finally {
      setSubmitting(false);
    }
  };

  const handleImportPrograms = async () => {
    if (!progImportFile) {
      showMsg('Please select an Excel (.xlsx) or CSV file to upload.', 'error');
      return;
    }
    setSubmitting(true);
    try {
      const res = await api.importPrograms(progImportFile, progImportMode, progReconcile, progClearApps);
      showMsg(res.message);
      setProgImportFile(null);
      await onRefreshData();
    } catch (err: any) {
      showMsg(err.message, 'error');
    } finally {
      setSubmitting(false);
    }
  };

  const handleAddApplicant = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newAppId.trim() || !newAppName.trim()) {
      showMsg('Applicant ID and Name are required.', 'error');
      return;
    }
    setSubmitting(true);
    try {
      const elig = newAppElig.split(',').map((x) => x.trim()).filter(Boolean);
      const res = await api.createApplicant({
        applicant_id: newAppId.trim(),
        name: newAppName.trim(),
        status: newAppStatus,
        eligibility: elig.length > 0 ? elig : ['ALL'],
        preferences: newAppPrefs,
        notes: newAppNotes.trim(),
      });
      showMsg(res.message);
      setNewAppId('');
      setNewAppName('');
      setNewAppNotes('');
      setNewAppPrefs([]);
      await onRefreshData();
    } catch (err: any) {
      showMsg(err.message, 'error');
    } finally {
      setSubmitting(false);
    }
  };

  const handleReplaceApplicant = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!replaceAppId) return;
    setSubmitting(true);
    try {
      const elig = replaceAppElig.split(',').map((x) => x.trim()).filter(Boolean);
      const res = await api.updateApplicant(replaceAppId, {
        name: replaceAppName.trim(),
        status: replaceAppStatus,
        eligibility: elig.length > 0 ? elig : ['ALL'],
        preferences: replaceAppPrefs,
        notes: replaceAppNotes.trim(),
      });
      showMsg(res.message);
      await onRefreshData();
    } catch (err: any) {
      showMsg(err.message, 'error');
    } finally {
      setSubmitting(false);
    }
  };

  const handleRemoveApplicant = async () => {
    if (!removeAppId) return;
    setSubmitting(true);
    try {
      const res = await api.deleteApplicant(removeAppId);
      showMsg(res.message);
      await onRefreshData();
    } catch (err: any) {
      showMsg(err.message, 'error');
    } finally {
      setSubmitting(false);
    }
  };

  const handleImportApplicants = async () => {
    if (!appImportFile) {
      showMsg('Please select an Excel (.xlsx) or CSV file to upload.', 'error');
      return;
    }
    setSubmitting(true);
    try {
      const res = await api.importApplicants(appImportFile, appImportMode, appCleanInvalid);
      showMsg(res.message);
      setAppImportFile(null);
      await onRefreshData();
    } catch (err: any) {
      showMsg(err.message, 'error');
    } finally {
      setSubmitting(false);
    }
  };

  // Filtered Programs
  const filteredPrograms = programs.filter(
    (p) =>
      p.program_id.toLowerCase().includes(progSearch.toLowerCase()) ||
      p.name.toLowerCase().includes(progSearch.toLowerCase()) ||
      p.eligibility_criteria.toLowerCase().includes(progSearch.toLowerCase())
  );

  // Filtered Applicants
  const filteredApplicants = applicants.filter((a) => {
    if (appStatusFilter === 'active' && a.status !== 'active') return false;
    if (appStatusFilter === 'withdrawn' && a.status !== 'withdrawn') return false;
    if (appSearch) {
      const q = appSearch.toLowerCase();
      return (
        a.applicant_id.toLowerCase().includes(q) ||
        a.name.toLowerCase().includes(q) ||
        a.preferences.some((p) => p.toLowerCase().includes(q)) ||
        a.eligibility.some((e) => e.toLowerCase().includes(q))
      );
    }
    return true;
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Title */}
      <div className="page-header">
        <div>
          <h2 className="page-title">Data Management</h2>
          <p className="page-desc">
            Inspect, edit, import, and export applicants and training programs. Dataset integrity is audited live with multi-level undo.
          </p>
        </div>
      </div>

      {/* Action Toast / Message */}
      {actionMessage && (
        <div className={`alert alert-${actionMessage.type === 'success' ? 'success' : 'error'}`}>
          {actionMessage.type === 'success' ? <CheckCircle2 size={18} /> : <AlertTriangle size={18} />}
          <span>{actionMessage.text}</span>
        </div>
      )}

      {/* Undo Banner */}
      {undoStatus && undoStatus.undo_count > 0 && undoStatus.last_action && (
        <div className="undo-banner">
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <RotateCcw size={18} color="#2563eb" />
            <div>
              <span style={{ fontWeight: 600, color: '#1e40af', fontSize: '0.85rem' }}>
                Undo Available ({undoStatus.undo_count} in history):
              </span>{' '}
              <span style={{ fontSize: '0.85rem', color: '#1e3a8a' }}>{undoStatus.last_action.action_description}</span>
            </div>
          </div>
          <div style={{ display: 'flex', gap: '10px' }}>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => setShowUndoHistory(!showUndoHistory)}
            >
              <History size={14} />
              <span>Stack ({undoStatus.undo_count})</span>
            </button>
            <button
              type="button"
              className="btn btn-primary btn-sm"
              onClick={handleUndo}
              disabled={submitting}
            >
              <RotateCcw size={14} />
              <span>Undo Last Action</span>
            </button>
          </div>
        </div>
      )}

      {/* Collapsible Undo History */}
      {showUndoHistory && undoStatus && (
        <div className="card" style={{ padding: '16px', background: '#f8fafc' }}>
          <div style={{ fontSize: '0.85rem', fontWeight: 600, marginBottom: '8px' }}>Undo History Stack:</div>
          <div className="table-container" style={{ maxHeight: '200px' }}>
            <table>
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Action Type</th>
                  <th>Description</th>
                </tr>
              </thead>
              <tbody>
                {undoStatus.history.map((item) => (
                  <tr key={item.id}>
                    <td style={{ fontSize: '0.75rem', fontFamily: 'var(--font-mono)' }}>
                      {item.timestamp?.slice(0, 19).replace('T', ' ')}
                    </td>
                    <td>
                      <span className="code-pill">{item.action_type}</span>
                    </td>
                    <td>{item.action_description}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Live Validation Alert Banner */}
      {validation && (
        <div>
          {!validation.is_valid ? (
            <div className="alert alert-error" style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <AlertTriangle size={20} color="#dc2626" />
                <span style={{ fontWeight: 700, fontSize: '0.95rem' }}>
                  Dataset Validation Alert: {validation.error_count} integrity issue
                  {validation.error_count !== 1 ? 's' : ''} detected.
                </span>
              </div>

              {validation.unlisted_pref_count > 0 && (
                <div style={{ background: '#ffffff', padding: '12px', borderRadius: '6px', border: '1px solid #fecaca', fontSize: '0.82rem', color: '#7f1d1d' }}>
                  <strong>Cause Identified:</strong> {validation.unlisted_pref_count} applicant preferences reference program IDs
                  that do not exist in the active program list (common when programs are imported from Excel/CSV with new IDs).
                </div>
              )}

              {/* 4 Actionable Fix Buttons */}
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                <button
                  type="button"
                  className="btn btn-primary btn-sm"
                  onClick={async () => {
                    setSubmitting(true);
                    try {
                      const res = await api.autoReconcile();
                      showMsg(res.message);
                      await onRefreshData();
                    } catch (e: any) {
                      showMsg(e.message, 'error');
                    } finally {
                      setSubmitting(false);
                    }
                  }}
                  disabled={submitting}
                >
                  <RefreshCw size={14} />
                  <span>🔄 Auto-Reconcile Dataset</span>
                </button>

                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={async () => {
                    setSubmitting(true);
                    try {
                      const res = await api.prunePreferences();
                      showMsg(res.message);
                      await onRefreshData();
                    } catch (e: any) {
                      showMsg(e.message, 'error');
                    } finally {
                      setSubmitting(false);
                    }
                  }}
                  disabled={submitting}
                >
                  <Wand2 size={14} />
                  <span>🧹 Prune Invalid Preferences</span>
                </button>

                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={async () => {
                    setSubmitting(true);
                    try {
                      const res = await api.autoAssignPreferences();
                      showMsg(res.message);
                      await onRefreshData();
                    } catch (e: any) {
                      showMsg(e.message, 'error');
                    } finally {
                      setSubmitting(false);
                    }
                  }}
                  disabled={submitting}
                >
                  <Sparkles size={14} />
                  <span>🎲 Auto-Assign Valid Prefs</span>
                </button>

                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={async () => {
                    setSubmitting(true);
                    try {
                      const res = await api.clearApplicants();
                      showMsg(res.message);
                      await onRefreshData();
                    } catch (e: any) {
                      showMsg(e.message, 'error');
                    } finally {
                      setSubmitting(false);
                    }
                  }}
                  disabled={submitting}
                >
                  <Trash2 size={14} />
                  <span>👥 Clear All Applicants</span>
                </button>
              </div>

              {/* Collapsible Error Log with max 20 preview */}
              <div style={{ marginTop: '4px' }}>
                <button
                  type="button"
                  onClick={() => setShowErrorLog(!showErrorLog)}
                  style={{
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    color: '#991b1b',
                    fontWeight: 600,
                    fontSize: '0.8rem',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                  }}
                >
                  {showErrorLog ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                  <span>Inspect All {validation.error_count} Validation Errors</span>
                </button>

                {showErrorLog && (
                  <div style={{ marginTop: '8px', maxHeight: '180px', overflowY: 'auto', background: '#ffffff', padding: '10px', borderRadius: '4px', fontSize: '0.78rem' }}>
                    <ul style={{ paddingLeft: '16px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                      {validation.errors.slice(0, 20).map((err, i) => (
                        <li key={i}>{err}</li>
                      ))}
                    </ul>
                    {validation.errors.length > 20 && (
                      <p style={{ marginTop: '8px', color: '#64748b', fontStyle: 'italic' }}>
                        ... and {validation.errors.length - 20} more errors. Use the Action buttons above to auto-fix.
                      </p>
                    )}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="alert alert-success">
              <CheckCircle2 size={18} color="#15803d" />
              <span style={{ fontWeight: 600 }}>Dataset is completely valid and ready for optimization.</span>
            </div>
          )}
        </div>
      )}

      {/* Subtab Navigation */}
      <div className="subtabs">
        <button
          type="button"
          className={`subtab-btn ${activeSubTab === 'programs' ? 'active' : ''}`}
          onClick={() => setActiveSubTab('programs')}
        >
          🏫 Training Programs ({programs.length})
        </button>
        <button
          type="button"
          className={`subtab-btn ${activeSubTab === 'applicants' ? 'active' : ''}`}
          onClick={() => setActiveSubTab('applicants')}
        >
          👥 Applicants ({applicants.length})
        </button>
      </div>

      {/* ========================================================= */}
      {/* PROGRAMS SUBTAB */}
      {/* ========================================================= */}
      {activeSubTab === 'programs' && (
        <div style={{ display: 'grid', gridTemplateColumns: '3fr 2fr', gap: '24px' }}>
          {/* Left: Program Table */}
          <div className="card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div style={{ position: 'relative', width: '280px' }}>
                <Search size={16} style={{ position: 'absolute', left: '10px', top: '10px', color: '#94a3b8' }} />
                <input
                  type="text"
                  placeholder="Search programs..."
                  value={progSearch}
                  onChange={(e) => setProgSearch(e.target.value)}
                  className="form-input"
                  style={{ paddingLeft: '32px' }}
                />
              </div>
              <a href={api.getProgramsCsvUrl()} download="programs.csv" className="btn btn-secondary btn-sm">
                <Download size={14} />
                <span>Export CSV</span>
              </a>
            </div>

            <div className="table-container" style={{ maxHeight: '520px' }}>
              <table>
                <thead>
                  <tr>
                    <th>Program ID</th>
                    <th>Name</th>
                    <th>Capacity</th>
                    <th>Eligibility Criteria</th>
                    <th>Description</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredPrograms.map((p) => (
                    <tr key={p.program_id}>
                      <td><span className="code-pill">{p.program_id}</span></td>
                      <td style={{ fontWeight: 600 }}>{p.name}</td>
                      <td><strong>{p.capacity}</strong></td>
                      <td><span style={{ fontSize: '0.8rem', color: '#475569' }}>{p.eligibility_criteria}</span></td>
                      <td style={{ fontSize: '0.78rem', color: '#64748b', maxWidth: '240px' }}>{p.description}</td>
                    </tr>
                  ))}
                  {filteredPrograms.length === 0 && (
                    <tr>
                      <td colSpan={5} style={{ textAlign: 'center', color: '#64748b', padding: '24px' }}>
                        No programs found matching filter.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            <div style={{ marginTop: '12px', fontSize: '0.8rem', color: '#64748b' }}>
              Total Programs: <strong>{programs.length}</strong> | Total Capacity:{' '}
              <strong>{programs.reduce((acc, p) => acc + p.capacity, 0)} seats</strong>
            </div>
          </div>

          {/* Right: Manage Programs Panel */}
          <div className="card">
            <div className="card-title">Manage Programs</div>

            {/* Action selector */}
            <div style={{ display: 'flex', gap: '6px', background: '#f1f5f9', padding: '4px', borderRadius: '8px', marginBottom: '16px' }}>
              {(['add', 'replace', 'remove', 'import'] as const).map((act) => (
                <button
                  key={act}
                  type="button"
                  onClick={() => {
                    setProgAction(act);
                    if (act === 'replace' && programs[0]) {
                      handleSelectProgramToReplace(programs[0].program_id);
                    }
                  }}
                  style={{
                    flex: 1,
                    padding: '6px',
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    border: 'none',
                    borderRadius: '6px',
                    cursor: 'pointer',
                    background: progAction === act ? '#ffffff' : 'transparent',
                    color: progAction === act ? '#2563eb' : '#64748b',
                    boxShadow: progAction === act ? 'var(--shadow-sm)' : 'none',
                    textTransform: 'capitalize',
                  }}
                >
                  {act === 'add' && '➕ Add'}
                  {act === 'replace' && '🔁 Replace'}
                  {act === 'remove' && '🗑️ Remove'}
                  {act === 'import' && '📥 Import'}
                </button>
              ))}
            </div>

            {/* ADD PROGRAM FORM */}
            {progAction === 'add' && (
              <form onSubmit={handleAddProgram}>
                <div className="form-group">
                  <label className="form-label">Program ID (Unique)</label>
                  <input
                    type="text"
                    placeholder="e.g. PROG_AI"
                    value={newProgId}
                    onChange={(e) => setNewProgId(e.target.value)}
                    className="form-input"
                    required
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Program Name</label>
                  <input
                    type="text"
                    placeholder="e.g. Artificial Intelligence Fellowship"
                    value={newProgName}
                    onChange={(e) => setNewProgName(e.target.value)}
                    className="form-input"
                    required
                  />
                </div>
                <div className="form-row">
                  <div className="form-group">
                    <label className="form-label">Seat Capacity</label>
                    <input
                      type="number"
                      min="0"
                      max="500"
                      value={newProgCap}
                      onChange={(e) => setNewProgCap(parseInt(e.target.value) || 0)}
                      className="form-input"
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Eligibility Criteria</label>
                    <input
                      type="text"
                      placeholder="ALL or required tags"
                      value={newProgCrit}
                      onChange={(e) => setNewProgCrit(e.target.value)}
                      className="form-input"
                    />
                  </div>
                </div>
                <div className="form-group">
                  <label className="form-label">Description</label>
                  <textarea
                    placeholder="Optional program details..."
                    value={newProgDesc}
                    onChange={(e) => setNewProgDesc(e.target.value)}
                    className="form-textarea"
                  />
                </div>
                <button type="submit" className="btn btn-primary" style={{ width: '100%' }} disabled={submitting}>
                  <Plus size={16} />
                  <span>Add Program Entry</span>
                </button>
              </form>
            )}

            {/* REPLACE PROGRAM FORM */}
            {progAction === 'replace' && (
              <form onSubmit={handleReplaceProgram}>
                <div className="form-group">
                  <label className="form-label">Select Program to Replace</label>
                  <select
                    className="form-select"
                    value={replaceProgId}
                    onChange={(e) => handleSelectProgramToReplace(e.target.value)}
                  >
                    {programs.map((p) => (
                      <option key={p.program_id} value={p.program_id}>
                        {p.program_id} - {p.name} (Cap: {p.capacity})
                      </option>
                    ))}
                  </select>
                </div>
                <div className="form-group">
                  <label className="form-label">Program Name</label>
                  <input
                    type="text"
                    value={replaceName}
                    onChange={(e) => setReplaceName(e.target.value)}
                    className="form-input"
                    required
                  />
                </div>
                <div className="form-row">
                  <div className="form-group">
                    <label className="form-label">Seat Capacity</label>
                    <input
                      type="number"
                      min="0"
                      max="500"
                      value={replaceCap}
                      onChange={(e) => setReplaceCap(parseInt(e.target.value) || 0)}
                      className="form-input"
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Eligibility Criteria</label>
                    <input
                      type="text"
                      value={replaceCrit}
                      onChange={(e) => setReplaceCrit(e.target.value)}
                      className="form-input"
                    />
                  </div>
                </div>
                <div className="form-group">
                  <label className="form-label">Description</label>
                  <textarea
                    value={replaceDesc}
                    onChange={(e) => setReplaceDesc(e.target.value)}
                    className="form-textarea"
                  />
                </div>
                <div className="form-group">
                  <label className="checkbox-label">
                    <input
                      type="checkbox"
                      checked={cascadeProgId}
                      onChange={(e) => setCascadeProgId(e.target.checked)}
                    />
                    <span>Cascade ID rename to applicant preferences & eligibility</span>
                  </label>
                </div>
                <button type="submit" className="btn btn-primary" style={{ width: '100%' }} disabled={submitting}>
                  <RefreshCw size={16} />
                  <span>Replace Program Entry</span>
                </button>
              </form>
            )}

            {/* REMOVE PROGRAM FORM */}
            {progAction === 'remove' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                <div className="form-group">
                  <label className="form-label">Select Program to Remove</label>
                  <select
                    className="form-select"
                    value={removeProgId}
                    onChange={(e) => setRemoveProgId(e.target.value)}
                  >
                    {programs.map((p) => (
                      <option key={p.program_id} value={p.program_id}>
                        {p.program_id} - {p.name} (Cap: {p.capacity})
                      </option>
                    ))}
                  </select>
                </div>

                <div className="alert alert-warning" style={{ fontSize: '0.8rem' }}>
                  <AlertTriangle size={16} style={{ flexShrink: 0 }} />
                  <div>
                    Removing <strong>{removeProgId}</strong> will remove seats from the system.
                  </div>
                </div>

                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={cleanProgRefs}
                    onChange={(e) => setCleanProgRefs(e.target.checked)}
                  />
                  <span>Automatically remove this program from applicant preference lists</span>
                </label>

                <button
                  type="button"
                  className="btn btn-danger"
                  style={{ width: '100%' }}
                  onClick={handleRemoveProgram}
                  disabled={submitting || !removeProgId}
                >
                  <Trash2 size={16} />
                  <span>Confirm Remove Program</span>
                </button>
              </div>
            )}

            {/* IMPORT PROGRAMS FORM */}
            {progAction === 'import' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                <div className="form-group">
                  <label className="form-label">Import Mode</label>
                  <div style={{ display: 'flex', gap: '16px' }}>
                    <label className="checkbox-label">
                      <input
                        type="radio"
                        name="progImportMode"
                        checked={progImportMode === 'replace'}
                        onChange={() => setProgImportMode('replace')}
                      />
                      <span>Replace all existing programs</span>
                    </label>
                    <label className="checkbox-label">
                      <input
                        type="radio"
                        name="progImportMode"
                        checked={progImportMode === 'merge'}
                        onChange={() => setProgImportMode('merge')}
                      />
                      <span>Append / Merge</span>
                    </label>
                  </div>
                </div>

                <div className="form-group">
                  <label className="checkbox-label">
                    <input
                      type="checkbox"
                      checked={progReconcile}
                      onChange={(e) => setProgReconcile(e.target.checked)}
                    />
                    <span>Reconcile applicant preferences & eligibility (Recommended)</span>
                  </label>
                </div>

                {progImportMode === 'replace' && (
                  <div className="form-group">
                    <label className="checkbox-label">
                      <input
                        type="checkbox"
                        checked={progClearApps}
                        onChange={(e) => setProgClearApps(e.target.checked)}
                      />
                      <span>Clear existing applicants (if uploading fresh applicants next)</span>
                    </label>
                  </div>
                )}

                <div className="form-group">
                  <label className="form-label">Select File (.xlsx or .csv)</label>
                  <input
                    type="file"
                    accept=".xlsx,.xls,.csv"
                    onChange={(e) => setProgImportFile(e.target.files?.[0] || null)}
                    className="form-input"
                  />
                </div>

                <button
                  type="button"
                  className="btn btn-primary"
                  style={{ width: '100%' }}
                  onClick={handleImportPrograms}
                  disabled={submitting || !progImportFile}
                >
                  <Upload size={16} />
                  <span>Process Programs Upload</span>
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ========================================================= */}
      {/* APPLICANTS SUBTAB */}
      {/* ========================================================= */}
      {activeSubTab === 'applicants' && (
        <div style={{ display: 'grid', gridTemplateColumns: '3fr 2fr', gap: '24px' }}>
          {/* Left: Applicants Table */}
          <div className="card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', gap: '10px' }}>
              <div style={{ position: 'relative', flex: 1 }}>
                <Search size={16} style={{ position: 'absolute', left: '10px', top: '10px', color: '#94a3b8' }} />
                <input
                  type="text"
                  placeholder="Search by ID, name, prefs, criteria..."
                  value={appSearch}
                  onChange={(e) => setAppSearch(e.target.value)}
                  className="form-input"
                  style={{ paddingLeft: '32px' }}
                />
              </div>

              <select
                className="form-select"
                style={{ width: '140px' }}
                value={appStatusFilter}
                onChange={(e) => setAppStatusFilter(e.target.value as any)}
              >
                <option value="all">All Statuses</option>
                <option value="active">Active Only</option>
                <option value="withdrawn">Withdrawn</option>
              </select>

              <a href={api.getApplicantsCsvUrl()} download="applicants.csv" className="btn btn-secondary btn-sm">
                <Download size={14} />
                <span>Export CSV</span>
              </a>
            </div>

            <div className="table-container" style={{ maxHeight: '520px' }}>
              <table>
                <thead>
                  <tr>
                    <th>Applicant ID</th>
                    <th>Name</th>
                    <th>Status</th>
                    <th>Ranked Preferences</th>
                    <th>Eligibility</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredApplicants.map((a) => (
                    <tr key={a.applicant_id}>
                      <td><span className="code-pill">{a.applicant_id}</span></td>
                      <td style={{ fontWeight: 600 }}>{a.name}</td>
                      <td>
                        <span className={`badge-status ${a.status === 'active' ? 'badge-optimal' : 'badge-timeout'}`}>
                          {a.status}
                        </span>
                      </td>
                      <td>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', maxWidth: '280px' }}>
                          {a.preferences.map((p, idx) => (
                            <span key={idx} className="code-pill" style={{ fontSize: '0.72rem' }}>
                              #{idx + 1} {p}
                            </span>
                          ))}
                          {a.preferences.length === 0 && <span style={{ color: '#94a3b8', fontStyle: 'italic' }}>None</span>}
                        </div>
                      </td>
                      <td>
                        <span style={{ fontSize: '0.78rem', color: '#475569' }}>
                          {a.eligibility.join(', ')}
                        </span>
                      </td>
                    </tr>
                  ))}
                  {filteredApplicants.length === 0 && (
                    <tr>
                      <td colSpan={5} style={{ textAlign: 'center', color: '#64748b', padding: '24px' }}>
                        No applicants found matching query.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            <div style={{ marginTop: '12px', fontSize: '0.8rem', color: '#64748b' }}>
              Showing <strong>{filteredApplicants.length}</strong> of <strong>{applicants.length}</strong> applicants
            </div>
          </div>

          {/* Right: Manage Applicants Panel */}
          <div className="card">
            <div className="card-title">Manage Applicants</div>

            {/* Action selector */}
            <div style={{ display: 'flex', gap: '6px', background: '#f1f5f9', padding: '4px', borderRadius: '8px', marginBottom: '16px' }}>
              {(['add', 'replace', 'remove', 'import'] as const).map((act) => (
                <button
                  key={act}
                  type="button"
                  onClick={() => {
                    setAppAction(act);
                    if (act === 'replace' && applicants[0]) {
                      handleSelectApplicantToReplace(applicants[0].applicant_id);
                    }
                  }}
                  style={{
                    flex: 1,
                    padding: '6px',
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    border: 'none',
                    borderRadius: '6px',
                    cursor: 'pointer',
                    background: appAction === act ? '#ffffff' : 'transparent',
                    color: appAction === act ? '#2563eb' : '#64748b',
                    boxShadow: appAction === act ? 'var(--shadow-sm)' : 'none',
                    textTransform: 'capitalize',
                  }}
                >
                  {act === 'add' && '➕ Add'}
                  {act === 'replace' && '🔁 Replace'}
                  {act === 'remove' && '🗑️ Remove'}
                  {act === 'import' && '📥 Import'}
                </button>
              ))}
            </div>

            {/* ADD APPLICANT FORM */}
            {appAction === 'add' && (
              <form onSubmit={handleAddApplicant}>
                <div className="form-group">
                  <label className="form-label">Applicant ID (Unique)</label>
                  <input
                    type="text"
                    placeholder="e.g. APP201"
                    value={newAppId}
                    onChange={(e) => setNewAppId(e.target.value)}
                    className="form-input"
                    required
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Full Name</label>
                  <input
                    type="text"
                    placeholder="e.g. Maya Lin"
                    value={newAppName}
                    onChange={(e) => setNewAppName(e.target.value)}
                    className="form-input"
                    required
                  />
                </div>
                <div className="form-row">
                  <div className="form-group">
                    <label className="form-label">Status</label>
                    <select
                      className="form-select"
                      value={newAppStatus}
                      onChange={(e) => setNewAppStatus(e.target.value)}
                    >
                      <option value="active">Active</option>
                      <option value="withdrawn">Withdrawn</option>
                    </select>
                  </div>
                  <div className="form-group">
                    <label className="form-label">Eligibility Tags</label>
                    <input
                      type="text"
                      placeholder="comma-separated tags"
                      value={newAppElig}
                      onChange={(e) => setNewAppElig(e.target.value)}
                      className="form-input"
                    />
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label">Ranked Preferences (Click to add in rank order)</label>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '8px' }}>
                    {programs.map((p) => {
                      const isRanked = newAppPrefs.includes(p.program_id);
                      const rankIdx = newAppPrefs.indexOf(p.program_id);
                      return (
                        <button
                          key={p.program_id}
                          type="button"
                          className={`btn btn-sm ${isRanked ? 'btn-primary' : 'btn-secondary'}`}
                          onClick={() => {
                            if (isRanked) {
                              setNewAppPrefs(newAppPrefs.filter((x) => x !== p.program_id));
                            } else {
                              setNewAppPrefs([...newAppPrefs, p.program_id]);
                            }
                          }}
                        >
                          {isRanked ? `#${rankIdx + 1} ` : '+ '}
                          {p.program_id}
                        </button>
                      );
                    })}
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label">Notes</label>
                  <textarea
                    placeholder="Optional notes..."
                    value={newAppNotes}
                    onChange={(e) => setNewAppNotes(e.target.value)}
                    className="form-textarea"
                  />
                </div>

                <button type="submit" className="btn btn-primary" style={{ width: '100%' }} disabled={submitting}>
                  <Plus size={16} />
                  <span>Add Applicant Entry</span>
                </button>
              </form>
            )}

            {/* REPLACE APPLICANT FORM */}
            {appAction === 'replace' && (
              <form onSubmit={handleReplaceApplicant}>
                <div className="form-group">
                  <label className="form-label">Select Applicant to Replace</label>
                  <select
                    className="form-select"
                    value={replaceAppId}
                    onChange={(e) => handleSelectApplicantToReplace(e.target.value)}
                  >
                    {applicants.map((a) => (
                      <option key={a.applicant_id} value={a.applicant_id}>
                        {a.applicant_id} - {a.name} ({a.status})
                      </option>
                    ))}
                  </select>
                </div>

                <div className="form-group">
                  <label className="form-label">Full Name</label>
                  <input
                    type="text"
                    value={replaceAppName}
                    onChange={(e) => setReplaceAppName(e.target.value)}
                    className="form-input"
                    required
                  />
                </div>

                <div className="form-row">
                  <div className="form-group">
                    <label className="form-label">Status</label>
                    <select
                      className="form-select"
                      value={replaceAppStatus}
                      onChange={(e) => setReplaceAppStatus(e.target.value)}
                    >
                      <option value="active">Active</option>
                      <option value="withdrawn">Withdrawn</option>
                    </select>
                  </div>
                  <div className="form-group">
                    <label className="form-label">Eligibility Tags</label>
                    <input
                      type="text"
                      value={replaceAppElig}
                      onChange={(e) => setReplaceAppElig(e.target.value)}
                      className="form-input"
                    />
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label">Ranked Preferences</label>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '8px' }}>
                    {programs.map((p) => {
                      const isRanked = replaceAppPrefs.includes(p.program_id);
                      const rankIdx = replaceAppPrefs.indexOf(p.program_id);
                      return (
                        <button
                          key={p.program_id}
                          type="button"
                          className={`btn btn-sm ${isRanked ? 'btn-primary' : 'btn-secondary'}`}
                          onClick={() => {
                            if (isRanked) {
                              setReplaceAppPrefs(replaceAppPrefs.filter((x) => x !== p.program_id));
                            } else {
                              setReplaceAppPrefs([...replaceAppPrefs, p.program_id]);
                            }
                          }}
                        >
                          {isRanked ? `#${rankIdx + 1} ` : '+ '}
                          {p.program_id}
                        </button>
                      );
                    })}
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label">Notes</label>
                  <textarea
                    value={replaceAppNotes}
                    onChange={(e) => setReplaceAppNotes(e.target.value)}
                    className="form-textarea"
                  />
                </div>

                <button type="submit" className="btn btn-primary" style={{ width: '100%' }} disabled={submitting}>
                  <RefreshCw size={16} />
                  <span>Replace Applicant Entry</span>
                </button>
              </form>
            )}

            {/* REMOVE APPLICANT */}
            {appAction === 'remove' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                <div className="form-group">
                  <label className="form-label">Select Applicant to Remove</label>
                  <select
                    className="form-select"
                    value={removeAppId}
                    onChange={(e) => setRemoveAppId(e.target.value)}
                  >
                    {applicants.map((a) => (
                      <option key={a.applicant_id} value={a.applicant_id}>
                        {a.applicant_id} - {a.name} ({a.status})
                      </option>
                    ))}
                  </select>
                </div>

                <div className="alert alert-warning" style={{ fontSize: '0.8rem' }}>
                  <AlertTriangle size={16} style={{ flexShrink: 0 }} />
                  <div>
                    Are you sure you want to permanently remove applicant <strong>{removeAppId}</strong>?
                  </div>
                </div>

                <button
                  type="button"
                  className="btn btn-danger"
                  style={{ width: '100%' }}
                  onClick={handleRemoveApplicant}
                  disabled={submitting || !removeAppId}
                >
                  <Trash2 size={16} />
                  <span>Confirm Remove Applicant</span>
                </button>
              </div>
            )}

            {/* IMPORT APPLICANTS */}
            {appAction === 'import' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                <div className="form-group">
                  <label className="form-label">Import Mode</label>
                  <div style={{ display: 'flex', gap: '16px' }}>
                    <label className="checkbox-label">
                      <input
                        type="radio"
                        name="appImportMode"
                        checked={appImportMode === 'replace'}
                        onChange={() => setAppImportMode('replace')}
                      />
                      <span>Replace all existing applicants</span>
                    </label>
                    <label className="checkbox-label">
                      <input
                        type="radio"
                        name="appImportMode"
                        checked={appImportMode === 'merge'}
                        onChange={() => setAppImportMode('merge')}
                      />
                      <span>Append / Merge</span>
                    </label>
                  </div>
                </div>

                <div className="form-group">
                  <label className="checkbox-label">
                    <input
                      type="checkbox"
                      checked={appCleanInvalid}
                      onChange={(e) => setAppCleanInvalid(e.target.checked)}
                    />
                    <span>Automatically prune preferences referencing unlisted programs</span>
                  </label>
                </div>

                <div className="form-group">
                  <label className="form-label">Select File (.xlsx or .csv)</label>
                  <input
                    type="file"
                    accept=".xlsx,.xls,.csv"
                    onChange={(e) => setAppImportFile(e.target.files?.[0] || null)}
                    className="form-input"
                  />
                </div>

                <button
                  type="button"
                  className="btn btn-primary"
                  style={{ width: '100%' }}
                  onClick={handleImportApplicants}
                  disabled={submitting || !appImportFile}
                >
                  <Upload size={16} />
                  <span>Process Applicants Upload</span>
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};


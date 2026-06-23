import { useEffect, useState } from 'react';
import { getAllApps, createApp, deleteApp, getAllDeps, createDep, deleteDep, addPurpose, addSymptom } from '../api/registry.api';
import LoadingSpinner from '../components/ui/LoadingSpinner';
import ErrorMessage from '../components/ui/ErrorMessage';
import toast from 'react-hot-toast';

const DEP_TYPES = [
  'login/access', 
  'performance/slow', 
  'data error', 
  'total outage', 
  'partial/degraded', 
  'cosmetic/UI', 
  'other'
];

function Registry() {
  const [apps,    setApps]    = useState([]);
  const [deps,    setDeps]    = useState([]);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState(null);
  const [tab,     setTab]     = useState('apps');
  const [newApp,  setNewApp]  = useState({ name: '', description: '', owning_team: '', contact: '' });
  const [newDep,  setNewDep]  = useState({ source_app_id: '', dependent_app_id: '', dependency_nature: 'login/access' });
  const [expandedApp,  setExpandedApp]  = useState(null);
  const [symptomText,  setSymptomText]  = useState('');
  const [purposeText,  setPurposeText]  = useState('');

  async function load() {
    setLoading(true); setError(null);
    try {
      const [appRes, depRes] = await Promise.all([getAllApps(), getAllDeps()]);
      setApps(appRes.data ?? []);
      setDeps(depRes.data ?? []);
    } catch (e) { setError(e.message || 'Failed to load registry'); }
    finally { setLoading(false); }
  }

  useEffect(() => { load(); }, []);

  async function handleCreateApp() {
    if (!newApp.name.trim()) { toast.error('App name required'); return; }
    try { await createApp({ ...newApp }); toast.success('App added!'); setNewApp({ name: '', description: '', owning_team: '', contact: '' }); load(); }
    catch (e) { toast.error(e.response?.data?.detail || 'Create failed'); }
  }

  async function handleDeleteApp(id) {
    if (!confirm('Delete this app?')) return;
    try { await deleteApp(id); toast.success('Deleted'); load(); }
    catch { toast.error('Delete failed'); }
  }

  async function handleCreateDep() {
    if (!newDep.source_app_id || !newDep.dependent_app_id) { toast.error('Both apps required'); return; }
    try {
      await createDep({
        source_app_id: +newDep.source_app_id,
        dependent_app_id: +newDep.dependent_app_id,
        dependency_nature: newDep.dependency_nature,
      });
      toast.success('Dependency added!');
      setNewDep({ source_app_id: '', dependent_app_id: '', dependency_nature: 'login/access' });
      load();
    }
    catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
  }

  async function handleDeleteDep(id) {
    try { await deleteDep(id); toast.success('Removed'); load(); }
    catch { toast.error('Delete failed'); }
  }

  async function handleAddSymptom(appId) {
    if (!symptomText.trim()) return;
    try {
      await addSymptom(appId, { application_id: appId, symptom_text: symptomText.trim() });
      toast.success('Symptom added'); setSymptomText(''); load();
    }
    catch { toast.error('Failed'); }
  }

  async function handleAddPurpose(appId) {
    if (!purposeText.trim()) return;
    try {
      await addPurpose(appId, { application_id: appId, purpose_text: purposeText.trim() });
      toast.success('Purpose added'); setPurposeText(''); load();
    }
    catch { toast.error('Failed'); }
  }

  if (loading) return <LoadingSpinner text="Registry load ho rahi hai..." />;
  if (error)   return <ErrorMessage message={error} onRetry={load} />;

  // Helper to resolve app names from IDs for dependency display
  const appMap = Object.fromEntries(apps.map(a => [a.id, a.name]));

  return (
    <div>
      <div style={{ display: 'flex', borderBottom: '0.5px solid #e2e8f0', marginBottom: '20px' }}>
        {['apps', 'deps'].map(t => (
          <button key={t} onClick={() => setTab(t)} style={{ padding: '8px 20px', fontSize: '13px', border: 'none', cursor: 'pointer', background: 'none', borderBottom: tab === t ? '2px solid #185FA5' : '2px solid transparent', color: tab === t ? '#185FA5' : '#64748b', fontWeight: tab === t ? 500 : 400 }}>
            {t === 'apps' ? `Applications (${apps.length})` : `Dependencies (${deps.length})`}
          </button>
        ))}
      </div>

      {tab === 'apps' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div style={card}>
            <div style={cardTitle}>Add Application</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginBottom: '10px' }}>
              <input placeholder="App name *" value={newApp.name} onChange={e => setNewApp(p => ({ ...p, name: e.target.value }))} style={inputStyle} />
              <input placeholder="Owning team" value={newApp.owning_team} onChange={e => setNewApp(p => ({ ...p, owning_team: e.target.value }))} style={inputStyle} />
              <input placeholder="Description" value={newApp.description} onChange={e => setNewApp(p => ({ ...p, description: e.target.value }))} style={inputStyle} />
              <input placeholder="Contact" value={newApp.contact} onChange={e => setNewApp(p => ({ ...p, contact: e.target.value }))} style={inputStyle} />
            </div>
            <button onClick={handleCreateApp} style={primaryBtn}>+ Add App</button>
          </div>

          {apps.map(app => (
            <div key={app.id} style={card}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <div style={{ fontWeight: 500, fontSize: '14px' }}>{app.name}</div>
                  <div style={{ fontSize: '12px', color: '#64748b', marginTop: '2px' }}>
                    {app.owning_team && `Team: ${app.owning_team}`}{app.contact && ` · ${app.contact}`}
                  </div>
                  {app.description && <div style={{ fontSize: '12px', color: '#475569', marginTop: '4px' }}>{app.description}</div>}
                </div>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button onClick={() => setExpandedApp(expandedApp === app.id ? null : app.id)} style={secondaryBtn}>{expandedApp === app.id ? 'Close' : 'Edit'}</button>
                  <button onClick={() => handleDeleteApp(app.id)} style={dangerBtn}>Delete</button>
                </div>
              </div>
              {expandedApp === app.id && (
                <div style={{ marginTop: '14px', borderTop: '0.5px solid #f1f5f9', paddingTop: '14px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  <div>
                    <div style={{ fontSize: '12px', color: '#64748b', marginBottom: '6px' }}>Add Symptom</div>
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <input value={symptomText} onChange={e => setSymptomText(e.target.value)} placeholder="e.g. login page not loading..." style={{ ...inputStyle, flex: 1 }} />
                      <button onClick={() => handleAddSymptom(app.id)} style={primaryBtn}>Add</button>
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: '12px', color: '#64748b', marginBottom: '6px' }}>Add Purpose</div>
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <input value={purposeText} onChange={e => setPurposeText(e.target.value)} placeholder="e.g. HR leave management..." style={{ ...inputStyle, flex: 1 }} />
                      <button onClick={() => handleAddPurpose(app.id)} style={primaryBtn}>Add</button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          ))}
          {apps.length === 0 && <div style={{ textAlign: 'center', color: '#94a3b8', padding: '40px', fontSize: '13px' }}>No apps yet. Add one above.</div>}
        </div>
      )}

      {tab === 'deps' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div style={card}>
            <div style={cardTitle}>Add Dependency</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '10px', marginBottom: '10px' }}>
              <select value={newDep.source_app_id} onChange={e => setNewDep(p => ({ ...p, source_app_id: e.target.value }))} style={inputStyle}>
                <option value="">Source app *</option>
                {apps.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
              </select>
              <select value={newDep.dependent_app_id} onChange={e => setNewDep(p => ({ ...p, dependent_app_id: e.target.value }))} style={inputStyle}>
                <option value="">Depends on *</option>
                {apps.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
              </select>
              <select value={newDep.dependency_nature} onChange={e => setNewDep(p => ({ ...p, dependency_nature: e.target.value }))} style={inputStyle}>
                {DEP_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            <button onClick={handleCreateDep} style={primaryBtn}>+ Add Dependency</button>
          </div>
          {deps.map(d => (
            <div key={d.id} style={{ ...card, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ fontSize: '13px' }}>
                <strong>{appMap[d.source_app_id] ?? `App #${d.source_app_id}`}</strong>
                <span style={{ color: '#64748b', margin: '0 8px' }}>→ [{d.dependency_nature}] →</span>
                <strong>{appMap[d.dependent_app_id] ?? `App #${d.dependent_app_id}`}</strong>
              </div>
              <button onClick={() => handleDeleteDep(d.id)} style={dangerBtn}>Remove</button>
            </div>
          ))}
          {deps.length === 0 && <div style={{ textAlign: 'center', color: '#94a3b8', padding: '40px', fontSize: '13px' }}>No dependencies yet.</div>}
        </div>
      )}
    </div>
  );
}

const card = { background: '#fff', border: '0.5px solid #e2e8f0', borderRadius: '12px', padding: '16px 20px' };
const cardTitle = { fontWeight: 500, fontSize: '13px', marginBottom: '12px' };
const inputStyle = { padding: '8px 10px', fontSize: '13px', border: '0.5px solid #cbd5e1', borderRadius: '8px', outline: 'none', fontFamily: 'inherit', color: '#1a1a2e', width: '100%' };
const primaryBtn = { background: '#185FA5', color: '#fff', border: 'none', borderRadius: '8px', padding: '8px 16px', fontSize: '13px', cursor: 'pointer' };
const secondaryBtn = { background: '#fff', color: '#185FA5', border: '0.5px solid #185FA5', borderRadius: '8px', padding: '6px 12px', fontSize: '12px', cursor: 'pointer' };
const dangerBtn = { background: '#fff', color: '#A32D2D', border: '0.5px solid #F09595', borderRadius: '8px', padding: '6px 12px', fontSize: '12px', cursor: 'pointer' };

export default Registry;
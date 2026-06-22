import { useEffect, useState } from 'react';
import { getAllApps, createApp, deleteApp, getAllDeps, createDep, deleteDep, addPurpose, addSymptom, seedDatabase } from '../api/registry.api';
import toast from 'react-hot-toast';

const DEP_TYPES = ['auth', 'data', 'network', 'other'];

const DEP_TYPE_PILL = {
  auth:    'bg-primary-fixed text-on-primary-fixed-variant',
  data:    'bg-secondary-container text-on-secondary-container',
  network: 'bg-tertiary-fixed text-on-tertiary-fixed-variant',
  other:   'bg-surface-container text-on-surface-variant',
};

function Registry() {
  const [apps,         setApps]         = useState([]);
  const [deps,         setDeps]         = useState([]);
  const [loading,      setLoading]      = useState(true);
  const [error,        setError]        = useState(null);
  const [tab,          setTab]          = useState('apps');
  const [newApp,       setNewApp]       = useState({ name: '', description: '', owning_team: '', contact: '' });
  const [newDep,       setNewDep]       = useState({ from_app_id: '', to_app_id: '', dep_type: 'auth', nature: '' });
  const [expandedApp,  setExpandedApp]  = useState(null);
  const [symptomText,  setSymptomText]  = useState('');
  const [purposeText,  setPurposeText]  = useState('');
  const [showAddModal, setShowAddModal] = useState(false);
  const [searchText,   setSearchText]   = useState('');

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
    try {
      await createApp({ ...newApp });
      toast.success('App added!');
      setNewApp({ name: '', description: '', owning_team: '', contact: '' });
      setShowAddModal(false);
      load();
    } catch (e) { toast.error(e.response?.data?.detail || 'Create failed'); }
  }

  async function handleDeleteApp(id) {
    if (!confirm('Delete this app?')) return;
    try { await deleteApp(id); toast.success('Deleted'); load(); }
    catch { toast.error('Delete failed'); }
  }

  async function handleCreateDep() {
    if (!newDep.from_app_id || !newDep.to_app_id) { toast.error('Both apps required'); return; }
    try {
      await createDep({ ...newDep, from_app_id: +newDep.from_app_id, to_app_id: +newDep.to_app_id });
      toast.success('Dependency added!');
      setNewDep({ from_app_id: '', to_app_id: '', dep_type: 'auth', nature: '' });
      load();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
  }

  async function handleDeleteDep(id) {
    try { await deleteDep(id); toast.success('Removed'); load(); }
    catch { toast.error('Delete failed'); }
  }

  async function handleAddSymptom(appId) {
    if (!symptomText.trim()) return;
    try { await addSymptom(appId, { description: symptomText.trim() }); toast.success('Symptom added'); setSymptomText(''); load(); }
    catch { toast.error('Failed'); }
  }

  async function handleAddPurpose(appId) {
    if (!purposeText.trim()) return;
    try { await addPurpose(appId, { description: purposeText.trim() }); toast.success('Purpose added'); setPurposeText(''); load(); }
    catch { toast.error('Failed'); }
  }

  async function handleSeed() {
    if (!confirm('Seed database with sample data?')) return;
    try { await seedDatabase(); toast.success('Database seeded!'); load(); }
    catch { toast.error('Seed failed'); }
  }

  const filteredApps = apps.filter(a =>
    !searchText || a.name?.toLowerCase().includes(searchText.toLowerCase()) ||
    a.owning_team?.toLowerCase().includes(searchText.toLowerCase())
  );

  if (error) return (
    <div className="bg-error-container text-on-error-container rounded-xl p-6 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <span className="material-symbols-outlined">error</span>
        <span>{error}</span>
      </div>
      <button onClick={load} className="font-label-md bg-surface px-4 py-2 rounded-lg hover:bg-surface-container transition-colors text-on-surface">Retry</button>
    </div>
  );

  return (
    <div className="space-y-section-gap">
      {/* Stats Banner */}
      <section className="grid grid-cols-2 md:grid-cols-4 gap-gutter">
        {[
          { label: 'Total Applications', value: loading ? '—' : apps.length, color: 'text-primary' },
          { label: 'Registered Teams', value: loading ? '—' : new Set(apps.map(a => a.owning_team).filter(Boolean)).size, color: 'text-primary' },
          { label: 'Dependencies', value: loading ? '—' : deps.length, color: 'text-secondary' },
          { label: 'Auth Dependencies', value: loading ? '—' : deps.filter(d => d.dep_type === 'auth').length, color: 'text-tertiary' },
        ].map(stat => (
          <div key={stat.label} className="bg-surface-container-lowest p-4 rounded-xl border border-outline-variant flex flex-col justify-between shadow-sm">
            <span className="text-on-surface-variant font-label-sm">{stat.label}</span>
            <span className={`text-headline-lg font-headline-lg ${stat.color} mt-2`}>{stat.value}</span>
          </div>
        ))}
      </section>

      {/* Tabs */}
      <div className="flex items-center justify-between border-b border-outline-variant pb-0">
        <div className="flex gap-0">
          {[
            { key: 'apps', label: `Applications (${apps.length})`, icon: 'apps' },
            { key: 'deps', label: `Dependencies (${deps.length})`, icon: 'account_tree' },
          ].map(t => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`flex items-center gap-2 px-5 py-3 font-body-md border-b-2 transition-colors ${
                tab === t.key
                  ? 'border-primary text-primary font-semibold'
                  : 'border-transparent text-on-surface-variant hover:text-on-surface'
              }`}
            >
              <span className="material-symbols-outlined text-[18px]">{t.icon}</span>
              {t.label}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-3 pb-3">
          <button
            onClick={handleSeed}
            className="flex items-center gap-2 px-3 py-1.5 font-label-md text-on-surface-variant bg-surface-container border border-outline-variant rounded-lg hover:bg-surface-container-high transition-colors"
          >
            <span className="material-symbols-outlined text-[16px]">database</span>
            Seed DB
          </button>
          <button
            onClick={() => setShowAddModal(true)}
            className="flex items-center gap-2 px-4 py-1.5 font-label-md text-on-primary bg-primary rounded-lg hover:opacity-90 transition-opacity shadow-sm"
          >
            <span className="material-symbols-outlined text-[18px]">add</span>
            Add Application
          </button>
        </div>
      </div>

      {/* Apps Tab */}
      {tab === 'apps' && (
        <section>
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-headline-md text-on-surface">Registered Applications</h2>
            <div className="relative">
              <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant text-[18px]">search</span>
              <input
                className="pl-10 pr-4 py-1.5 bg-surface-container text-body-sm border border-outline-variant rounded-lg focus:ring-1 focus:ring-primary outline-none w-64 transition-all"
                placeholder="Filter registry..."
                value={searchText}
                onChange={e => setSearchText(e.target.value)}
              />
            </div>
          </div>

          {loading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-gutter">
              {[1,2,3].map(i => (
                <div key={i} className="bg-surface-container-lowest rounded-xl border border-outline-variant p-5 space-y-3">
                  <div className="h-4 loading-shimmer rounded w-2/3"></div>
                  <div className="h-3 loading-shimmer rounded w-full"></div>
                  <div className="h-3 loading-shimmer rounded w-1/2"></div>
                </div>
              ))}
            </div>
          ) : filteredApps.length === 0 ? (
            <div className="bg-surface-container-lowest border border-outline-variant rounded-xl py-16 flex flex-col items-center gap-3 text-on-surface-variant">
              <span className="material-symbols-outlined text-5xl text-outline-variant">apps</span>
              <p className="font-body-md">No applications yet. Add one or click "Seed DB".</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-gutter">
              {filteredApps.map(app => (
                <div
                  key={app.id}
                  className="bg-surface-container-lowest p-5 rounded-xl border border-outline-variant flex flex-col hover:shadow-md hover:-translate-y-0.5 transition-all duration-200"
                >
                  <div className="flex justify-between items-start mb-4">
                    <div className="p-2 bg-primary-fixed text-on-primary-fixed-variant rounded-lg">
                      <span className="material-symbols-outlined">hub</span>
                    </div>
                    {app.owning_team && (
                      <span className="bg-secondary-container text-on-secondary-container px-2 py-1 rounded text-label-sm">
                        {app.owning_team}
                      </span>
                    )}
                  </div>
                  <h3 className="font-headline-sm text-on-surface mb-1">{app.name}</h3>
                  {app.description && (
                    <p className="text-body-sm text-on-surface-variant line-clamp-2 mb-4">{app.description}</p>
                  )}
                  <div className="mt-auto space-y-2">
                    {app.owning_team && (
                      <div className="flex items-center gap-2 text-body-sm">
                        <span className="material-symbols-outlined text-[16px] text-outline">groups</span>
                        <span className="font-medium">{app.owning_team}</span>
                      </div>
                    )}
                    {app.contact && (
                      <div className="flex items-center gap-2 text-body-sm">
                        <span className="material-symbols-outlined text-[16px] text-outline">mail</span>
                        <span className="text-on-surface-variant">{app.contact}</span>
                      </div>
                    )}
                  </div>
                  <div className="mt-4 pt-4 border-t border-outline-variant flex items-center justify-between">
                    <button
                      onClick={() => setExpandedApp(expandedApp === app.id ? null : app.id)}
                      className="text-primary font-label-md flex items-center gap-1 hover:underline group"
                    >
                      {expandedApp === app.id ? 'Close Details' : 'Manage Details'}
                      <span className="material-symbols-outlined text-[16px] group-hover:translate-x-0.5 transition-transform">
                        {expandedApp === app.id ? 'expand_less' : 'arrow_forward'}
                      </span>
                    </button>
                    <button
                      onClick={() => handleDeleteApp(app.id)}
                      className="text-error font-label-md hover:underline flex items-center gap-1"
                    >
                      <span className="material-symbols-outlined text-[16px]">delete</span>
                    </button>
                  </div>

                  {expandedApp === app.id && (
                    <div className="mt-4 pt-4 border-t border-outline-variant space-y-3">
                      <div>
                        <label className="font-label-sm text-on-surface-variant block mb-1">Add Symptom</label>
                        <div className="flex gap-2">
                          <input
                            value={symptomText}
                            onChange={e => setSymptomText(e.target.value)}
                            placeholder="e.g. login page not loading..."
                            className="flex-1 bg-surface-container border border-outline-variant rounded-lg px-3 py-1.5 font-body-sm outline-none focus:ring-1 focus:ring-primary"
                          />
                          <button
                            onClick={() => handleAddSymptom(app.id)}
                            className="bg-primary text-on-primary px-3 py-1.5 rounded-lg font-label-md hover:opacity-90 transition-opacity"
                          >
                            Add
                          </button>
                        </div>
                      </div>
                      <div>
                        <label className="font-label-sm text-on-surface-variant block mb-1">Add Purpose</label>
                        <div className="flex gap-2">
                          <input
                            value={purposeText}
                            onChange={e => setPurposeText(e.target.value)}
                            placeholder="e.g. HR leave management..."
                            className="flex-1 bg-surface-container border border-outline-variant rounded-lg px-3 py-1.5 font-body-sm outline-none focus:ring-1 focus:ring-primary"
                          />
                          <button
                            onClick={() => handleAddPurpose(app.id)}
                            className="bg-primary text-on-primary px-3 py-1.5 rounded-lg font-label-md hover:opacity-90 transition-opacity"
                          >
                            Add
                          </button>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {/* Dependencies Tab */}
      {tab === 'deps' && (
        <section className="space-y-section-gap">
          {/* Add Dependency Form */}
          <div className="bg-surface-container-low p-margin-desktop rounded-2xl border border-outline-variant">
            <div className="flex items-center gap-3 mb-4">
              <span className="material-symbols-outlined text-primary">add_link</span>
              <h2 className="font-headline-md text-on-surface">Add Dependency</h2>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="space-y-1">
                <label className="font-label-sm text-on-surface-variant block">From App *</label>
                <select value={newDep.from_app_id} onChange={e => setNewDep(p => ({ ...p, from_app_id: e.target.value }))}
                  className="w-full bg-surface-container border border-outline-variant rounded-lg px-3 py-2 font-body-md focus:ring-1 focus:ring-primary outline-none">
                  <option value="">Select app...</option>
                  {apps.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
                </select>
              </div>
              <div className="space-y-1">
                <label className="font-label-sm text-on-surface-variant block">Depends On *</label>
                <select value={newDep.to_app_id} onChange={e => setNewDep(p => ({ ...p, to_app_id: e.target.value }))}
                  className="w-full bg-surface-container border border-outline-variant rounded-lg px-3 py-2 font-body-md focus:ring-1 focus:ring-primary outline-none">
                  <option value="">Select app...</option>
                  {apps.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
                </select>
              </div>
              <div className="space-y-1">
                <label className="font-label-sm text-on-surface-variant block">Dependency Type</label>
                <select value={newDep.dep_type} onChange={e => setNewDep(p => ({ ...p, dep_type: e.target.value }))}
                  className="w-full bg-surface-container border border-outline-variant rounded-lg px-3 py-2 font-body-md focus:ring-1 focus:ring-primary outline-none">
                  {DEP_TYPES.map(t => <option key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</option>)}
                </select>
              </div>
              <div className="space-y-1">
                <label className="font-label-sm text-on-surface-variant block">Nature</label>
                <input placeholder="e.g. SSO token validation" value={newDep.nature} onChange={e => setNewDep(p => ({ ...p, nature: e.target.value }))}
                  className="w-full bg-surface-container border border-outline-variant rounded-lg px-3 py-2 font-body-md focus:ring-1 focus:ring-primary outline-none" />
              </div>
            </div>
            <div className="mt-4 flex justify-end">
              <button onClick={handleCreateDep}
                className="flex items-center gap-2 bg-primary text-on-primary px-5 py-2 rounded-lg font-label-md shadow-sm hover:opacity-90 transition-opacity">
                <span className="material-symbols-outlined text-[18px]">add</span>
                Add Dependency
              </button>
            </div>
          </div>

          {/* Dependencies List */}
          <div>
            <div className="flex items-center gap-3 mb-4">
              <span className="material-symbols-outlined text-primary">account_tree</span>
              <h2 className="font-headline-md text-on-surface">Dependency Map</h2>
            </div>
            {loading ? (
              <div className="space-y-3">
                {[1,2,3].map(i => <div key={i} className="h-16 loading-shimmer rounded-xl"></div>)}
              </div>
            ) : deps.length === 0 ? (
              <div className="bg-surface-container-lowest border border-outline-variant rounded-xl py-12 flex flex-col items-center gap-3 text-on-surface-variant">
                <span className="material-symbols-outlined text-5xl text-outline-variant">account_tree</span>
                <p className="font-body-md">No dependencies yet.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {deps.map(d => (
                  <div key={d.id} className="bg-surface-container-lowest p-4 rounded-xl border border-outline-variant flex flex-wrap items-center gap-4 hover:border-primary/30 transition-colors">
                    <div className="flex items-center gap-3 min-w-[180px]">
                      <div className="w-8 h-8 rounded bg-surface-container flex items-center justify-center">
                        <span className="material-symbols-outlined text-[18px]">hub</span>
                      </div>
                      <span className="font-headline-sm">{d.from_app_name ?? d.from_app_id}</span>
                    </div>

                    <div className="flex-1 flex items-center justify-center min-w-[100px]">
                      <div className="h-px bg-outline flex-1"></div>
                      <span className="font-mono-sm text-outline-variant uppercase tracking-widest text-[10px] mx-3">depends on</span>
                      <div className="h-px bg-outline flex-1"></div>
                    </div>

                    <div className="flex items-center gap-3 min-w-[180px] justify-end">
                      <span className="font-headline-sm">{d.to_app_name ?? d.to_app_id}</span>
                      <div className="w-8 h-8 rounded bg-surface-container flex items-center justify-center">
                        <span className="material-symbols-outlined text-[18px]">settings</span>
                      </div>
                    </div>

                    <div className="flex items-center gap-3 ml-auto">
                      <span className={`px-3 py-1 rounded-full text-label-sm font-semibold border ${DEP_TYPE_PILL[d.dep_type] || 'bg-surface-container text-on-surface-variant'}`}>
                        {d.dep_type?.charAt(0).toUpperCase() + d.dep_type?.slice(1)}
                      </span>
                      {d.nature && <span className="font-body-sm text-on-surface-variant">{d.nature}</span>}
                      <button onClick={() => handleDeleteDep(d.id)} className="text-error hover:bg-error-container p-1 rounded-full transition-colors">
                        <span className="material-symbols-outlined text-[18px]">delete</span>
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>
      )}

      {/* Add App Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-inverse-surface/40 backdrop-blur-sm" onClick={() => setShowAddModal(false)}></div>
          <div className="relative bg-surface rounded-2xl shadow-2xl w-full max-w-2xl overflow-hidden border border-outline-variant animate-in fade-in zoom-in duration-200">
            <div className="px-6 py-4 border-b border-outline-variant flex items-center justify-between bg-surface-container-low">
              <h2 className="font-headline-md text-on-surface">Add New Application</h2>
              <button className="material-symbols-outlined text-on-surface-variant hover:text-error transition-colors p-1" onClick={() => setShowAddModal(false)}>close</button>
            </div>
            <div className="p-6 space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-1">
                  <label className="font-label-sm text-on-surface-variant block">Application Name *</label>
                  <input className="w-full bg-surface-container text-body-md border border-outline-variant rounded-lg p-2.5 focus:ring-2 focus:ring-primary focus:border-transparent outline-none"
                    placeholder="e.g. Employee Portal"
                    value={newApp.name} onChange={e => setNewApp(p => ({ ...p, name: e.target.value }))} />
                </div>
                <div className="space-y-1">
                  <label className="font-label-sm text-on-surface-variant block">Owning Team</label>
                  <input className="w-full bg-surface-container text-body-md border border-outline-variant rounded-lg p-2.5 focus:ring-2 focus:ring-primary focus:border-transparent outline-none"
                    placeholder="e.g. Infrastructure Squad"
                    value={newApp.owning_team} onChange={e => setNewApp(p => ({ ...p, owning_team: e.target.value }))} />
                </div>
              </div>
              <div className="space-y-1">
                <label className="font-label-sm text-on-surface-variant block">Contact Email</label>
                <input className="w-full bg-surface-container text-body-md border border-outline-variant rounded-lg p-2.5 focus:ring-2 focus:ring-primary focus:border-transparent outline-none"
                  placeholder="support-team@corp.com" type="email"
                  value={newApp.contact} onChange={e => setNewApp(p => ({ ...p, contact: e.target.value }))} />
              </div>
              <div className="space-y-1">
                <label className="font-label-sm text-on-surface-variant block">Description</label>
                <textarea className="w-full bg-surface-container text-body-md border border-outline-variant rounded-lg p-2.5 focus:ring-2 focus:ring-primary focus:border-transparent outline-none resize-none"
                  placeholder="Briefly describe the purpose of this application..." rows="3"
                  value={newApp.description} onChange={e => setNewApp(p => ({ ...p, description: e.target.value }))} />
              </div>
              <div className="pt-4 flex justify-end gap-3">
                <button className="px-6 py-2 rounded-lg font-label-md text-on-surface-variant hover:bg-surface-container-high transition-colors"
                  onClick={() => setShowAddModal(false)} type="button">Cancel</button>
                <button className="px-6 py-2 bg-primary text-on-primary rounded-lg font-label-md shadow-sm hover:opacity-90 transition-opacity"
                  onClick={handleCreateApp}>Register Application</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default Registry;
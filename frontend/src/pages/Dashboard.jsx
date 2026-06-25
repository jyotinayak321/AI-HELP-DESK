import { useEffect, useState } from 'react';
import { listTickets } from '../api/tickets.api';
import { getAllApps } from '../api/registry.api';
import StatCard from '../components/ui/StatCard';
import Badge from '../components/ui/Badge';
import LoadingSpinner from '../components/ui/LoadingSpinner';
import ErrorMessage from '../components/ui/ErrorMessage';
import { STATUS_COLOR, SEVERITY_COLOR } from '../constants/enums';
import { useCurrentUser } from '../useCurrentUser';

function detectOutages(tickets) {
  const appCount = {};
  const ONE_HOUR = 60 * 60 * 1000;
  const now = Date.now();
  tickets.forEach(t => {
    if (t.status === 'open') {
      const age = now - new Date(t.created_at).getTime();
      if (age <= ONE_HOUR) {
        const appName = t.primary_application_name || 'Unknown';
        appCount[appName] = (appCount[appName] || 0) + 1;
      }
    }
  });
  return Object.entries(appCount)
    .filter(([, count]) => count >= 3)
    .map(([app, count]) => ({ app, count }));
}

function Dashboard() {
  const { role } = useCurrentUser();
  const [tickets,  setTickets]  = useState([]);
  const [appCount, setAppCount] = useState(null);
  const [loading,  setLoading]  = useState(true);
  const [error,    setError]    = useState(null);

  async function load() {
    setLoading(true); setError(null);
    try {
      const [ticketRes, appRes] = await Promise.all([
        listTickets({ limit: 100 }),
        getAllApps(),
      ]);
      setTickets(ticketRes.data?.tickets ?? ticketRes.data ?? []);
      setAppCount(appRes.data?.length ?? 0);
    } catch (e) {
      setError(e.message || 'Failed to load dashboard');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  if (loading) return <LoadingSpinner text="Loading dashboard..." />;
  if (error)   return <ErrorMessage message={error} onRetry={load} />;

  const total         = tickets.length;
  const openCount     = tickets.filter(t => t.status === 'open').length;
  const triageCount   = tickets.filter(t => t.status === 'triage').length;
  const outages       = detectOutages(tickets);
  const recent        = tickets.slice(0, 6);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2 style={{ fontSize: '24px', fontWeight: 700, color: '#1e293b', marginBottom: '4px' }}>Dashboard</h2>
          <div style={{ fontSize: '13px', color: '#64748b' }}>
            System overview and active operations 
            {role && <span style={{ marginLeft: '8px', padding: '2px 6px', background: '#e2e8f0', borderRadius: '4px', fontSize: '11px', textTransform: 'uppercase', fontWeight: 600 }}>{role}</span>}
          </div>
        </div>
      </div>

      {outages.length > 0 && (
        <div style={{
          background: '#FCEBEB', border: '0.5px solid #F09595',
          borderRadius: '10px', padding: '12px 16px',
        }}>
          <div style={{ fontWeight: 500, fontSize: '13px', color: '#A32D2D', marginBottom: '6px' }}>
            ⚠ Possible Mass Outage Detected
          </div>
          {outages.map(({ app, count }) => (
            <div key={app} style={{ fontSize: '12px', color: '#791F1F' }}>
              {count} open tickets on <strong>{app}</strong> in the last hour
            </div>
          ))}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: '12px' }}>
        <StatCard label="Total Tickets"   value={total}       sub="All time"        dotColor="#185FA5" />
        <StatCard label="Open"            value={openCount}   sub="Awaiting action" dotColor="#EF9F27" />
        <StatCard label="Needs Triage"    value={triageCount} sub="Unclassified"    dotColor="#e24b4a" />
        <StatCard label="Registered Apps" value={appCount}    sub="In registry"     dotColor="#534AB7" />
      </div>

      <div style={{
        background: '#fff', border: '0.5px solid #e2e8f0',
        borderRadius: '12px', padding: '16px',
      }}>
        <div style={{ fontWeight: 500, fontSize: '14px', marginBottom: '14px' }}>Recent Tickets</div>
        {recent.length === 0 ? (
          <div style={{ color: '#94a3b8', fontSize: '13px', padding: '20px 0', textAlign: 'center' }}>
            No tickets yet. Submit a complaint to get started.
          </div>
        ) : (
          recent.map(t => (
            <div key={t.ticket_number} style={{
              display: 'flex', alignItems: 'center', gap: '12px',
              padding: '10px 0', borderBottom: '0.5px solid #f1f5f9',
            }}>
              <span style={{
                width: '8px', height: '8px', borderRadius: '50%', flexShrink: 0,
                background: STATUS_COLOR[t.status] || '#888',
              }} />
              <span style={{ fontSize: '11px', color: '#94a3b8', fontFamily: 'monospace', minWidth: '90px' }}>
                {t.ticket_number}
              </span>
              <span style={{ flex: 1, fontSize: '13px' }}>
                {t.original_complaint_text?.slice(0, 60)}{t.original_complaint_text?.length > 60 ? '…' : ''}
              </span>
              <Badge label={t.severity} color={SEVERITY_COLOR[t.severity]} bg={(SEVERITY_COLOR[t.severity] || '#888') + '22'} />
              <Badge label={t.status}   color={STATUS_COLOR[t.status]}    bg={(STATUS_COLOR[t.status] || '#888') + '22'} />
            </div>
          ))
        )}
      </div>
    </div>
  );
}
export default Dashboard;
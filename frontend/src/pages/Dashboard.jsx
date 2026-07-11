import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
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
  const navigate = useNavigate();
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
  if (error)   return <ErrorMessage message={error} />;

  const open     = tickets.filter(t => t.status === 'open').length;
  const needsTriage = tickets.filter(t => !t.fault_type).length;
  const outages  = detectOutages(tickets);
  const recent   = tickets.slice(0, 8);

  return (
    <div>
      {/* Header — NO h1, topbar handles title */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 20 }}>
        <button className="btn btn-primary" onClick={() => navigate('/submit')}>
          + New Ticket
        </button>
      </div>

      {/* Stat Cards */}
      <div className="grid-4" style={{ marginBottom: 20 }}>
        <div style={{ background:'var(--surface-1)', border:'1px solid var(--border)', borderRadius:'var(--radius-lg)', padding:'18px 20px', boxShadow:'var(--shadow-card)', position:'relative', overflow:'hidden' }}>
          <div style={{ position:'absolute', top:0, left:0, right:0, height:2, background:'var(--accent)', opacity:0.6 }}></div>
          <div style={{ position:'absolute', top:14, right:16, fontSize:20, opacity:0.12 }}>📋</div>
          <div style={{ fontSize:'2rem', fontWeight:700, color:'var(--text-primary)', lineHeight:1.1 }}>{tickets.length}</div>
          <div style={{ fontSize:'0.68rem', color:'var(--text-muted)', textTransform:'uppercase', letterSpacing:'0.08em', marginTop:6 }}>Total Tickets</div>
        </div>
        <div style={{ background:'var(--surface-1)', border:'1px solid var(--border)', borderRadius:'var(--radius-lg)', padding:'18px 20px', boxShadow:'var(--shadow-card)', position:'relative', overflow:'hidden' }}>
          <div style={{ position:'absolute', top:0, left:0, right:0, height:2, background:'var(--success)', opacity:0.6 }}></div>
          <div style={{ position:'absolute', top:14, right:16, fontSize:20, opacity:0.12 }}>🟢</div>
          <div style={{ fontSize:'2rem', fontWeight:700, color:'var(--success)', lineHeight:1.1 }}>{open}</div>
          <div style={{ fontSize:'0.68rem', color:'var(--text-muted)', textTransform:'uppercase', letterSpacing:'0.08em', marginTop:6 }}>Open</div>
        </div>
        <div style={{ background:'var(--surface-1)', border:'1px solid var(--border)', borderRadius:'var(--radius-lg)', padding:'18px 20px', boxShadow:'var(--shadow-card)', position:'relative', overflow:'hidden' }}>
          <div style={{ position:'absolute', top:0, left:0, right:0, height:2, background:'var(--warning)', opacity:0.6 }}></div>
          <div style={{ position:'absolute', top:14, right:16, fontSize:20, opacity:0.12 }}>🟡</div>
          <div style={{ fontSize:'2rem', fontWeight:700, color:'var(--warning)', lineHeight:1.1 }}>{needsTriage}</div>
          <div style={{ fontSize:'0.68rem', color:'var(--text-muted)', textTransform:'uppercase', letterSpacing:'0.08em', marginTop:6 }}>Needs Triage</div>
        </div>
        <div style={{ background:'var(--surface-1)', border:'1px solid var(--border)', borderRadius:'var(--radius-lg)', padding:'18px 20px', boxShadow:'var(--shadow-card)', position:'relative', overflow:'hidden' }}>
          <div style={{ position:'absolute', top:0, left:0, right:0, height:2, background:'var(--info)', opacity:0.6 }}></div>
          <div style={{ position:'absolute', top:14, right:16, fontSize:20, opacity:0.12 }}>📱</div>
          <div style={{ fontSize:'2rem', fontWeight:700, color:'var(--info)', lineHeight:1.1 }}>{appCount ?? '—'}</div>
          <div style={{ fontSize:'0.68rem', color:'var(--text-muted)', textTransform:'uppercase', letterSpacing:'0.08em', marginTop:6 }}>Registered Apps</div>
        </div>
      </div>

      {/* Outage Alert */}
      {outages.length > 0 && (
        <div className="alert alert-error" style={{ marginBottom: 20 }}>
          <span>🔴</span>
          <div>
            <strong>Possible Outage Detected:</strong>{' '}
            {outages.map(o => `${o.app} (${o.count} tickets)`).join(', ')}
          </div>
        </div>
      )}

      {/* Recent Tickets */}
      <div style={{ background:'var(--surface-1)', border:'1px solid var(--border)', borderRadius:'var(--radius-lg)', boxShadow:'var(--shadow-card)', overflow:'hidden', marginBottom: 20 }}>
        <div style={{ padding:'14px 18px', borderBottom:'1px solid var(--border-light)', display:'flex', alignItems:'center', justifyContent:'space-between' }}>
          <h3>Recent Tickets</h3>
          <button className="btn btn-ghost btn-sm" onClick={() => navigate('/tickets')}>View All →</button>
        </div>
        <div style={{ overflowX:'auto' }}>
          <table style={{ width:'100%', borderCollapse:'collapse', fontSize:'0.82rem' }}>
            <thead>
              <tr style={{ background:'var(--surface-2)', borderBottom:'1px solid var(--border)' }}>
                {['Ticket ID','Service No','Description','Category','Severity','Status'].map(h => (
                  <th key={h} style={{ padding:'10px 16px', textAlign:'left', fontSize:'0.66rem', fontWeight:700, color:'var(--text-muted)', textTransform:'uppercase', letterSpacing:'0.07em', whiteSpace:'nowrap' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {recent.length === 0 ? (
                <tr><td colSpan={6} style={{ textAlign:'center', color:'var(--text-muted)', padding:32 }}>No tickets found</td></tr>
              ) : recent.map(t => (
                <tr key={t.id}
                  onClick={() => navigate(`/tickets/${t.ticket_number || t.id}`)}
                  style={{ cursor:'pointer', borderBottom:'1px solid var(--border-light)' }}
                  onMouseEnter={e => e.currentTarget.style.background='var(--surface-2)'}
                  onMouseLeave={e => e.currentTarget.style.background='transparent'}
                >
                  <td style={{ padding:'11px 16px' }}>
                    <span style={{ fontFamily:'var(--font-mono)', fontSize:'0.76rem', color:'var(--accent)' }}>
                      {t.ticket_number || t.id?.slice(0,8)?.toUpperCase()}
                    </span>
                  </td>
                  <td style={{ padding:'11px 16px' }}>
                    <span style={{ fontFamily:'var(--font-mono)', fontSize:'0.76rem' }}>{t.complainant_service_no || '—'}</span>
                  </td>
                  <td style={{ padding:'11px 16px', maxWidth:220 }}>
                    <span style={{ display:'-webkit-box', WebkitLineClamp:1, WebkitBoxOrient:'vertical', overflow:'hidden', fontSize:'0.82rem', color:'var(--text-secondary)' }}>
                      {t.raw_text || '—'}
                    </span>
                  </td>
                  <td style={{ padding:'11px 16px', fontSize:'0.82rem', color:'var(--text-secondary)' }}>{t.fault_type || '—'}</td>
                  <td style={{ padding:'11px 16px' }}>
                    <span style={{
                      display:'inline-flex', padding:'2px 8px', borderRadius:20,
                      fontSize:'0.66rem', fontWeight:700, textTransform:'uppercase', letterSpacing:'0.05em',
                      background: t.severity==='critical' ? 'rgba(239,68,68,0.1)' : t.severity==='high' ? 'rgba(245,158,11,0.1)' : 'rgba(56,189,248,0.1)',
                      color: t.severity==='critical' ? 'var(--danger)' : t.severity==='high' ? 'var(--warning)' : 'var(--info)',
                      border: `1px solid ${t.severity==='critical' ? 'rgba(239,68,68,0.2)' : t.severity==='high' ? 'rgba(245,158,11,0.2)' : 'rgba(56,189,248,0.2)'}`,
                    }}>
                      {t.severity || 'normal'}
                    </span>
                  </td>
                  <td style={{ padding:'11px 16px' }}>
                    <span style={{
                      display:'inline-flex', padding:'2px 8px', borderRadius:20,
                      fontSize:'0.66rem', fontWeight:700, textTransform:'uppercase', letterSpacing:'0.05em',
                      background: t.status==='open' ? 'rgba(34,197,94,0.1)' : t.status==='closed' ? 'rgba(100,116,139,0.1)' : 'rgba(245,158,11,0.1)',
                      color: t.status==='open' ? 'var(--success)' : t.status==='closed' ? '#64748b' : 'var(--warning)',
                      border: `1px solid ${t.status==='open' ? 'rgba(34,197,94,0.2)' : t.status==='closed' ? 'rgba(100,116,139,0.2)' : 'rgba(245,158,11,0.2)'}`,
                    }}>
                      {t.status || 'open'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

export default Dashboard;

import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { listTickets } from '../api/tickets.api';
import { TICKET_STATUSES, STATUS_COLOR, SEVERITY_COLOR } from '../constants/enums';
import Badge from '../components/ui/Badge';
import LoadingSpinner from '../components/ui/LoadingSpinner';
import ErrorMessage from '../components/ui/ErrorMessage';
import { useCurrentUser } from '../useCurrentUser';
import { detectOutages } from '../utils/detectOutages';

function TeamQueue() {
  const navigate   = useNavigate();
  const { managedTeam } = useCurrentUser();
  const [tickets,  setTickets]  = useState([]);
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState(null);

  async function load() {
    setLoading(true); setError(null);
    try {
      const [openRes, inProgressRes] = await Promise.all([
        listTickets({ status: 'open',        limit: 100 }),
        listTickets({ status: 'in_progress', limit: 100 }),
      ]);
      const allTickets = [
        ...(openRes.data?.tickets ?? []),
        ...(inProgressRes.data?.tickets ?? []),
      ];
      allTickets.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
      setTickets(allTickets);
    } catch (e) {
      setError(e.response?.data?.detail || e.message || 'Failed to load queue');
    } finally { setLoading(false); }
  }

  useEffect(() => { load(); }, []);

  const criticalCount = tickets.filter(t => t.severity === 'critical').length;
  const highCount     = tickets.filter(t => t.severity === 'high').length;
  const outages       = detectOutages(tickets);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>

      <div style={{
        background: 'var(--surface-1)', border: '1px solid var(--border)',
        borderRadius: 'var(--radius-lg)', padding: '16px 20px',
        boxShadow: 'var(--shadow-card)'
      }}>
        <div style={{ fontSize: '15px', fontWeight: 600, marginBottom: '4px', color: 'var(--text-primary)' }}>
          📋 Queue for {managedTeam || 'Your Team'}
        </div>
        <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
          Showing active tickets (open and in progress) assigned to your department's applications.
        </div>
      </div>

      {outages.length > 0 && (
        <div className="alert alert-error">
          <span>🔴</span>
          <div>
            <strong>Possible Outage Detected:</strong>{' '}
            {outages.map(o => `${o.app} (${o.count} tickets)`).join(', ')}
            {' '}— multiple operators are reporting the same application within the last hour.
          </div>
        </div>
      )}

      {!loading && !error && (
        <div style={{ display: 'flex', gap: '12px' }}>
          {[
            { label: 'Total Active', value: tickets.length, color: 'var(--accent)',  bg: 'rgba(24,95,165,0.08)' },
            { label: 'Critical',     value: criticalCount,  color: 'var(--danger)',  bg: 'rgba(239,68,68,0.08)' },
            { label: 'High',         value: highCount,      color: 'var(--warning)', bg: 'rgba(245,158,11,0.08)' },
          ].map(s => (
            <div key={s.label} style={{
              flex: 1, background: s.bg, border: `1px solid ${s.color}33`,
              borderRadius: '10px', padding: '12px 16px', textAlign: 'center',
            }}>
              <div style={{ fontSize: '22px', fontWeight: 700, color: s.color }}>{s.value}</div>
              <div style={{ fontSize: '11px', color: s.color, marginTop: '2px' }}>{s.label}</div>
            </div>
          ))}
        </div>
      )}

      {loading ? <LoadingSpinner text="Loading queue..." /> :
       error   ? <ErrorMessage message={error} onRetry={() => load()} /> :
        <div style={{
          background: 'var(--surface-1)', border: '1px solid var(--border)',
          borderRadius: 'var(--radius-lg)', overflow: 'hidden',
          boxShadow: 'var(--shadow-card)'
        }}>
          <div style={{
            display: 'grid', gridTemplateColumns: '140px 1fr 120px 110px 90px 80px',
            gap: '12px', padding: '10px 16px', background: 'var(--surface-2)',
            fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600,
            textTransform: 'uppercase', letterSpacing: '0.05em',
            borderBottom: '1px solid var(--border)'
          }}>
            <span>Ticket No.</span><span>Complaint</span><span>Application</span><span>Fault Type</span><span>Severity</span><span>Status</span>
          </div>
          {tickets.length === 0 ? (
            <div style={{ padding: '32px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '13px' }}>
              No active tickets for your application. 🎉
            </div>
          ) : tickets.map(t => (
            <div key={t.ticket_number} onClick={() => navigate(`/tickets/${t.ticket_number}`, { state: { from: '/queue' } })}
              style={{
                display: 'grid', gridTemplateColumns: '140px 1fr 120px 110px 90px 80px',
                gap: '12px', padding: '12px 16px', borderBottom: '1px solid var(--border-light)',
                cursor: 'pointer', alignItems: 'center'
              }}
              onMouseEnter={e => e.currentTarget.style.background = 'var(--surface-2)'}
              onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
              <span style={{ fontSize: '12px', fontFamily: 'var(--font-mono, monospace)', color: 'var(--accent)' }}>
                {t.ticket_number}
              </span>
              <span style={{ fontSize: '13px', color: 'var(--text-primary)' }}>
                {t.original_complaint_text?.slice(0, 55)}{t.original_complaint_text?.length > 55 ? '…' : ''}
              </span>
              <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                {t.primary_application_name ?? '—'}
              </span>
              <Badge label={t.fault_type?.replace(/_/g, ' ') ?? '—'} color="#534AB7" bg="#EEEDFE" />
              <Badge label={t.severity ?? '—'} color={SEVERITY_COLOR[t.severity]} bg={(SEVERITY_COLOR[t.severity] || '#888') + '22'} />
              <Badge label={t.status ?? '—'} color={STATUS_COLOR[t.status]} bg={(STATUS_COLOR[t.status] || '#888') + '22'} />
            </div>
          ))}
        </div>
      }
    </div>
  );
}

export default TeamQueue;
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { listTickets } from '../api/tickets.api';
import { TICKET_STATUSES, STATUS_COLOR, SEVERITY_COLOR } from '../constants/enums';
import Badge from '../components/ui/Badge';
import LoadingSpinner from '../components/ui/LoadingSpinner';
import ErrorMessage from '../components/ui/ErrorMessage';
import { useCurrentUser } from '../useCurrentUser';

/**
 * R-16: Team Queue View
 * Shows only open/in-progress tickets filtered by the operator's owning team.
 * The operator selects their team name from a dropdown.
 */
function TeamQueue() {
  const navigate   = useNavigate();
  const { managedTeam } = useCurrentUser();
  const [tickets,  setTickets]  = useState([]);
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState(null);

  async function load() {
    setLoading(true); setError(null);
    try {
      // Filter to open + in_progress tickets. The backend enforces admin scope automatically.
      const [openRes, inProgressRes] = await Promise.all([
        listTickets({ status: 'open',        limit: 100 }),
        listTickets({ status: 'in_progress', limit: 100 }),
      ]);
      const allTickets = [
        ...(openRes.data?.tickets ?? []),
        ...(inProgressRes.data?.tickets ?? []),
      ];
      // Sort by created_at descending
      allTickets.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
      setTickets(allTickets);
    } catch (e) {
      setError(e.response?.data?.detail || e.message || 'Failed to load queue');
    } finally { setLoading(false); }
  }

  useEffect(() => {
    load();
  }, []);

  const criticalCount = tickets.filter(t => t.severity === 'critical').length;
  const highCount     = tickets.filter(t => t.severity === 'high').length;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>

      {/* Header */}
      <div style={{ background: '#fff', border: '0.5px solid #e2e8f0', borderRadius: '12px', padding: '16px 20px' }}>
        <div style={{ fontSize: '15px', fontWeight: 600, marginBottom: '4px' }}>📋 Queue for {managedTeam || 'Your Team'}</div>
        <div style={{ fontSize: '12px', color: '#64748b' }}>
          Showing active tickets (open and in progress) assigned to your department's applications.
        </div>
      </div>

      {/* Stats strip */}
      {!loading && !error && (
        <div style={{ display: 'flex', gap: '12px' }}>
          {[
            { label: 'Total Active', value: tickets.length, color: '#185FA5', bg: '#EBF4FF' },
            { label: 'Critical',     value: criticalCount,  color: '#DC2626', bg: '#FEF2F2' },
            { label: 'High',         value: highCount,      color: '#D97706', bg: '#FFFBEB' },
          ].map(s => (
            <div key={s.label} style={{
              flex: 1, background: s.bg, border: `0.5px solid ${s.color}33`,
              borderRadius: '10px', padding: '12px 16px', textAlign: 'center',
            }}>
              <div style={{ fontSize: '22px', fontWeight: 700, color: s.color }}>{s.value}</div>
              <div style={{ fontSize: '11px', color: s.color, marginTop: '2px' }}>{s.label}</div>
            </div>
          ))}
        </div>
      )}

      {/* Ticket table */}
      {loading ? <LoadingSpinner text="Queue load ho raha hai..." /> :
       error   ? <ErrorMessage message={error} onRetry={() => load()} /> :
        <div style={{ background: '#fff', border: '0.5px solid #e2e8f0', borderRadius: '12px', overflow: 'hidden' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '140px 1fr 120px 110px 90px 80px', gap: '12px', padding: '10px 16px', background: '#f8fafc', fontSize: '11px', color: '#64748b', fontWeight: 500, borderBottom: '0.5px solid #e2e8f0' }}>
            <span>Ticket No.</span><span>Complaint</span><span>Application</span><span>Fault Type</span><span>Severity</span><span>Status</span>
          </div>
          {tickets.length === 0 ? (
            <div style={{ padding: '32px', textAlign: 'center', color: '#94a3b8', fontSize: '13px' }}>
              No active tickets for your application. 🎉
            </div>
          ) : tickets.map(t => (
            <div key={t.ticket_number} onClick={() => navigate(`/tickets/${t.ticket_number}`, { state: { from: '/queue' } })}
              style={{ display: 'grid', gridTemplateColumns: '140px 1fr 120px 110px 90px 80px', gap: '12px', padding: '12px 16px', borderBottom: '0.5px solid #f1f5f9', cursor: 'pointer', alignItems: 'center' }}
              onMouseEnter={e => e.currentTarget.style.background = '#f8fafc'}
              onMouseLeave={e => e.currentTarget.style.background = ''}>
              <span style={{ fontSize: '12px', fontFamily: 'monospace', color: '#185FA5' }}>{t.ticket_number}</span>
              <span style={{ fontSize: '13px' }}>{t.original_complaint_text?.slice(0, 55)}{t.original_complaint_text?.length > 55 ? '…' : ''}</span>
              <span style={{ fontSize: '12px', color: '#475569' }}>{t.primary_application_name ?? '—'}</span>
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

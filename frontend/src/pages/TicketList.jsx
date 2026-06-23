import { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { listTickets } from '../api/tickets.api';
import { getAllApps } from '../api/registry.api';
import { TICKET_STATUSES, SEVERITY_LEVELS, STATUS_COLOR, SEVERITY_COLOR } from '../constants/enums';
import Badge from '../components/ui/Badge';
import LoadingSpinner from '../components/ui/LoadingSpinner';
import ErrorMessage from '../components/ui/ErrorMessage';

function TicketList() {
  const { state } = useLocation();
  const navigate  = useNavigate();
  const [tickets, setTickets] = useState([]);
  const [apps,    setApps]    = useState([]);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState(null);
  const [filters, setFilters] = useState({ status: '', app_id: '', severity: '', date_from: '', date_to: '', search: '' });

  function handleFilter(e) {
    setFilters(prev => ({ ...prev, [e.target.name]: e.target.value }));
  }

  async function load() {
    setLoading(true); setError(null);
    try {
      const params = Object.fromEntries(Object.entries(filters).filter(([, v]) => v !== ''));
      const [ticketRes, appRes] = await Promise.all([listTickets(params), getAllApps()]);
      setTickets(ticketRes.data?.tickets ?? ticketRes.data ?? []);
      setApps(appRes.data ?? []);
    } catch (e) {
      setError(e.response?.data?.detail || e.message || 'Failed to load tickets');
    } finally { setLoading(false); }
  }

  useEffect(() => { load(); }, [filters]);

  return (
    <div>
      {state?.newTicket && (
        <div style={{ background: '#EAF3DE', border: '0.5px solid #C0DD97', borderRadius: '10px', padding: '12px 16px', fontSize: '13px', color: '#27500A', marginBottom: '16px' }}>
          ✓ Ticket created: <strong>{state.newTicket.ticket_number}</strong> — {state.newTicket.message}
          {state.newTicket.routed_to_team && ` → Routed to: ${state.newTicket.routed_to_team}`}
        </div>
      )}

      <div style={{ background: '#fff', border: '0.5px solid #e2e8f0', borderRadius: '12px', padding: '14px 16px', display: 'grid', gridTemplateColumns: 'repeat(3,1fr) repeat(2,1fr) 1fr', gap: '10px', marginBottom: '16px', alignItems: 'end' }}>
        <div>
          <label style={labelStyle}>Status</label>
          <select name="status" value={filters.status} onChange={handleFilter} style={selectStyle}>
            <option value="">All statuses</option>
            {TICKET_STATUSES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
          </select>
        </div>
        <div>
          <label style={labelStyle}>Application</label>
          <select name="app_id" value={filters.app_id} onChange={handleFilter} style={selectStyle}>
            <option value="">All apps</option>
            {apps.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
          </select>
        </div>
        <div>
          <label style={labelStyle}>Severity</label>
          <select name="severity" value={filters.severity} onChange={handleFilter} style={selectStyle}>
            <option value="">All severities</option>
            {SEVERITY_LEVELS.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
          </select>
        </div>
        <div>
          <label style={labelStyle}>From</label>
          <input type="date" name="date_from" value={filters.date_from} onChange={handleFilter} style={selectStyle} />
        </div>
        <div>
          <label style={labelStyle}>To</label>
          <input type="date" name="date_to" value={filters.date_to} onChange={handleFilter} style={selectStyle} />
        </div>
        <div>
          <label style={labelStyle}>Search</label>
          <input name="search" value={filters.search} onChange={handleFilter} placeholder="Keyword..." style={selectStyle} />
        </div>
      </div>

      {loading ? <LoadingSpinner text="Tickets load ho rahe hain..." /> :
       error   ? <ErrorMessage message={error} onRetry={load} /> : (
        <div style={{ background: '#fff', border: '0.5px solid #e2e8f0', borderRadius: '12px', overflow: 'hidden' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '140px 1fr 120px 110px 90px 80px', gap: '12px', padding: '10px 16px', background: '#f8fafc', fontSize: '11px', color: '#64748b', fontWeight: 500, borderBottom: '0.5px solid #e2e8f0' }}>
            <span>Ticket No.</span><span>Complaint</span><span>Application</span><span>Fault Type</span><span>Severity</span><span>Status</span>
          </div>
          {tickets.length === 0 ? (
            <div style={{ padding: '32px', textAlign: 'center', color: '#94a3b8', fontSize: '13px' }}>No tickets match the current filters.</div>
          ) : tickets.map(t => (
            <div key={t.ticket_number} onClick={() => navigate(`/tickets/${t.ticket_number}`)}
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
      )}
    </div>
  );
}

const labelStyle = { display: 'block', fontSize: '11px', color: '#64748b', marginBottom: '4px' };
const selectStyle = { width: '100%', padding: '7px 10px', fontSize: '12px', border: '0.5px solid #cbd5e1', borderRadius: '8px', outline: 'none', fontFamily: 'inherit', color: '#1a1a2e' };

export default TicketList;
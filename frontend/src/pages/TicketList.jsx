import { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { listTickets } from '../api/tickets.api';
import { getAllApps } from '../api/registry.api';
import { TICKET_STATUSES, SEVERITY_LEVELS, STATUS_COLOR, SEVERITY_COLOR } from '../constants/enums';

const SEVERITY_PILL = {
  critical: 'bg-error-container text-on-error-container',
  high:     'bg-tertiary-fixed text-on-tertiary-fixed',
  normal:   'bg-secondary-container text-on-secondary-container',
  low:      'bg-surface-container text-on-surface-variant',
};

const STATUS_PILL = {
  open:     'bg-tertiary-fixed text-on-tertiary-fixed',
  triage:   'bg-error-container text-on-error-container',
  assigned: 'bg-secondary-container text-on-secondary-container',
  resolved: 'bg-surface-container text-on-surface-variant',
  closed:   'bg-surface-container-high text-on-surface-variant',
  reopened: 'bg-primary-fixed text-on-primary-fixed-variant',
};

function Pill({ label, type = 'neutral' }) {
  const cls = type === 'severity' ? (SEVERITY_PILL[label?.toLowerCase()] || 'bg-surface-container text-on-surface-variant')
    : type === 'status' ? (STATUS_PILL[label?.toLowerCase()] || 'bg-surface-container text-on-surface-variant')
    : 'bg-primary-fixed text-on-primary-fixed-variant';
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded font-label-sm uppercase tracking-wider ${cls}`}>
      {label || '—'}
    </span>
  );
}

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
    <div className="space-y-gutter">
      {state?.newTicket && (
        <div className="bg-surface-container-lowest border border-outline-variant rounded-xl p-4 flex items-start gap-3 shadow-sm">
          <span className="material-symbols-outlined text-[20px] text-primary mt-0.5" style={{ fontVariationSettings: "'FILL' 1" }}>check_circle</span>
          <div>
            <p className="font-headline-sm text-on-surface">Ticket Created Successfully</p>
            <p className="font-body-sm text-on-surface-variant mt-0.5">
              <strong className="text-primary font-mono-sm">{state.newTicket.ticket_number}</strong> — {state.newTicket.message}
              {state.newTicket.routed_to && ` → Routed to: ${state.newTicket.routed_to}`}
            </p>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="bg-surface-container-lowest border border-outline-variant rounded-xl p-4 shadow-sm">
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          <div className="space-y-1">
            <label className="font-label-sm text-on-surface-variant block">Status</label>
            <div className="relative">
              <select name="status" value={filters.status} onChange={handleFilter}
                className="w-full appearance-none bg-surface-container border border-outline-variant rounded-lg py-1.5 px-3 pr-8 font-body-sm text-on-surface focus:ring-1 focus:ring-primary outline-none transition-all">
                <option value="">All statuses</option>
                {TICKET_STATUSES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
              </select>
              <span className="absolute right-2 top-1/2 -translate-y-1/2 material-symbols-outlined text-on-surface-variant pointer-events-none text-[16px]">expand_more</span>
            </div>
          </div>
          <div className="space-y-1">
            <label className="font-label-sm text-on-surface-variant block">Application</label>
            <div className="relative">
              <select name="app_id" value={filters.app_id} onChange={handleFilter}
                className="w-full appearance-none bg-surface-container border border-outline-variant rounded-lg py-1.5 px-3 pr-8 font-body-sm text-on-surface focus:ring-1 focus:ring-primary outline-none transition-all">
                <option value="">All apps</option>
                {apps.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
              </select>
              <span className="absolute right-2 top-1/2 -translate-y-1/2 material-symbols-outlined text-on-surface-variant pointer-events-none text-[16px]">expand_more</span>
            </div>
          </div>
          <div className="space-y-1">
            <label className="font-label-sm text-on-surface-variant block">Severity</label>
            <div className="relative">
              <select name="severity" value={filters.severity} onChange={handleFilter}
                className="w-full appearance-none bg-surface-container border border-outline-variant rounded-lg py-1.5 px-3 pr-8 font-body-sm text-on-surface focus:ring-1 focus:ring-primary outline-none transition-all">
                <option value="">All severities</option>
                {SEVERITY_LEVELS.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
              </select>
              <span className="absolute right-2 top-1/2 -translate-y-1/2 material-symbols-outlined text-on-surface-variant pointer-events-none text-[16px]">expand_more</span>
            </div>
          </div>
          <div className="space-y-1">
            <label className="font-label-sm text-on-surface-variant block">From</label>
            <input type="date" name="date_from" value={filters.date_from} onChange={handleFilter}
              className="w-full bg-surface-container border border-outline-variant rounded-lg py-1.5 px-3 font-body-sm text-on-surface focus:ring-1 focus:ring-primary outline-none transition-all" />
          </div>
          <div className="space-y-1">
            <label className="font-label-sm text-on-surface-variant block">To</label>
            <input type="date" name="date_to" value={filters.date_to} onChange={handleFilter}
              className="w-full bg-surface-container border border-outline-variant rounded-lg py-1.5 px-3 font-body-sm text-on-surface focus:ring-1 focus:ring-primary outline-none transition-all" />
          </div>
          <div className="space-y-1">
            <label className="font-label-sm text-on-surface-variant block">Search</label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 material-symbols-outlined text-on-surface-variant text-[16px]">search</span>
              <input name="search" value={filters.search} onChange={handleFilter} placeholder="Keyword..."
                className="w-full bg-surface-container border border-outline-variant rounded-lg py-1.5 pl-8 pr-3 font-body-sm text-on-surface focus:ring-1 focus:ring-primary outline-none transition-all" />
            </div>
          </div>
        </div>
      </div>

      {/* Tickets Table */}
      {loading ? (
        <div className="bg-surface-container-lowest border border-outline-variant rounded-xl p-12 flex flex-col items-center gap-4">
          <div className="relative w-10 h-10">
            <div className="absolute inset-0 border-4 border-primary/20 rounded-full"></div>
            <div className="absolute inset-0 border-4 border-primary rounded-full border-t-transparent animate-spin"></div>
          </div>
          <p className="font-body-sm text-on-surface-variant">Loading tickets...</p>
        </div>
      ) : error ? (
        <div className="bg-error-container text-on-error-container rounded-xl p-6 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="material-symbols-outlined">error</span>
            <span className="font-body-md">{error}</span>
          </div>
          <button onClick={load} className="font-label-md bg-surface px-4 py-2 rounded-lg hover:bg-surface-container transition-colors">Retry</button>
        </div>
      ) : (
        <div className="bg-surface-container-lowest border border-outline-variant rounded-xl overflow-hidden shadow-sm">
          {/* Header */}
          <div className="grid gap-3 px-5 py-3 bg-surface-container-low border-b border-outline-variant"
            style={{ gridTemplateColumns: '160px 1fr 130px 120px 100px 90px' }}>
            {['Ticket No.', 'Complaint', 'Application', 'Fault Type', 'Severity', 'Status'].map(h => (
              <span key={h} className="font-label-sm text-on-surface-variant uppercase tracking-wider">{h}</span>
            ))}
          </div>

          {tickets.length === 0 ? (
            <div className="py-16 flex flex-col items-center gap-3 text-on-surface-variant">
              <span className="material-symbols-outlined text-5xl text-outline-variant">confirmation_number</span>
              <p className="font-body-md">No tickets match the current filters.</p>
            </div>
          ) : tickets.map(t => (
            <div
              key={t.ticket_number}
              onClick={() => navigate(`/tickets/${t.ticket_number}`)}
              className="grid gap-3 px-5 py-3 border-b border-outline-variant/50 cursor-pointer items-center hover:bg-surface-container-low transition-colors group"
              style={{ gridTemplateColumns: '160px 1fr 130px 120px 100px 90px' }}
            >
              <span className="font-mono-sm text-primary group-hover:underline">{t.ticket_number}</span>
              <span className="font-body-sm text-on-surface">
                {t.original_complaint_text?.slice(0, 60)}{t.original_complaint_text?.length > 60 ? '…' : ''}
              </span>
              <span className="font-body-sm text-on-surface-variant">{t.primary_app_name ?? '—'}</span>
              <Pill label={t.fault_type?.replace(/_/g, ' ')} type="fault" />
              <Pill label={t.severity} type="severity" />
              <Pill label={t.status} type="status" />
            </div>
          ))}

          {tickets.length > 0 && (
            <div className="px-5 py-3 bg-surface-container-low flex items-center justify-between">
              <span className="font-label-sm text-on-surface-variant">{tickets.length} ticket{tickets.length !== 1 ? 's' : ''} found</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default TicketList;
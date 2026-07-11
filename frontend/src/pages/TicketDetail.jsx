import { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { listTickets, updateTicket, getSimilarResolutions, getTicketHistory } from '../api/tickets.api';
import { TICKET_STATUSES, SEVERITY_COLOR, STATUS_COLOR } from '../constants/enums';
import Badge from '../components/ui/Badge';
import LoadingSpinner from '../components/ui/LoadingSpinner';
import ErrorMessage from '../components/ui/ErrorMessage';
import toast from 'react-hot-toast';
import { useCurrentUser } from '../useCurrentUser';

// ─── helper ──────────────────────────────────────────────────────────────────
function fmtDate(raw) {
  if (!raw) return '—';
  return new Date(raw).toLocaleString('en-IN', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit', hour12: true,
  });
}

const CLOSED_STATUSES = ['resolved', 'closed'];

// ─── Ticket History / Resolution Panel (shown for closed tickets) ─────────────
function HistoryPanel({ history }) {
  if (!history.length) return null;

  // The final resolution entry (last closed/resolved)
  const resolution = [...history].reverse().find(
    h => CLOSED_STATUSES.includes(h.new_status) && h.notes?.trim()
  );

  return (
    <div style={{ ...card, borderColor: '#6EE7B7', background: '#ECFDF5' }}>
      <div style={{ ...cardTitle, color: '#065F46' }}>✅ Resolution & Audit Trail</div>

      {/* Final resolution note highlighted at the top */}
      {resolution && (
        <div style={{
          background: '#D1FAE5', borderRadius: '8px', padding: '12px 14px',
          marginBottom: '14px', border: '0.5px solid #6EE7B7',
        }}>
          <div style={{ fontSize: '11px', color: '#065F46', fontWeight: 600, marginBottom: '5px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Final Resolution Note
          </div>
          <div style={{ fontSize: '13px', color: '#064E3B', lineHeight: '1.7' }}>{resolution.notes}</div>
          <div style={{ fontSize: '11px', color: '#059669', marginTop: '6px' }}>
            Closed by {resolution.changed_by || 'Unknown'} · {fmtDate(resolution.changed_at)}
          </div>
        </div>
      )}

      {/* Full timeline */}
      <div style={{ fontSize: '12px', color: '#065F46', fontWeight: 500, marginBottom: '8px' }}>Full Timeline</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {history.map((h, i) => (
          <div key={h.id} style={{ display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', paddingTop: '3px' }}>
              <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: STATUS_COLOR[h.new_status] || '#94a3b8', flexShrink: 0 }} />
              {i < history.length - 1 && <div style={{ width: '1px', flex: 1, background: '#d1fae5', marginTop: '2px', minHeight: '16px' }} />}
            </div>
            <div style={{ flex: 1, paddingBottom: '8px' }}>
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
                <span style={{ fontSize: '12px', fontWeight: 500, color: '#065F46' }}>
                  {h.old_status ? `${h.old_status} → ` : ''}{h.new_status}
                </span>
                <span style={{ fontSize: '11px', color: '#6EE7B7', background: '#065F46', padding: '1px 6px', borderRadius: '4px' }}>
                  {h.changed_by || 'system'}
                </span>
                <span style={{ fontSize: '11px', color: '#64748b' }}>{fmtDate(h.changed_at)}</span>
              </div>
              {h.notes?.trim() && (
                <div style={{ fontSize: '12px', color: '#374151', marginTop: '4px', lineHeight: '1.6' }}>
                  {h.notes}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Similar Resolutions Panel (shown for open/in-progress tickets) ───────────
function SimilarResolutionsPanel({ resolutions }) {
  if (!resolutions.length) return null;

  return (
    <div style={{ ...card, borderColor: '#93C5FD', background: '#EFF6FF' }}>
      <div style={{ ...cardTitle, color: '#1E40AF' }}>💡 How was this fixed before?</div>
      <div style={{ fontSize: '12px', color: '#3B82F6', marginBottom: '12px' }}>
        The AI found past tickets with a similar complaint. Here's how they were resolved:
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {resolutions.map((r, i) => (
          <div key={i} style={{
            background: '#fff', padding: '12px 14px', borderRadius: '8px',
            border: '0.5px solid #93C5FD',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <span style={{ fontFamily: 'monospace', fontSize: '12px', color: '#185FA5', fontWeight: 500 }}>
                {r.ticket_number}
              </span>
              <span style={{
                fontSize: '11px', fontWeight: 600,
                color: r.similarity_score > 0.8 ? '#059669' : r.similarity_score > 0.65 ? '#D97706' : '#64748b',
                background: r.similarity_score > 0.8 ? '#D1FAE5' : r.similarity_score > 0.65 ? '#FEF3C7' : '#f1f5f9',
                padding: '2px 8px', borderRadius: '6px',
              }}>
                {Math.round(r.similarity_score * 100)}% match
              </span>
            </div>
            <div style={{ fontSize: '13px', color: '#1e293b', lineHeight: '1.7', fontStyle: 'italic' }}>
              "{r.notes}"
            </div>
            <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '6px' }}>
              Resolved by <strong>{r.changed_by || 'operator'}</strong> · {fmtDate(r.changed_at)}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────
function TicketDetail() {
  const { ticketNumber } = useParams();
  const navigate = useNavigate();
  const { state } = useLocation();
  const { isAdmin } = useCurrentUser();

  const [ticket,      setTicket]      = useState(null);
  const [resolutions, setResolutions] = useState([]);
  const [history,     setHistory]     = useState([]);
  const [loading,     setLoading]     = useState(true);
  const [saving,      setSaving]      = useState(false);
  const [error,       setError]       = useState(null);
  const [update,      setUpdate]      = useState({
    new_status: '', notes: '', changed_by: 'system', assignee_id: '',
  });

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const res = await listTickets({ search: ticketNumber });
      const found = (res.data?.tickets ?? res.data ?? []).find(
        t => t.ticket_number === ticketNumber
      );
      if (!found) throw new Error('Ticket not found');
      setTicket(found);
      setUpdate({
        new_status: found.status,
        notes: '',
        changed_by: 'system',
        assignee_id: found.assignee_id || '',
      });

      const isOpen = !CLOSED_STATUSES.includes(found.status);

      // Always load history (for the audit trail)
      try {
        const hRes = await getTicketHistory(ticketNumber);
        setHistory(hRes.data ?? []);
      } catch (_) { setHistory([]); }

      // Only load similar resolutions if ticket is still open/in-progress
      if (isOpen) {
        try {
          const rRes = await getSimilarResolutions(ticketNumber);
          setResolutions(rRes.data ?? []);
        } catch (_) { setResolutions([]); }
      } else {
        setResolutions([]);
      }

    } catch (e) {
      setError(e.message || 'Failed to load ticket');
    } finally { setLoading(false); }
  }, [ticketNumber]);

  useEffect(() => { load(); }, [load]);

  async function handleUpdate() {
    setSaving(true);
    try {
      await updateTicket(ticketNumber, {
        new_status:  update.new_status,
        notes:       update.notes || '',
        changed_by:  update.changed_by || 'system',
        assignee_id: update.assignee_id || null,
      });
      toast.success('Ticket updated!');
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Update failed');
    } finally { setSaving(false); }
  }

  if (loading) return <LoadingSpinner text="Ticket load ho raha hai..." />;
  if (error)   return <ErrorMessage message={error} onRetry={load} />;
  if (!ticket) return null;

  const isClosed = CLOSED_STATUSES.includes(ticket.status);

  return (
    <div style={{ maxWidth: '680px', display: 'flex', flexDirection: 'column', gap: '16px' }}>

      <button onClick={() => navigate(state?.from || '/tickets')} style={{
        background: 'none', border: 'none', color: '#185FA5',
        fontSize: '13px', cursor: 'pointer', alignSelf: 'flex-start', padding: 0,
      }}>
        ← Back to {state?.from === '/queue' ? 'Queue' : 'Tickets'}
      </button>

      {/* ── Header card ─────────────────────────────────────────────── */}
      <div style={card}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <div style={{ fontFamily: 'monospace', fontSize: '13px', color: '#64748b', marginBottom: '4px' }}>
              {ticket.ticket_number}
            </div>
            <div style={{ fontSize: '15px', fontWeight: 500 }}>
              {ticket.primary_application_name ?? 'Unclassified'}
            </div>
            {ticket.assignee_id && (
              <div style={{ fontSize: '12px', color: '#475569', marginTop: '4px' }}>
                👤 Assigned to: <strong>{ticket.assignee_id}</strong>
              </div>
            )}
          </div>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
            <Badge label={ticket.severity} color={SEVERITY_COLOR[ticket.severity]} bg={(SEVERITY_COLOR[ticket.severity] || '#888') + '22'} />
            <Badge label={ticket.status}   color={STATUS_COLOR[ticket.status]}    bg={(STATUS_COLOR[ticket.status] || '#888') + '22'} />
          </div>
        </div>
      </div>

      {/* ── Complaint card ──────────────────────────────────────────── */}
      <div style={card}>
        <div style={cardTitle}>Complaint</div>
        <div style={{ fontSize: '13px', lineHeight: '1.7', background: '#f8fafc', borderRadius: '8px', padding: '12px' }}>
          {ticket.original_complaint_text ?? 'No complaint text available.'}
        </div>
        <div style={{ fontSize: '12px', color: '#64748b', marginTop: '10px', display: 'flex', gap: '20px', flexWrap: 'wrap' }}>
          <span>Service No: <strong>{ticket.complainant_service_no}</strong></span>
          {ticket.complainant_rank && <span>Rank: <strong>{ticket.complainant_rank}</strong></span>}
          {ticket.complainant_unit && <span>Unit: <strong>{ticket.complainant_unit}</strong></span>}
          <span>Fault: <strong>{ticket.fault_type?.replace(/_/g, ' ')}</strong></span>
        </div>
      </div>

      {/* ── Impacted Infrastructure ─────────────────────────────────── */}
      {ticket.dependencies?.length > 0 && (
        <div style={{ ...card, borderColor: '#F09595', background: '#FCEBEB' }}>
          <div style={{ ...cardTitle, color: '#A32D2D' }}>⚠ Impacted Infrastructure</div>
          <div style={{ fontSize: '13px', color: '#791F1F', marginBottom: '10px' }}>
            The following underlying services may be experiencing a cascaded failure:
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {ticket.dependencies.map(dep => (
              <div key={dep.application_id} style={{
                background: '#fff', padding: '10px 12px', borderRadius: '6px',
                border: '0.5px solid #F09595', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              }}>
                <strong style={{ color: '#A32D2D', fontSize: '13px' }}>{dep.application_name}</strong>
                <span style={{ fontSize: '11px', color: '#A32D2D', background: '#FCEBEB', padding: '2px 6px', borderRadius: '4px' }}>
                  Nature: {dep.dependency_nature?.replace(/_/g, ' ')}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Adaptive middle panels ───────────────────────────────────── */}
      {isClosed
        ? <HistoryPanel history={history} />
        : <SimilarResolutionsPanel resolutions={resolutions} />
      }

      {/* ── Update panel ─────────────────────────────────────────────── */}
      {isAdmin && (
        <div style={card}>
          <div style={cardTitle}>Update Ticket</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>

            <div>
              <label style={labelStyle}>Status</label>
              <select
                value={update.new_status}
                onChange={e => setUpdate(p => ({ ...p, new_status: e.target.value }))}
                style={selectStyle}
                disabled={isClosed}
              >
                {TICKET_STATUSES.map(s => (
                  <option key={s.value} value={s.value}>{s.label}</option>
                ))}
              </select>
              {isClosed && (
                <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '4px' }}>
                  This ticket is closed. Status can no longer be changed.
                </div>
              )}
            </div>

            <div>
              <label style={labelStyle}>
                Assign To <span style={{ color: '#94a3b8' }}>(service no. or name)</span>
              </label>
              <input
                value={update.assignee_id}
                onChange={e => setUpdate(p => ({ ...p, assignee_id: e.target.value }))}
                placeholder="e.g. 12345P or Cpl. Kumar"
                style={selectStyle}
                disabled={isClosed}
              />
            </div>

            <div>
              <label style={labelStyle}>Changed By</label>
              <input
                value={update.changed_by}
                onChange={e => setUpdate(p => ({ ...p, changed_by: e.target.value }))}
                placeholder="Operator ID or name"
                style={selectStyle}
                disabled={isClosed}
              />
            </div>

            <div>
              <label style={labelStyle}>
                Notes{' '}
                {update.new_status === 'closed' && (
                  <span style={{ color: '#e24b4a' }}>* required for closing</span>
                )}
                {CLOSED_STATUSES.includes(update.new_status) && update.new_status !== 'closed' && (
                  <span style={{ color: '#059669' }}> (will be saved as resolution note)</span>
                )}
              </label>
              <textarea
                value={update.notes}
                onChange={e => setUpdate(p => ({ ...p, notes: e.target.value }))}
                placeholder={
                  isClosed
                    ? 'Ticket is already closed.'
                    : CLOSED_STATUSES.includes(update.new_status)
                      ? 'Describe exactly how you resolved this issue — this note will help future operators!'
                      : 'Update note, progress, or context...'
                }
                rows={3}
                style={{ ...selectStyle, resize: 'vertical', lineHeight: '1.6' }}
                disabled={isClosed}
              />
            </div>

            {!isClosed && (
              <button
                onClick={handleUpdate}
                disabled={saving || (update.new_status === 'closed' && !update.notes.trim())}
                style={{
                  background: '#185FA5', color: '#fff', border: 'none',
                  borderRadius: '8px', padding: '10px 20px',
                  fontSize: '13px', fontWeight: 500, cursor: 'pointer',
                  opacity: (saving || (update.new_status === 'closed' && !update.notes.trim())) ? 0.6 : 1,
                }}
              >
                {saving ? 'Saving...' : 'Update Ticket'}
              </button>
            )}

          </div>
        </div>
      )}

    </div>
  );
}

const card = { background: '#fff', border: '0.5px solid #e2e8f0', borderRadius: '12px', padding: '16px 20px' };
const cardTitle = { fontWeight: 500, fontSize: '13px', marginBottom: '12px' };
const labelStyle = { display: 'block', fontSize: '12px', color: '#64748b', marginBottom: '4px' };
const selectStyle = {
  width: '100%', padding: '9px 12px', fontSize: '13px',
  border: '0.5px solid #cbd5e1', borderRadius: '8px',
  outline: 'none', fontFamily: 'inherit', color: '#1a1a2e',
  background: '#fff',
};

export default TicketDetail;

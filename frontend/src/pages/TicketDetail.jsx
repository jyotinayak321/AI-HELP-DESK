import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { listTickets, updateTicket } from '../api/tickets.api';
import { TICKET_STATUSES, SEVERITY_COLOR, STATUS_COLOR } from '../constants/enums';
import Badge from '../components/ui/Badge';
import LoadingSpinner from '../components/ui/LoadingSpinner';
import ErrorMessage from '../components/ui/ErrorMessage';
import toast from 'react-hot-toast';

function TicketDetail() {
  const { ticketNumber } = useParams();
  const navigate = useNavigate();
  const [ticket,  setTicket]  = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving,  setSaving]  = useState(false);
  const [error,   setError]   = useState(null);
  const [update,  setUpdate]  = useState({ status: '', notes: '', resolving_action: '' });

  async function load() {
    setLoading(true); setError(null);
    try {
      const res = await listTickets({ search: ticketNumber });
      const found = (res.data?.tickets ?? res.data ?? []).find(t => t.ticket_number === ticketNumber);
      if (!found) throw new Error('Ticket not found');
      setTicket(found);
      setUpdate({ status: found.status, notes: '', resolving_action: '' });
    } catch (e) {
      setError(e.message || 'Failed to load ticket');
    } finally { setLoading(false); }
  }

  useEffect(() => { load(); }, [ticketNumber]);

  async function handleUpdate() {
    setSaving(true);
    try {
      const payload = {
        status: update.status,
        ...(update.notes && { notes: update.notes }),
        ...(update.resolving_action && { resolving_action: update.resolving_action }),
      };
      await updateTicket(ticketNumber, payload);
      toast.success('Ticket updated!');
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Update failed');
    } finally { setSaving(false); }
  }

  if (loading) return <LoadingSpinner text="Ticket load ho raha hai..." />;
  if (error)   return <ErrorMessage message={error} onRetry={load} />;
  if (!ticket) return null;

  return (
    <div style={{ maxWidth: '680px', display: 'flex', flexDirection: 'column', gap: '16px' }}>

      <button onClick={() => navigate('/tickets')} style={{
        background: 'none', border: 'none', color: '#185FA5',
        fontSize: '13px', cursor: 'pointer', alignSelf: 'flex-start', padding: 0,
      }}>
        ← Back to Tickets
      </button>

      <div style={card}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <div style={{ fontFamily: 'monospace', fontSize: '13px', color: '#64748b', marginBottom: '4px' }}>
              {ticket.ticket_number}
            </div>
            <div style={{ fontSize: '15px', fontWeight: 500 }}>
              {ticket.primary_app_name ?? 'Unclassified'}
            </div>
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            <Badge label={ticket.severity} color={SEVERITY_COLOR[ticket.severity]} bg={(SEVERITY_COLOR[ticket.severity] || '#888') + '22'} />
            <Badge label={ticket.status}   color={STATUS_COLOR[ticket.status]}    bg={(STATUS_COLOR[ticket.status] || '#888') + '22'} />
          </div>
        </div>
      </div>

      <div style={card}>
        <div style={cardTitle}>Complaint</div>
        <div style={{ fontSize: '13px', lineHeight: '1.7', background: '#f8fafc', borderRadius: '8px', padding: '12px' }}>
          {ticket.original_complaint_text}
        </div>
        <div style={{ fontSize: '12px', color: '#64748b', marginTop: '10px', display: 'flex', gap: '20px' }}>
          <span>Service No: <strong>{ticket.complainant_service_no}</strong></span>
          {ticket.complainant_identity && (
            <span>Name: <strong>{ticket.complainant_identity}</strong></span>
          )}
          <span>Fault: <strong>{ticket.fault_type?.replace(/_/g, ' ')}</strong></span>
        </div>
      </div>

      {ticket.routed_to && (
        <div style={card}>
          <div style={cardTitle}>Routing</div>
          <div style={{ fontSize: '13px' }}>
            Routed to: <strong>{ticket.routed_to}</strong>
          </div>
        </div>
      )}

      <div style={card}>
        <div style={cardTitle}>Update Ticket</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>

          <div>
            <label style={labelStyle}>Status</label>
            <select
              value={update.status}
              onChange={e => setUpdate(p => ({ ...p, status: e.target.value }))}
              style={selectStyle}
            >
              {TICKET_STATUSES.map(s => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>
          </div>

          <div>
            <label style={labelStyle}>Notes</label>
            <textarea
              value={update.notes}
              onChange={e => setUpdate(p => ({ ...p, notes: e.target.value }))}
              placeholder="Update note ya progress..."
              rows={3}
              style={{ ...selectStyle, resize: 'vertical', lineHeight: '1.6' }}
            />
          </div>

          {(update.status === 'resolved' || update.status === 'closed') && (
            <div>
              <label style={labelStyle}>Resolving Action</label>
              <textarea
                value={update.resolving_action}
                onChange={e => setUpdate(p => ({ ...p, resolving_action: e.target.value }))}
                placeholder="Kya kiya tha fix karne ke liye..."
                rows={3}
                style={{ ...selectStyle, resize: 'vertical', lineHeight: '1.6' }}
              />
            </div>
          )}

          <button
            onClick={handleUpdate}
            disabled={saving}
            style={{
              background: '#185FA5', color: '#fff', border: 'none',
              borderRadius: '8px', padding: '10px 20px',
              fontSize: '13px', fontWeight: 500, cursor: 'pointer',
              opacity: saving ? 0.6 : 1,
            }}
          >
            {saving ? 'Saving...' : 'Update Ticket'}
          </button>

        </div>
      </div>
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
};

export default TicketDetail;
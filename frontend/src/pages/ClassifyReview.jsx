import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { confirmTicket, confirmMultiTicket } from '../api/tickets.api';
import { FAULT_TYPES, SEVERITY_LEVELS, SEVERITY_COLOR } from '../constants/enums';
import ErrorMessage from '../components/ui/ErrorMessage';
import LoadingSpinner from '../components/ui/LoadingSpinner';

/**
 * A single ticket form block for the R-14a multi-fault intake.
 */
function TicketBlock({ index, ticket, candidates, onUpdate, onRemove, canRemove }) {
  function set(key, val) { onUpdate(index, { ...ticket, [key]: val }); }
  function toggleRelated(appId) {
    const next = ticket.relatedAppIds.includes(appId)
      ? ticket.relatedAppIds.filter(id => id !== appId)
      : [...ticket.relatedAppIds, appId];
    set('relatedAppIds', next);
  }

  return (
    <div style={{ border: '1px solid #cbd5e1', borderRadius: '12px', padding: '16px', background: '#fafbfc', position: 'relative' }}>
      {canRemove && (
        <button onClick={() => onRemove(index)} style={{
          position: 'absolute', top: '10px', right: '12px',
          background: 'none', border: 'none', color: '#e24b4a', fontSize: '18px', cursor: 'pointer', lineHeight: 1
        }} title="Remove this ticket">✕</button>
      )}
      <div style={{ fontSize: '12px', fontWeight: 600, color: '#64748b', marginBottom: '10px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        Ticket {index + 1}
      </div>

      {/* App selection */}
      <div style={{ marginBottom: '10px' }}>
        <div style={cardTitle}>Primary Application</div>
        {candidates.map(c => (
          <div key={c.application_id} onClick={() => set('selectedAppId', c.application_id)}
            style={{
              display: 'flex', alignItems: 'center', gap: '12px',
              padding: '8px 12px', borderRadius: '8px', cursor: 'pointer', marginBottom: '4px',
              border: ticket.selectedAppId === c.application_id ? '1.5px solid #185FA5' : '0.5px solid #e2e8f0',
              background: ticket.selectedAppId === c.application_id ? '#E6F1FB' : '#fff',
            }}>
            <input type="radio" readOnly checked={ticket.selectedAppId === c.application_id} style={{ accentColor: '#185FA5' }} />
            <span style={{ fontSize: '13px', flex: 1 }}>{c.application_name}</span>
            {ticket.selectedAppId !== c.application_id && (
              <label style={{ fontSize: '11px', color: '#64748b', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px' }}
                onClick={e => { e.stopPropagation(); toggleRelated(c.application_id); }}>
                <input type="checkbox" checked={ticket.relatedAppIds.includes(c.application_id)} readOnly /> related
              </label>
            )}
          </div>
        ))}
      </div>

      {/* Fault + Severity */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
        <div>
          <div style={cardTitle}>Fault Type</div>
          <select value={ticket.faultType} onChange={e => set('faultType', e.target.value)} style={selectStyle}>
            {FAULT_TYPES.map(f => <option key={f.value} value={f.value}>{f.label}</option>)}
          </select>
        </div>
        <div>
          <div style={cardTitle}>Severity</div>
          <select value={ticket.severity} onChange={e => set('severity', e.target.value)} style={selectStyle}>
            {SEVERITY_LEVELS.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
          </select>
          <div style={{ marginTop: '6px', height: '3px', borderRadius: '2px', background: SEVERITY_COLOR[ticket.severity] || '#e2e8f0' }} />
        </div>
      </div>

      {/* Notes */}
      <div style={{ marginTop: '12px' }}>
        <div style={cardTitle}>Notes (optional)</div>
        <textarea value={ticket.notes} onChange={e => set('notes', e.target.value)}
          placeholder="Context for this specific fault..." rows={2}
          style={{ ...selectStyle, resize: 'vertical', lineHeight: '1.6' }} />
      </div>
    </div>
  );
}

function ClassifyReview() {
  const { state } = useLocation();
  const navigate  = useNavigate();

  if (!state?.intakeResponse) { navigate('/submit'); return null; }

  const { intakeResponse, originalForm } = state;
  const { candidates, fault_type_proposal, severity_proposal, is_repeat_caller, potential_duplicates, intake_id } = intakeResponse;

  const sameUserDupes = (potential_duplicates || []).filter(d => d.is_same_user);
  const diffUserDupes = (potential_duplicates || []).filter(d => !d.is_same_user);

  const defaultTicket = () => ({
    selectedAppId: candidates.find(c => c.is_primary)?.application_id ?? candidates[0]?.application_id ?? null,
    relatedAppIds: candidates.filter(c => !c.is_primary).map(c => c.application_id),
    faultType: fault_type_proposal,
    severity: severity_proposal,
    notes: '',
    noMatch: false,
  });

  // R-14a: array of ticket blocks
  const [tickets,  setTickets]  = useState([defaultTicket()]);
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState(null);

  function updateTicket(idx, updated) {
    setTickets(prev => prev.map((t, i) => i === idx ? updated : t));
  }
  function addTicket() {
    setTickets(prev => [...prev, { ...defaultTicket(), faultType: 'other', severity: 'medium', notes: '', relatedAppIds: [] }]);
  }
  function removeTicket(idx) {
    setTickets(prev => prev.filter((_, i) => i !== idx));
  }

  async function handleConfirm() {
    setLoading(true); setError(null);
    try {
      const predictedAppId       = candidates.find(c => c.is_primary)?.application_id ?? null;

      if (tickets.length === 1) {
        // Single ticket — use original endpoint for backwards compat
        const t = tickets[0];
        const payload = {
          intake_id,
          confirmed_app_id:     t.noMatch ? null : t.selectedAppId,
          related_app_ids:      t.noMatch ? [] : t.relatedAppIds,
          confirmed_fault_type: t.noMatch ? 'other' : t.faultType,
          confirmed_severity:   t.noMatch ? 'normal' : t.severity,
          operator_notes:       t.notes || '',
          predicted_app_id:     predictedAppId,
          predicted_fault_type: fault_type_proposal,
          predicted_severity:   severity_proposal,
        };
        const res = await confirmTicket(payload);
        navigate('/tickets', { state: { newTicket: res.data } });
      } else {
        // R-14a: multi-ticket
        const payload = {
          intake_id,
          tickets: tickets.map(t => ({
            confirmed_app_id:     t.noMatch ? candidates[0]?.application_id : t.selectedAppId,
            related_app_ids:      t.noMatch ? [] : t.relatedAppIds,
            confirmed_fault_type: t.noMatch ? 'other' : t.faultType,
            confirmed_severity:   t.noMatch ? 'normal' : t.severity,
            operator_notes:       t.notes || '',
            predicted_app_id:     predictedAppId,
            predicted_fault_type: fault_type_proposal,
            predicted_severity:   severity_proposal,
          })),
        };
        const res = await confirmMultiTicket(payload);
        navigate('/tickets', { state: { newTicket: res.data.created_tickets[0] } });
      }
    } catch (e) {
      setError(e.response?.data?.detail || e.message || 'Confirm failed');
    } finally {
      setLoading(false);
    }
  }

  if (loading) return <LoadingSpinner text="Ticket(s) create ho rahe hain..." />;

  return (
    <div style={{ maxWidth: '720px', display: 'flex', flexDirection: 'column', gap: '16px' }}>

      {/* Duplicate alerts */}
      {sameUserDupes.length > 0 && (
        <div style={{ background: '#FAEEDA', border: '0.5px solid #FAC775', borderRadius: '10px', padding: '12px 16px', fontSize: '13px', color: '#633806' }}>
          <div style={{ fontWeight: 600, marginBottom: '6px' }}>⚠ This user already submitted similar open tickets:</div>
          {sameUserDupes.map(d => (
            <div key={d.ticket_number} style={{ marginLeft: '10px', marginBottom: '4px' }}>
              • <strong>{d.ticket_number}</strong>: "{d.text_snippet}"
            </div>
          ))}
        </div>
      )}

      {diffUserDupes.length > 0 && (
        <div style={{ background: '#FCEBEB', border: '0.5px solid #e24b4a', borderRadius: '10px', padding: '12px 16px', fontSize: '13px', color: '#A32D2D' }}>
          <div style={{ fontWeight: 600, marginBottom: '6px' }}>🚨 Mass Outage Warning: Other users recently reported highly similar issues:</div>
          {diffUserDupes.map(d => (
            <div key={d.ticket_number} style={{ marginLeft: '10px', marginBottom: '4px' }}>
              • <strong>{d.ticket_number}</strong> ({d.complainant_service_no}): "{d.text_snippet}"
            </div>
          ))}
        </div>
      )}

      {error && <ErrorMessage message={error} />}

      {/* Original complaint */}
      <div style={card}>
        <div style={cardTitle}>Original Complaint</div>
        <div style={{ fontSize: '13px', background: '#f8fafc', borderRadius: '8px', padding: '12px', lineHeight: '1.7' }}>
          {originalForm.raw_text}
        </div>
        <div style={{ fontSize: '12px', color: '#64748b', marginTop: '8px' }}>
          Service No: <strong>{originalForm.complainant_service_no}</strong>
          {originalForm.complainant_name && ` — ${originalForm.complainant_name}`}
        </div>
      </div>

      {/* R-14a: Ticket blocks */}
      <div style={card}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
          <div style={cardTitle}>
            {tickets.length === 1 ? 'Confirm Ticket' : `Create ${tickets.length} Tickets from this Intake`}
          </div>
          {tickets.length > 1 && (
            <span style={{ fontSize: '11px', color: '#64748b', background: '#f1f5f9', padding: '3px 8px', borderRadius: '6px' }}>
              R-14a: Multi-fault
            </span>
          )}
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          {tickets.map((t, i) => (
            <TicketBlock
              key={i}
              index={i}
              ticket={t}
              candidates={candidates}
              onUpdate={updateTicket}
              onRemove={removeTicket}
              canRemove={tickets.length > 1}
            />
          ))}
        </div>

        {/* Add another ticket button */}
        <button onClick={addTicket} style={{
          marginTop: '14px', width: '100%', padding: '10px',
          border: '1px dashed #cbd5e1', borderRadius: '8px', background: '#f8fafc',
          color: '#185FA5', fontSize: '13px', cursor: 'pointer', fontWeight: 500,
        }}>
          + Add Another Fault / Ticket for This Complaint
        </button>
      </div>

      <div style={{ display: 'flex', gap: '12px' }}>
        <button onClick={() => navigate('/submit')} style={secondaryBtn}>← Back</button>
        <button onClick={handleConfirm} style={primaryBtn}>
          {tickets.length === 1 ? 'Confirm & Create Ticket →' : `Confirm & Create ${tickets.length} Tickets →`}
        </button>
      </div>
    </div>
  );
}

const card = { background: '#fff', border: '0.5px solid #e2e8f0', borderRadius: '12px', padding: '16px 20px' };
const cardTitle = { fontWeight: 500, fontSize: '13px', marginBottom: '10px' };
const selectStyle = { width: '100%', padding: '9px 12px', fontSize: '13px', border: '0.5px solid #cbd5e1', borderRadius: '8px', outline: 'none', fontFamily: 'inherit', color: '#1a1a2e' };
const primaryBtn = { background: '#185FA5', color: '#fff', border: 'none', borderRadius: '8px', padding: '10px 24px', fontSize: '14px', fontWeight: 500, cursor: 'pointer', flex: 1 };
const secondaryBtn = { background: '#fff', color: '#185FA5', border: '0.5px solid #185FA5', borderRadius: '8px', padding: '10px 20px', fontSize: '14px', cursor: 'pointer' };

export default ClassifyReview;
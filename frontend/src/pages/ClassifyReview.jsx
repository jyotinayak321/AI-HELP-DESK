import { useState, useEffect, useRef } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { confirmTicket, confirmMultiTicket, reanalyzeIntake } from '../api/tickets.api';
import { fetchAudioBlob } from '../api/voice.api';
import { FAULT_TYPES, SEVERITY_LEVELS, SEVERITY_COLOR } from '../constants/enums';
import ErrorMessage from '../components/ui/ErrorMessage';
import LoadingSpinner from '../components/ui/LoadingSpinner';

function TicketBlock({ index, ticket, candidates, onUpdate, onRemove, canRemove }) {
  function set(key, val) { onUpdate(index, { ...ticket, [key]: val }); }
  function toggleRelated(appId) {
    const next = ticket.relatedAppIds.includes(appId)
      ? ticket.relatedAppIds.filter(id => id !== appId)
      : [...ticket.relatedAppIds, appId];
    set('relatedAppIds', next);
  }

  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: '12px', padding: '16px', background: 'var(--surface-2)', position: 'relative' }}>
      {canRemove && (
        <button onClick={() => onRemove(index)} style={{
          position: 'absolute', top: '10px', right: '12px',
          background: 'none', border: 'none', color: 'var(--danger)', fontSize: '18px', cursor: 'pointer', lineHeight: 1
        }} title="Remove this ticket">✕</button>
      )}
      <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '10px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        Ticket {index + 1}
      </div>

      <div style={{ marginBottom: '10px' }}>
        <div style={cardTitle}>Primary Application</div>
        {candidates.map(c => (
          <div key={c.application_id} onClick={() => set('selectedAppId', c.application_id)}
            style={{
              display: 'flex', alignItems: 'center', gap: '12px',
              padding: '8px 12px', borderRadius: '8px', cursor: 'pointer', marginBottom: '4px',
              border: ticket.selectedAppId === c.application_id ? '1.5px solid var(--accent)' : '1px solid var(--border)',
              background: ticket.selectedAppId === c.application_id ? 'rgba(24,95,165,0.12)' : 'var(--surface-1)',
            }}>
            <input type="radio" readOnly checked={ticket.selectedAppId === c.application_id} style={{ accentColor: 'var(--accent)' }} />
            <span style={{ fontSize: '13px', flex: 1, color: 'var(--text-primary)' }}>{c.application_name}</span>
            {ticket.selectedAppId !== c.application_id && (
              <label style={{ fontSize: '11px', color: 'var(--text-muted)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px' }}
                onClick={e => { e.stopPropagation(); toggleRelated(c.application_id); }}>
                <input type="checkbox" checked={ticket.relatedAppIds.includes(c.application_id)} readOnly /> related
              </label>
            )}
          </div>
        ))}
      </div>

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
          <div style={{ marginTop: '6px', height: '3px', borderRadius: '2px', background: SEVERITY_COLOR[ticket.severity] || 'var(--border)' }} />
        </div>
      </div>

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

  const { intakeResponse, originalForm, ttsUrl } = state;
  
  const [intakeResp, setIntakeResp] = useState(intakeResponse);
  const { candidates, fault_type_proposal, severity_proposal, is_repeat_caller, potential_duplicates, intake_id } = intakeResp;

  const [editedComplaint, setEditedComplaint] = useState(originalForm.raw_text);
  const [reanalyzing, setReanalyzing] = useState(false);
  const [newSuggestions, setNewSuggestions] = useState(false);
  const audioRef = useRef(null);

  useEffect(() => {
    let isMounted = true;
    if (ttsUrl) {
      const playTts = async () => {
        try {
          const blobUrl = await fetchAudioBlob(ttsUrl);
          if (!isMounted) return;
          const audio = new Audio(blobUrl);
          audioRef.current = audio;
          await audio.play();
        } catch (err) {
          console.error("Failed to play TTS on ClassifyReview", err);
        }
      };
      playTts();
    }
    return () => {
      isMounted = false;
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current.src = '';
      }
    };
  }, [ttsUrl]);

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

  const [tickets,  setTickets]  = useState([defaultTicket()]);
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState(null);

  function updateTicket(idx, updated) {
    setTickets(prev => prev.map((t, i) => i === idx ? updated : t));
  }
  function addTicket() {
    setTickets(prev => [...prev, { ...defaultTicket(), faultType: 'other', severity: 'normal', notes: '', relatedAppIds: [] }]);
  }
  function removeTicket(idx) {
    setTickets(prev => prev.filter((_, i) => i !== idx));
  }

  async function handleReanalyze() {
    setReanalyzing(true); setError(null);
    try {
      const res = await reanalyzeIntake(intake_id, { raw_text: editedComplaint });
      setIntakeResp(res.data);
      setNewSuggestions(true);
    } catch (e) {
      setError(e.response?.data?.detail || e.message || 'Re-analyze failed');
    } finally {
      setReanalyzing(false);
    }
  }

  function applySuggestions() {
    setTickets([defaultTicket()]);
    setNewSuggestions(false);
  }

  async function handleConfirm() {
    setLoading(true); setError(null);
    try {
      const predictedAppId       = candidates.find(c => c.is_primary)?.application_id ?? null;

      if (tickets.length === 1) {
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
          edited_raw_text:      editedComplaint,
        };
        const res = await confirmTicket(payload);
        navigate('/tickets', { state: { newTicket: res.data } });
      } else {
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
            edited_raw_text:      editedComplaint,
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

      {sameUserDupes.length > 0 && (
        <div style={{ background: 'rgba(245,158,11,0.1)', border: '1px solid var(--warning)', borderRadius: '10px', padding: '12px 16px', fontSize: '13px', color: 'var(--warning)' }}>
          <div style={{ fontWeight: 600, marginBottom: '6px' }}>⚠ This user already submitted similar open tickets:</div>
          {sameUserDupes.map(d => (
            <div key={d.ticket_number} style={{ marginLeft: '10px', marginBottom: '4px' }}>
              • <strong>{d.ticket_number}</strong>: "{d.text_snippet}"
            </div>
          ))}
        </div>
      )}

      {diffUserDupes.length > 0 && (
        <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid var(--danger)', borderRadius: '10px', padding: '12px 16px', fontSize: '13px', color: 'var(--danger)' }}>
          <div style={{ fontWeight: 600, marginBottom: '6px' }}>🚨 Mass Outage Warning: Other users recently reported highly similar issues:</div>
          {diffUserDupes.map(d => (
            <div key={d.ticket_number} style={{ marginLeft: '10px', marginBottom: '4px' }}>
              • <strong>{d.ticket_number}</strong> ({d.complainant_service_no}): "{d.text_snippet}"
            </div>
          ))}
        </div>
      )}

      {error && <ErrorMessage message={error} />}

      <div style={card}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
          <div style={cardTitle} style={{ marginBottom: 0, fontWeight: 500, fontSize: '13px', color: 'var(--text-primary)' }}>Original Complaint</div>
          <button 
            onClick={handleReanalyze} 
            disabled={editedComplaint === (intakeResp.corrected_text || originalForm.raw_text) || reanalyzing}
            style={{ 
              background: 'transparent', color: 'var(--accent)', border: '1px solid var(--accent)', 
              borderRadius: '6px', padding: '4px 10px', fontSize: '12px', cursor: (editedComplaint === (intakeResp.corrected_text || originalForm.raw_text) || reanalyzing) ? 'not-allowed' : 'pointer',
              opacity: (editedComplaint === (intakeResp.corrected_text || originalForm.raw_text) || reanalyzing) ? 0.5 : 1
            }}
          >
            {reanalyzing ? '↻ Re-analyzing...' : '↻ Re-analyze Complaint'}
          </button>
        </div>
        <textarea
          value={editedComplaint}
          onChange={(e) => setEditedComplaint(e.target.value)}
          style={{ width: '100%', fontSize: '13px', background: 'var(--surface-2)', color: 'var(--text-primary)', border: '1px solid var(--border)', borderRadius: '8px', padding: '12px', lineHeight: '1.7', resize: 'vertical', minHeight: '80px', fontFamily: 'inherit' }}
        />
        <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '8px' }}>
          Service No: <strong>{originalForm.complainant_service_no}</strong>
          {originalForm.complainant_name && ` — ${originalForm.complainant_name}`}
        </div>
      </div>

      <div style={card}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
          <div style={cardTitle} style={{ marginBottom: 0, fontWeight: 500, fontSize: '13px', color: 'var(--text-primary)' }}>
            {tickets.length === 1 ? 'Confirm Ticket' : `Create ${tickets.length} Tickets from this Intake`}
          </div>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            {newSuggestions && (
              <button 
                onClick={applySuggestions}
                style={{ background: 'var(--accent)', color: '#fff', border: 'none', borderRadius: '6px', padding: '4px 10px', fontSize: '11px', cursor: 'pointer' }}
              >
                Apply New AI Suggestions
              </button>
            )}
            {tickets.length > 1 && (
              <span style={{ fontSize: '11px', color: 'var(--text-muted)', background: 'var(--surface-2)', padding: '3px 8px', borderRadius: '6px' }}>
                R-14a: Multi-fault
              </span>
            )}
          </div>
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

        <button onClick={addTicket} style={{
          marginTop: '14px', width: '100%', padding: '10px',
          border: '1px dashed var(--border)', borderRadius: '8px', background: 'var(--surface-2)',
          color: 'var(--accent)', fontSize: '13px', cursor: 'pointer', fontWeight: 500,
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

const card = { background: 'var(--surface-1)', border: '1px solid var(--border)', borderRadius: '12px', padding: '16px 20px', boxShadow: 'var(--shadow-card)' };
const cardTitle = { fontWeight: 500, fontSize: '13px', marginBottom: '10px', color: 'var(--text-primary)' };
const selectStyle = { width: '100%', padding: '9px 12px', fontSize: '13px', border: '1px solid var(--border)', borderRadius: '8px', outline: 'none', fontFamily: 'inherit', color: 'var(--text-primary)', background: 'var(--surface-2)' };
const primaryBtn = { background: 'var(--accent)', color: '#fff', border: 'none', borderRadius: '8px', padding: '10px 24px', fontSize: '14px', fontWeight: 500, cursor: 'pointer', flex: 1 };
const secondaryBtn = { background: 'transparent', color: 'var(--accent)', border: '1px solid var(--accent)', borderRadius: '8px', padding: '10px 20px', fontSize: '14px', cursor: 'pointer' };

export default ClassifyReview;
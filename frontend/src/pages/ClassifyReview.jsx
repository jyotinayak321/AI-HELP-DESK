import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { confirmTicket } from '../api/tickets.api';
import { FAULT_TYPES, SEVERITY_LEVELS, SEVERITY_COLOR } from '../constants/enums';
import ErrorMessage from '../components/ui/ErrorMessage';
import LoadingSpinner from '../components/ui/LoadingSpinner';

function ClassifyReview() {
  const { state } = useLocation();
  const navigate  = useNavigate();

  if (!state?.intakeResponse) { navigate('/submit'); return null; }

  const { intakeResponse, originalForm } = state;
  const { candidates, fault_type_proposal, severity_proposal, is_repeat_caller, existing_ticket_number } = intakeResponse;

  const [selectedAppId, setSelectedAppId] = useState(candidates.find(c => c.is_primary)?.application_id ?? candidates[0]?.application_id ?? null);
  const [relatedAppIds, setRelatedAppIds] = useState(candidates.filter(c => !c.is_primary).map(c => c.application_id));
  const [faultType,     setFaultType]     = useState(fault_type_proposal);
  const [severity,      setSeverity]      = useState(severity_proposal);
  const [operatorNotes, setOperatorNotes] = useState('');
  const [noMatch,       setNoMatch]       = useState(false);
  const [loading,       setLoading]       = useState(false);
  const [error,         setError]         = useState(null);

  function toggleRelated(appId) {
    setRelatedAppIds(prev => prev.includes(appId) ? prev.filter(id => id !== appId) : [...prev, appId]);
  }

  async function handleConfirm() {
    setLoading(true); setError(null);
    try {
      const payload = {
        complainant_service_no:   originalForm.complainant_service_no,
        complainant_identity:     originalForm.complainant_identity,
        original_complaint_text:  originalForm.raw_text,
        confirmed_primary_app_id: noMatch ? null : selectedAppId,
        confirmed_fault_type:     noMatch ? 'other' : faultType,
        confirmed_severity:       noMatch ? 'normal' : severity,
        predicted_primary_app_id: candidates.find(c => c.is_primary)?.application_id ?? null,
        predicted_fault_type:     fault_type_proposal,
        predicted_severity:       severity_proposal,
        related_app_ids:          noMatch ? [] : relatedAppIds,
        operator_notes:           operatorNotes || undefined,
      };
      const res = await confirmTicket(payload);
      navigate('/tickets', { state: { newTicket: res.data } });
    } catch (e) {
      setError(e.response?.data?.detail || e.message || 'Confirm failed');
    } finally {
      setLoading(false);
    }
  }

  if (loading) return <LoadingSpinner text="Ticket create ho raha hai..." />;

  return (
    <div style={{ maxWidth: '700px', display: 'flex', flexDirection: 'column', gap: '16px' }}>

      {is_repeat_caller && (
        <div style={{ background: '#FAEEDA', border: '0.5px solid #FAC775', borderRadius: '10px', padding: '12px 16px', fontSize: '13px', color: '#633806' }}>
          ⚠ Repeat caller — existing ticket: <strong>{existing_ticket_number}</strong>
        </div>
      )}

      {error && <ErrorMessage message={error} />}

      <div style={card}>
        <div style={cardTitle}>Original Complaint</div>
        <div style={{ fontSize: '13px', background: '#f8fafc', borderRadius: '8px', padding: '12px', lineHeight: '1.7' }}>
          {originalForm.raw_text}
        </div>
        <div style={{ fontSize: '12px', color: '#64748b', marginTop: '8px' }}>
          Service No: <strong>{originalForm.complainant_service_no}</strong>
          {originalForm.complainant_identity && ` — ${originalForm.complainant_identity}`}
        </div>
      </div>

      <div style={card}>
        <div style={cardTitle}>AI Candidate Applications — Select Primary</div>
        {candidates.map(c => (
          <div key={c.application_id} onClick={() => { setSelectedAppId(c.application_id); setNoMatch(false); }}
            style={{
              display: 'flex', alignItems: 'center', gap: '12px',
              padding: '10px 12px', borderRadius: '8px', cursor: 'pointer', marginBottom: '6px',
              border: selectedAppId === c.application_id && !noMatch ? '1.5px solid #185FA5' : '0.5px solid #e2e8f0',
              background: selectedAppId === c.application_id && !noMatch ? '#E6F1FB' : '#fff',
            }}>
            <input type="radio" readOnly checked={selectedAppId === c.application_id && !noMatch} style={{ accentColor: '#185FA5' }} />
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: '13px', fontWeight: 500 }}>{c.name}</div>
              {c.expansion_reason && <div style={{ fontSize: '11px', color: '#64748b', marginTop: '2px' }}>Pulled in: {c.expansion_reason}</div>}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div style={{ width: '80px', height: '4px', background: '#e2e8f0', borderRadius: '2px' }}>
                <div style={{ width: `${Math.round(c.confidence_score * 100)}%`, height: '100%', background: '#185FA5', borderRadius: '2px' }} />
              </div>
              <span style={{ fontSize: '11px', color: '#64748b' }}>{Math.round(c.confidence_score * 100)}%</span>
            </div>
            {c.is_primary && <span style={{ fontSize: '10px', padding: '2px 8px', borderRadius: '10px', background: '#E6F1FB', color: '#185FA5' }}>AI pick</span>}
            {selectedAppId !== c.application_id && (
              <label style={{ fontSize: '11px', color: '#64748b', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <input type="checkbox" checked={relatedAppIds.includes(c.application_id)} onChange={() => toggleRelated(c.application_id)} />
                related
              </label>
            )}
          </div>
        ))}
        <div onClick={() => { setNoMatch(true); setSelectedAppId(null); }}
          style={{
            display: 'flex', alignItems: 'center', gap: '10px',
            padding: '10px 12px', borderRadius: '8px', cursor: 'pointer',
            border: noMatch ? '1.5px solid #e24b4a' : '0.5px solid #e2e8f0',
            background: noMatch ? '#FCEBEB' : '#fff',
          }}>
          <input type="radio" readOnly checked={noMatch} style={{ accentColor: '#e24b4a' }} />
          <span style={{ fontSize: '13px', color: '#A32D2D' }}>None of these match — log as Needs Triage</span>
        </div>
      </div>

      {!noMatch && (
        <div style={{ ...card, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
          <div>
            <div style={cardTitle}>Fault Type</div>
            <select value={faultType} onChange={e => setFaultType(e.target.value)} style={selectStyle}>
              {FAULT_TYPES.map(f => <option key={f.value} value={f.value}>{f.label}</option>)}
            </select>
          </div>
          <div>
            <div style={cardTitle}>Severity</div>
            <select value={severity} onChange={e => setSeverity(e.target.value)} style={selectStyle}>
              {SEVERITY_LEVELS.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
            </select>
            <div style={{ marginTop: '8px', height: '4px', borderRadius: '2px', background: SEVERITY_COLOR[severity] || '#e2e8f0' }} />
          </div>
        </div>
      )}

      <div style={card}>
        <div style={cardTitle}>Operator Notes (optional)</div>
        <textarea value={operatorNotes} onChange={e => setOperatorNotes(e.target.value)}
          placeholder="Additional context ya correction note..." rows={3} style={{ ...selectStyle, resize: 'vertical', lineHeight: '1.6' }} />
      </div>

      <div style={{ display: 'flex', gap: '12px' }}>
        <button onClick={() => navigate('/submit')} style={secondaryBtn}>← Back</button>
        <button onClick={handleConfirm} style={primaryBtn}>
          {noMatch ? 'Log as Triage →' : 'Confirm & Create Ticket →'}
        </button>
      </div>
    </div>
  );
}

const card = { background: '#fff', border: '0.5px solid #e2e8f0', borderRadius: '12px', padding: '16px 20px' };
const cardTitle = { fontWeight: 500, fontSize: '13px', marginBottom: '12px' };
const selectStyle = { width: '100%', padding: '9px 12px', fontSize: '13px', border: '0.5px solid #cbd5e1', borderRadius: '8px', outline: 'none', fontFamily: 'inherit', color: '#1a1a2e' };
const primaryBtn = { background: '#185FA5', color: '#fff', border: 'none', borderRadius: '8px', padding: '10px 24px', fontSize: '14px', fontWeight: 500, cursor: 'pointer', flex: 1 };
const secondaryBtn = { background: '#fff', color: '#185FA5', border: '0.5px solid #185FA5', borderRadius: '8px', padding: '10px 20px', fontSize: '14px', cursor: 'pointer' };

export default ClassifyReview;
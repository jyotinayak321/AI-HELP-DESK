import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { submitIntake } from '../api/tickets.api';
import LoadingSpinner from '../components/ui/LoadingSpinner';
import ErrorMessage from '../components/ui/ErrorMessage';
import VoiceSessionPanel from '../components/voice/VoiceSessionPanel';

function SubmitComplaint() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    raw_text: '',
    complainant_service_no: '',
    complainant_name: '',
    complainant_unit: '',
    complainant_rank: '',
  });
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState(null);
  const [isVoiceMode, setIsVoiceMode] = useState(false);

  function handleChange(e) {
    setForm(prev => ({ ...prev, [e.target.name]: e.target.value }));
  }

async function handleSubmit() {
  if (!form.raw_text.trim() || !form.complainant_service_no.trim()) {
    setError('Complaint text aur service number dono required hain.');
    return;
  }
  const svcPattern = /^\d{5}$/;
  if (!svcPattern.test(form.complainant_service_no.trim())) {
    setError('Service number must be exactly 5 digits (e.g., 12345).');
    return;
  }
  setLoading(true); setError(null);
  try {
    const payload = {
      raw_text: form.raw_text.trim(),
      complainant_service_no: form.complainant_service_no.trim(),
      complainant_name: form.complainant_name.trim() || '',
      complainant_unit: form.complainant_unit.trim() || '',
      complainant_rank: form.complainant_rank.trim() || '',
      operator_id: 'system',
    };
    const res = await submitIntake(payload);

    if (res.data.corrected_text) {
      payload.raw_text = res.data.corrected_text;
    }

    navigate('/classify', { state: { intakeResponse: res.data, originalForm: payload } });
  } catch (e) {
    setError(e.response?.data?.detail || e.message || 'Intake failed');
  } finally {
    setLoading(false);
  }
}

  function handleVoiceClassificationComplete(intakeResponse, voiceForm, ttsUrl) {
    navigate('/classify', { state: { intakeResponse, originalForm: voiceForm, ttsUrl } });
  }

  if (loading) return <LoadingSpinner text="AI classification chal rahi hai..." />;

  return (
    <div style={{ maxWidth: '640px', display: 'flex', flexDirection: 'column', gap: '16px' }}>

      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '-8px' }}>
        <button
          onClick={() => {
            setIsVoiceMode(!isVoiceMode);
            setError(null);
          }}
          style={{
            background: isVoiceMode ? 'var(--surface-2)' : 'rgba(24,95,165,0.12)',
            color: isVoiceMode ? 'var(--text-secondary)' : 'var(--accent)',
            border: `1px solid ${isVoiceMode ? 'var(--border)' : 'var(--accent)'}`,
            padding: '8px 16px', borderRadius: '20px', fontSize: '13px', fontWeight: 600, cursor: 'pointer'
          }}
        >
          {isVoiceMode ? 'Switch to Manual Entry' : '🎙️ Switch to Voice Mode'}
        </button>
      </div>

      {error && <ErrorMessage message={error} />}

      {isVoiceMode ? (
        <VoiceSessionPanel
          onClassificationComplete={handleVoiceClassificationComplete}
          onCancel={() => setIsVoiceMode(false)}
        />
      ) : (
        <>
          <div style={card}>
            <div style={cardTitle}>Complainant Details</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '14px' }}>
              <div>
                <labeel style={labelStyle}>Service Number *</labeel>
                <input name="complainant_service_no" value={form.complainant_service_no}
                  onChange={handleChange} placeholder="e.g. 12345" style={inputStyle} />
              </div>
              <div>
                <label style={labelStyle}>Name (optional)</label>
                <input name="complainant_name" value={form.complainant_name}
                  onChange={handleChange} placeholder="Complainant ka naam" style={inputStyle} />
              </div>
              <div>
                <label style={labelStyle}>Unit (optional)</label>
                <input name="complainant_unit" value={form.complainant_unit}
                  onChange={handleChange} placeholder="e.g. Admin Wing" style={inputStyle} />
              </div>
              <div>
                <label style={labelStyle}>Rank (optional)</label>
                <input name="complainant_rank" value={form.complainant_rank}
                  onChange={handleChange} placeholder="e.g. Sergeant" style={inputStyle} />
              </div>
            </div>
          </div>

          <div style={card}>
            <div style={cardTitle}>Complaint Description</div>

            <>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '12px' }}>
                English, Hindi, ya Hinglish — jo bhi operator type kare
              </div>
              <textarea name="raw_text" value={form.raw_text} onChange={handleChange}
                placeholder="e.g. Mera login nahi ho raha HRMS mein — kal se same problem chal rahi hai..."
                rows={6} style={{ ...inputStyle, resize: 'vertical', lineHeight: '1.6' }} />
            </>
          </div>

          <button onClick={handleSubmit}
            disabled={!form.raw_text.trim() || !form.complainant_service_no.trim()}
            style={{
              background: 'var(--accent)', color: '#fff', border: 'none',
              borderRadius: '8px', padding: '10px 24px',
              fontSize: '14px', fontWeight: 500, cursor: 'pointer',
              opacity: (!form.raw_text.trim() || !form.complainant_service_no.trim()) ? 0.5 : 1,
            }}>
            Classify Complaint →
          </button>
        </>
      )}

    </div>
  );
}

const card = { background: 'var(--surface-1)', border: '1px solid var(--border)', borderRadius: '12px', padding: '20px', boxShadow: 'var(--shadow-card)' };
const cardTitle = { fontWeight: 500, fontSize: '14px', marginBottom: '16px', color: 'var(--text-primary)' };
const labelStyle = { display: 'block', fontSize: '12px', color: 'var(--text-muted)', marginBottom: '5px' };
const inputStyle = {
  width: '100%', padding: '9px 12px', fontSize: '13px',
  border: '1px solid var(--border)', borderRadius: '8px',
  outline: 'none', fontFamily: 'inherit', color: 'var(--text-primary)',
  background: 'var(--surface-2)',
};
export default SubmitComplaint;
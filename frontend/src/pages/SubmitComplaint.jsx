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
  // Issue 3: separate state for "voice complaint only" after manual service-no entry
  const [voiceComplaintMode, setVoiceComplaintMode] = useState(false);

  function handleChange(e) {
    setForm(prev => ({ ...prev, [e.target.name]: e.target.value }));
  }

  async function handleSubmit() {
    if (!form.raw_text.trim() || !form.complainant_service_no.trim()) {
      setError('Complaint text aur service number dono required hain.');
      return;
    }
    const svcPattern = /^\d{3}[a-zA-Z]$/;
    if (!svcPattern.test(form.complainant_service_no.trim())) {
      setError('Service number must be exactly 3 digits followed by 1 letter (e.g., 123A).');
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
      navigate('/classify', { state: { intakeResponse: res.data, originalForm: payload } });
    } catch (e) {
      setError(e.response?.data?.detail || e.message || 'Intake failed');
    } finally {
      setLoading(false);
    }
  }

  function handleVoiceClassificationComplete(intakeResponse, voiceForm, ttsUrl) {
    // Merge manually-entered service number if coming from voiceComplaintMode
    const merged = voiceComplaintMode
      ? { ...voiceForm, complainant_service_no: form.complainant_service_no }
      : voiceForm;
    navigate('/classify', { state: { intakeResponse, originalForm: merged, ttsUrl } });
  }

  if (loading) return <LoadingSpinner text="AI classification chal rahi hai..." />;

  return (
    <div style={{ maxWidth: '640px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
      
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '-8px' }}>
        <button 
          onClick={() => setIsVoiceMode(!isVoiceMode)}
          style={{
            background: isVoiceMode ? '#f1f5f9' : '#e0f2fe',
            color: isVoiceMode ? '#475569' : '#0284c7',
            border: `1px solid ${isVoiceMode ? '#cbd5e1' : '#bae6fd'}`,
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
                <label style={labelStyle}>Service Number *</label>
                <input name="complainant_service_no" value={form.complainant_service_no}
                  onChange={handleChange} placeholder="e.g. 2893456P" style={inputStyle} />
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

            {voiceComplaintMode && form.complainant_service_no.trim() ? (
              // Voice Panel in complaint-only mode
              <VoiceSessionPanel
                onClassificationComplete={handleVoiceClassificationComplete}
                onCancel={() => setVoiceComplaintMode(false)}
              />
            ) : (
              <>
                <div style={{ fontSize: '12px', color: '#64748b', marginBottom: '12px' }}>
                  English, Hindi, ya Hinglish — jo bhi operator type kare
                </div>
                <textarea name="raw_text" value={form.raw_text} onChange={handleChange}
                  placeholder="e.g. Mera login nahi ho raha HRMS mein — kal se same problem chal rahi hai..."
                  rows={6} style={{ ...inputStyle, resize: 'vertical', lineHeight: '1.6' }} />

                {/* Issue 3: Switch to voice for complaint if service number is already filled */}
                {form.complainant_service_no.trim() && (
                  <button
                    onClick={() => setVoiceComplaintMode(true)}
                    style={{
                      marginTop: '10px',
                      background: '#e0f2fe', color: '#0284c7',
                      border: '1px solid #bae6fd',
                      padding: '8px 16px', borderRadius: '20px',
                      fontSize: '13px', fontWeight: 600, cursor: 'pointer',
                    }}
                  >
                    🎙️ Use Voice for Complaint
                  </button>
                )}
              </>
            )}
          </div>

          {!voiceComplaintMode && (
            <button onClick={handleSubmit}
              disabled={!form.raw_text.trim() || !form.complainant_service_no.trim()}
              style={{
                background: '#185FA5', color: '#fff', border: 'none',
                borderRadius: '8px', padding: '10px 24px',
                fontSize: '14px', fontWeight: 500, cursor: 'pointer',
                opacity: (!form.raw_text.trim() || !form.complainant_service_no.trim()) ? 0.5 : 1,
              }}>
              Classify Complaint →
            </button>
          )}
        </>
      )}

    </div>
  );
}

const card = { background: '#fff', border: '0.5px solid #e2e8f0', borderRadius: '12px', padding: '20px' };
const cardTitle = { fontWeight: 500, fontSize: '14px', marginBottom: '16px' };
const labelStyle = { display: 'block', fontSize: '12px', color: '#64748b', marginBottom: '5px' };
const inputStyle = {
  width: '100%', padding: '9px 12px', fontSize: '13px',
  border: '0.5px solid #cbd5e1', borderRadius: '8px',
  outline: 'none', fontFamily: 'inherit', color: '#1a1a2e',
};
export default SubmitComplaint;
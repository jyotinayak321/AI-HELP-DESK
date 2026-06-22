import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { submitIntake, confirmTicket } from '../api/tickets.api';
import { FAULT_TYPES, SEVERITY_LEVELS } from '../constants/enums';

function SubmitComplaint() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    raw_text: '', complainant_service_no: 'SN-8821-XP', complainant_identity: '',
  });
  
  const [intakeResponse, setIntakeResponse] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  // Classify Review State
  const [selectedAppId, setSelectedAppId] = useState(null);
  const [relatedAppIds, setRelatedAppIds] = useState([]);
  const [faultType, setFaultType] = useState('');
  const [severity, setSeverity] = useState('');
  const [noMatch, setNoMatch] = useState(false);

  function handleChange(e) {
    setForm(prev => ({ ...prev, [e.target.name]: e.target.value }));
  }

  async function handleAnalyze() {
    if (!form.raw_text.trim() || !form.complainant_service_no.trim()) {
      setError('Complaint text and service number are required.');
      return;
    }
    setLoading(true); setError(null); setIntakeResponse(null);
    try {
      const payload = {
        raw_text: form.raw_text.trim(),
        complainant_service_no: form.complainant_service_no.trim(),
        complainant_identity: form.complainant_identity.trim() || undefined,
      };
      const res = await submitIntake(payload);
      const data = res.data;
      setIntakeResponse(data);
      
      const primaryCandidate = data.candidates.find(c => c.is_primary) || data.candidates[0];
      setSelectedAppId(primaryCandidate?.application_id || null);
      setRelatedAppIds(data.candidates.filter(c => !c.is_primary).map(c => c.application_id));
      setFaultType(data.fault_type_proposal || '');
      setSeverity(data.severity_proposal || '');
      setNoMatch(false);
    } catch (e) {
      setError(e.response?.data?.detail || e.message || 'Intake failed');
    } finally {
      setLoading(false);
    }
  }

  async function handleConfirm() {
    setLoading(true); setError(null);
    try {
      const payload = {
        complainant_service_no: form.complainant_service_no,
        complainant_identity: form.complainant_identity,
        original_complaint_text: form.raw_text,
        confirmed_primary_app_id: noMatch ? null : selectedAppId,
        confirmed_fault_type: noMatch ? 'other' : faultType,
        confirmed_severity: noMatch ? 'normal' : severity,
        predicted_primary_app_id: intakeResponse.candidates.find(c => c.is_primary)?.application_id ?? null,
        predicted_fault_type: intakeResponse.fault_type_proposal,
        predicted_severity: intakeResponse.severity_proposal,
        related_app_ids: noMatch ? [] : relatedAppIds,
        operator_notes: undefined,
      };
      const res = await confirmTicket(payload);
      navigate('/tickets', { state: { newTicket: res.data } });
    } catch (e) {
      setError(e.response?.data?.detail || e.message || 'Confirm failed');
    } finally {
      setLoading(false);
    }
  }

  const primaryCandidate = intakeResponse?.candidates?.find(c => c.application_id === selectedAppId) || intakeResponse?.candidates?.[0];

  return (
    <div className="space-y-gutter">
      {error && <div className="bg-error-container text-on-error-container px-4 py-3 rounded-lg">{error}</div>}

      <div className="bg-surface-container-lowest border border-outline-variant rounded-xl overflow-hidden shadow-sm">
        <div className="p-6">
          <label className="block font-label-sm text-on-surface-variant mb-stack-compact" htmlFor="service-number">Service Number</label>
          <div className="relative">
            <input 
              name="complainant_service_no" 
              value={form.complainant_service_no} 
              onChange={handleChange}
              className="w-full text-headline-md font-headline-md py-3 px-4 border border-outline-variant rounded-lg focus:border-primary focus:ring-1 focus:ring-primary-container outline-none transition-all" 
              id="service-number" type="text" 
            />
            <span className="absolute right-4 top-1/2 -translate-y-1/2 material-symbols-outlined text-primary">contact_page</span>
          </div>
        </div>
        {intakeResponse?.is_repeat_caller && (
          <div className="bg-tertiary-fixed text-on-tertiary-fixed px-6 py-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="material-symbols-outlined text-[20px] text-tertiary">warning</span>
              <span className="font-body-md font-medium">Repeat caller — existing ticket: {intakeResponse.existing_ticket_number}</span>
            </div>
            <button onClick={() => navigate('/tickets')} className="text-tertiary-fixed-variant font-semibold text-body-sm hover:underline flex items-center gap-1">
              View Tickets <span className="material-symbols-outlined text-sm">open_in_new</span>
            </button>
          </div>
        )}
      </div>

      <div className="bg-surface-container-lowest border border-outline-variant rounded-xl p-6 shadow-sm">
        <div className="flex items-center justify-between mb-stack-default">
          <label className="block font-headline-sm text-headline-sm" htmlFor="description">Complaint Description</label>
          <span className="text-on-surface-variant font-label-sm uppercase tracking-widest bg-surface-container px-2 py-0.5 rounded">Voice-to-Text Enabled</span>
        </div>
        <textarea 
          name="raw_text"
          value={form.raw_text}
          onChange={handleChange}
          className="w-full font-body-lg text-body-lg p-4 border border-outline-variant rounded-lg focus:border-primary focus:ring-1 focus:ring-primary-container outline-none transition-all resize-none custom-scrollbar" 
          id="description" placeholder="Describe the issue in your own words..." rows="6"
        />
        <div className="mt-6 flex justify-center">
          <button 
            disabled={loading || !form.raw_text.trim()} 
            onClick={handleAnalyze} 
            className="bg-primary text-on-primary px-10 py-4 rounded-full font-headline-sm text-headline-sm shadow-lg shadow-primary-container hover:translate-y-[-2px] active:translate-y-0 transition-all flex items-center gap-3 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <span className={`material-symbols-outlined ${loading ? 'animate-spin' : ''}`}>{loading ? 'refresh' : 'psychology'}</span>
            {loading ? 'Analyzing...' : 'Analyze Complaint'}
          </button>
        </div>
      </div>

      {loading && (
        <div className="animate-in fade-in duration-500">
          <div className="bg-surface-container-low border border-outline-variant rounded-xl p-8 border-dashed flex flex-col items-center justify-center text-on-surface-variant space-y-4">
            <div className="relative w-12 h-12">
              <div className="absolute inset-0 border-4 border-primary/20 rounded-full"></div>
              <div className="absolute inset-0 border-4 border-primary rounded-full border-t-transparent animate-spin"></div>
            </div>
            <div className="text-center">
              <h3 className="font-headline-sm text-headline-sm">Searching similar cases...</h3>
              <p className="font-body-sm mt-1">AI engine is classifying the intent and matching dependencies</p>
            </div>
            <div className="w-full max-w-sm space-y-3 mt-4">
              <div className="h-4 w-full loading-shimmer rounded"></div>
              <div className="h-4 w-2/3 loading-shimmer rounded mx-auto"></div>
            </div>
          </div>
        </div>
      )}

      {intakeResponse && !loading && (
        <div className="bg-surface-container-lowest border border-primary-container rounded-xl shadow-xl overflow-hidden animate-in slide-in-from-bottom-4 duration-700">
          <div className="bg-on-primary-container px-6 py-2 flex items-center justify-between">
            <span className="text-on-primary-fixed-variant font-label-sm uppercase tracking-widest font-bold">AI Suggested Classification</span>
            <div className="flex items-center gap-1 text-primary">
              <span className="material-symbols-outlined text-sm" style={{ fontVariationSettings: "'FILL' 1" }}>auto_awesome</span>
              <span className="font-label-sm">High Confidence</span>
            </div>
          </div>
          <div className="p-8">
            <div className="flex flex-col md:flex-row items-start gap-8">
              <div className="flex items-center gap-4 bg-surface-container rounded-xl p-4 flex-1 w-full md:w-auto">
                <div className="w-16 h-16 bg-primary rounded-lg flex items-center justify-center text-on-primary">
                  <span className="material-symbols-outlined text-4xl" style={{ fontVariationSettings: "'FILL' 1" }}>holiday_village</span>
                </div>
                <div>
                  <h3 className="font-headline-lg text-headline-lg">{primaryCandidate?.name || 'Unknown Application'}</h3>
                  <p className="text-on-surface-variant font-body-sm">Predicted Primary Target</p>
                </div>
              </div>
              
              <div className="flex flex-col items-center justify-center bg-secondary-container/30 border border-secondary-container rounded-xl p-4 w-full md:w-32">
                <div className="relative w-16 h-16 flex items-center justify-center">
                  <svg className="w-full h-full -rotate-90">
                    <circle className="text-secondary-container/50" cx="32" cy="32" fill="transparent" r="28" stroke="currentColor" strokeWidth="4"></circle>
                    <circle className="text-primary" cx="32" cy="32" fill="transparent" r="28" stroke="currentColor" strokeDasharray="176" strokeDashoffset={176 - (176 * (primaryCandidate?.confidence_score || 0))} strokeWidth="4"></circle>
                  </svg>
                  <span className="absolute font-headline-sm text-headline-sm">{Math.round((primaryCandidate?.confidence_score || 0) * 100)}%</span>
                </div>
                <span className="font-label-md mt-2 text-on-secondary-container">Confidence</span>
              </div>
            </div>

            <div className="mt-8 grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="font-label-sm text-on-surface-variant ml-1">Fault Type</label>
                <div className="relative">
                  <select value={faultType} onChange={e => setFaultType(e.target.value)} className="w-full appearance-none bg-surface-container border border-outline-variant rounded-lg py-2 px-4 pr-10 font-body-md focus:ring-1 focus:ring-primary outline-none transition-all">
                    {FAULT_TYPES.map(f => <option key={f.value} value={f.value}>{f.label}</option>)}
                  </select>
                  <span className="absolute right-3 top-1/2 -translate-y-1/2 material-symbols-outlined text-on-surface-variant pointer-events-none">expand_more</span>
                </div>
              </div>
              <div className="space-y-2">
                <label className="font-label-sm text-on-surface-variant ml-1">Severity</label>
                <div className="relative">
                  <select value={severity} onChange={e => setSeverity(e.target.value)} className="w-full appearance-none bg-tertiary-fixed text-on-tertiary-fixed border border-tertiary-container rounded-lg py-2 px-4 pr-10 font-body-md focus:ring-1 focus:ring-tertiary-container outline-none transition-all">
                    {SEVERITY_LEVELS.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
                  </select>
                  <span className="absolute right-3 top-1/2 -translate-y-1/2 material-symbols-outlined text-on-tertiary-fixed pointer-events-none">expand_more</span>
                </div>
              </div>
            </div>

            {intakeResponse.candidates.length > 1 && (
              <div className="mt-8 border-t border-outline-variant pt-6">
                <h4 className="font-label-sm text-on-surface-variant uppercase tracking-wider mb-4">Other Candidates</h4>
                <div className="flex flex-wrap gap-4">
                  {intakeResponse.candidates.filter(c => c.application_id !== selectedAppId).map(c => (
                    <div key={c.application_id} className="flex items-center gap-3 bg-surface border border-outline-variant px-4 py-3 rounded-lg">
                      <div className="w-8 h-8 rounded bg-secondary-container flex items-center justify-center">
                        <span className="material-symbols-outlined text-on-secondary-container text-[20px]">extension</span>
                      </div>
                      <div>
                        <p className="font-body-md font-semibold">{c.name}</p>
                        <p className="text-[11px] text-on-surface-variant">{Math.round(c.confidence_score * 100)}% match</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="mt-10 flex flex-col items-center gap-4">
              <button onClick={handleConfirm} className="w-full bg-primary text-on-primary py-4 rounded-lg font-headline-sm text-headline-sm hover:bg-primary-fixed-variant transition-colors shadow-lg active:scale-[0.98]">
                Confirm & Create Ticket
              </button>
              <button onClick={() => { setNoMatch(true); handleConfirm(); }} className="text-on-surface-variant hover:text-primary font-body-md transition-colors flex items-center gap-1">
                None of these — search manually <span className="material-symbols-outlined text-[18px]">search</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
export default SubmitComplaint;
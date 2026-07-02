import React, { useState, useEffect, useRef } from 'react';
import { 
  startVoiceSession, 
  submitServiceNumberAudio, 
  submitComplaintAudio, 
  confirmServiceNumber,
  submitConfirmAudio,
  submitFallback,
  fetchAudioBlob
} from '../../api/voice.api';
import VoiceRecorder from './VoiceRecorder';
import TranscriptPanel from './TranscriptPanel';

/**
 * VoiceSessionPanel Component
 * Orchestrates the full voice session state machine.
 */
function VoiceSessionPanel({ onClassificationComplete, onCancel }) {
  const [session, setSession] = useState({
    id: null,
    state: 'INIT', // INIT, GREETING, CAPTURING_SERVICE_NUMBER, CONFIRMING_SERVICE_NUMBER, CAPTURING_COMPLAINT, OPERATOR_FALLBACK, ERROR
    promptText: 'Starting voice session...',
    transcript: '',
    serviceNumber: '',
    confidence: 0,
    language: '',
    latency: 0,
    retries: 0
  });

  const [isProcessing, setIsProcessing] = useState(false);
  const [fallbackData, setFallbackData] = useState({ service_no: '' });
  // autoStartTrigger: toggled to a new Date() to tell VoiceRecorder to start listening.
  const [autoStartTrigger, setAutoStartTrigger] = useState(null);
  const audioPlayerRef = useRef(new Audio());
  // Stores the ordered blob URLs for the service-number confirmation sequence
  const confirmSequenceRef = useRef([]);

  const isMounted = useRef(true);
  const hasInitialized = useRef(false);
  const playbackIdRef = useRef(0);

  useEffect(() => {
    isMounted.current = true;
    
    // Hack to unlock the Audio element for autoplay:
    // Play a tiny silent WAV file synchronously during the click event that mounts this component.
    // This attaches the user gesture token to the audio player, preventing NotAllowedError later.
    audioPlayerRef.current.src = 'data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA=';
    audioPlayerRef.current.play().catch(() => {});

    // Start session on mount only once (Strict Mode fix)
    if (!hasInitialized.current) {
      hasInitialized.current = true;
      initSession();
    }
    
    return () => {
      isMounted.current = false;
      playbackIdRef.current++; // Abort any running sequence
      // Cleanup audio
      if (audioPlayerRef.current) {
        audioPlayerRef.current.pause();
        audioPlayerRef.current.src = '';
      }
    };
  }, []);

  // ─── Play a short beep then start VAD ─────────────────────────────────
  const triggerVAD = () => {
    if (!isMounted.current) return;
    playBeep();
    // Small delay so the beep finishes before mic opens
    setTimeout(() => {
      if (isMounted.current) setAutoStartTrigger(new Date());
    }, 600);
  };

  // ─── Programmatic beep using AudioContext oscillator ──────────────────
  const playBeep = () => {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.type = 'sine';
      osc.frequency.setValueAtTime(880, ctx.currentTime);         // A5 note
      gain.gain.setValueAtTime(0.3, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.45);
      osc.start(ctx.currentTime);
      osc.stop(ctx.currentTime + 0.45);
    } catch (e) {
      console.warn('Beep failed:', e);
    }
  };

  const initSession = async () => {
    setIsProcessing(true);
    try {
      const res = await startVoiceSession();
      if (!isMounted.current) return;
      setSession(prev => ({
        ...prev,
        id: res.data.session_id,
        state: res.data.state,
        promptText: res.data.prompt_text,
      }));
      // Play short prompt then trigger VAD automatically
      await playAudio(`http://127.0.0.1:8000/api/voice/prompt/ask_service_number?_t=${Date.now()}`);
      if (isMounted.current) triggerVAD();
    } catch (err) {
      console.error(err);
      if (isMounted.current) {
        setSession(prev => ({ ...prev, state: 'ERROR', promptText: 'Failed to start voice session.' }));
      }
    } finally {
      if (isMounted.current) setIsProcessing(false);
    }
  };

  const stopAllAudio = () => {
    playbackIdRef.current++; // Invalidates active play sequences
    if (audioPlayerRef.current) {
      audioPlayerRef.current.pause();
      audioPlayerRef.current.currentTime = 0;
      audioPlayerRef.current.src = '';
    }
  };

  // playAudio — now returns a Promise that resolves when audio FINISHES playing
  const playAudio = async (url) => {
    if (!url) return null;
    const currentId = ++playbackIdRef.current;
    try {
      if (audioPlayerRef.current) {
        audioPlayerRef.current.pause();
        audioPlayerRef.current.src = '';
      }
      const blobUrl = await fetchAudioBlob(url);
      if (!isMounted.current || playbackIdRef.current !== currentId) return null;
      audioPlayerRef.current.src = blobUrl;
      // Wait until playback finishes (not just starts)
      await new Promise((resolve) => {
        audioPlayerRef.current.onended = resolve;
        audioPlayerRef.current.onerror = resolve;
        audioPlayerRef.current.play().catch(resolve);
      });
      return blobUrl;
    } catch (e) {
      if (playbackIdRef.current === currentId) {
        console.error('Audio play failed:', e);
      }
      return null;
    }
  };

  /**
   * Play a list of audio URLs sequentially, one after the other.
   * Returns the array of fetched blob URLs (for caching/replay).
   */
  const playSequential = async (urls) => {
    const player = audioPlayerRef.current;
    const blobs = [];
    const currentId = ++playbackIdRef.current;
    for (let url of urls) {
      if (!isMounted.current || playbackIdRef.current !== currentId) break;
      try {
        const blobUrl = await fetchAudioBlob(url);
        if (!isMounted.current || playbackIdRef.current !== currentId) break;
        blobs.push(blobUrl);
        player.src = blobUrl;
        await new Promise((resolve, reject) => {
          player.onended = resolve;
          player.onerror = reject;
          player.play().catch(reject);
        });
      } catch (e) {
        if (playbackIdRef.current !== currentId) break; // User intentionally stopped it
        console.error('Sequential audio failed at:', url, e);
        blobs.push(null);
      }
    }
    return blobs;
  };

  const handleRecordingComplete = async (audioBlob) => {
    if (!session.id) return;
    setIsProcessing(true);

    try {
      // Issue 1 FIX: CONFIRMING state audio goes to confirm-audio endpoint, not service-number
      if (session.state === 'CONFIRMING_SERVICE_NUMBER') {
        const res = await submitConfirmAudio(session.id, audioBlob);
        setSession(prev => ({
          ...prev,
          state: res.data.state,
          transcript: res.data.recognized_text || '[Unrecognized or silent audio]',
          promptText: res.data.prompt_text,
          language: res.data.stt_language,
          latency: res.data.stt_processing_time_ms,
        }));
        if (res.data.state === 'CAPTURING_COMPLAINT') {
          // Edge case: confirm said "yes" but went back to complaint
          await playAudio(`http://127.0.0.1:8000/api/voice/prompt/ask_complaint?_t=${Date.now()}`);
          if (isMounted.current) triggerVAD();
        } else if (res.data.state === 'CAPTURING_SERVICE_NUMBER') {
          // Edge case: confirm audio failed, ask again
          await playAudio(`http://127.0.0.1:8000/api/voice/prompt/ask_service_number?_t=${Date.now()}`);
          if (isMounted.current) triggerVAD();
        } else {
          // Unclear — stay on CONFIRMING, play the prompt, then trigger VAD
          await playAudio(`http://127.0.0.1:8000/api/voice/prompt/confirm_yes_no?_t=${Date.now()}`);
          if (isMounted.current) triggerVAD();
        }
      } else if (session.state === 'CAPTURING_SERVICE_NUMBER') {
        const res = await submitServiceNumberAudio(session.id, audioBlob);
        
        setSession(prev => ({
          ...prev,
          state: res.data.state,
          transcript: res.data.recognized_text || '[Unrecognized or silent audio]',
          serviceNumber: res.data.normalised_service_no,
          confidence: res.data.confidence,
          language: res.data.stt_language,
          latency: res.data.stt_processing_time_ms,
          promptText: res.data.prompt_text,
          retries: res.data.retries_count
        }));

        if (res.data.state === 'CONFIRMING_SERVICE_NUMBER' && res.data.is_valid) {
          const BASE = 'http://127.0.0.1:8000/api/voice';
          const sequence = [
            `${BASE}/prompt/heard_as`,
            `${BASE}/spell/${encodeURIComponent(res.data.normalised_service_no)}`,
            `${BASE}/prompt/is_that_correct`,
            `${BASE}/prompt/confirm_yes_no`,
          ];
          confirmSequenceRef.current = [];
          // Play the confirmation sequence then auto-trigger VAD for yes/no
          playSequential(sequence).then(async blobs => {
            if (isMounted.current) {
              confirmSequenceRef.current = blobs;
              triggerVAD(); // VAD for yes/no answer
            }
          });
        } else if (res.data.state === 'CAPTURING_SERVICE_NUMBER') {
          // Retry edge case: STT failed, ask again + VAD
          await playAudio(`http://127.0.0.1:8000/api/voice/prompt/retry_service?_t=${Date.now()}`);
          if (isMounted.current) triggerVAD();
        } else if (res.data.state === 'OPERATOR_FALLBACK') {
          playAudio(`http://127.0.0.1:8000/api/voice/prompt/fallback_operator?_t=${Date.now()}`);
        }
      } 
      else if (session.state === 'CAPTURING_COMPLAINT' || session.state === 'OPERATOR_REVIEW') {
        const res = await submitComplaintAudio(session.id, audioBlob);
        
        setSession(prev => ({
          ...prev,
          state: res.data.state,
          transcript: res.data.transcript || '[Unrecognized or silent audio]',
          confidence: res.data.confidence,
          language: res.data.stt_language,
          latency: res.data.stt_processing_time_ms,
          promptText: res.data.prompt_text,
        }));

        if (res.data.state === 'OPERATOR_REVIEW') {
           // We do not play the summary audio here anymore.
           // Since the component unmounts immediately to navigate to ClassifyReview,
           // we pass the TTS URL to the parent so it can be played on the next screen.
           const ttsUrl = `http://127.0.0.1:8000/api/voice/tts?text=${encodeURIComponent(res.data.prompt_text)}`;
           
           // Pass the final proposal to the parent SubmitComplaint form
           // We map the response slightly to match the Phase 1 IntakeResponse format expected by ClassifyReview
           const intakeResponse = {
             intake_id: res.data.intake_id,
             is_repeat_caller: false, // Could be extracted if we added it to VoiceComplaintResponse
             potential_duplicates: [],
             fault_type_proposal: res.data.fault_type_proposal,
             severity_proposal: res.data.severity_proposal,
             candidates: res.data.candidates
           };
           
           onClassificationComplete(intakeResponse, {
             raw_text: res.data.transcript,
             complainant_service_no: session.serviceNumber,
             complainant_name: '',
             complainant_unit: '',
             complainant_rank: ''
           }, ttsUrl);
         } else if (res.data.state === 'CAPTURING_COMPLAINT') {
           // Silence or invalid complaint — ask again with VAD auto-restart
           await playAudio(`http://127.0.0.1:8000/api/voice/prompt/ask_complaint?_t=${Date.now()}`);
           if (isMounted.current) triggerVAD();
         }
      }
    } catch (err) {
      console.error(err);
      setSession(prev => ({ ...prev, state: 'ERROR', promptText: 'An error occurred during audio processing.' }));
    } finally {
      setIsProcessing(false);
    }
  };

  const handleServiceNumberConfirm = async (confirmed) => {
    setIsProcessing(true);
    try {
      const res = await confirmServiceNumber(session.id, confirmed);
      setSession(prev => ({
        ...prev,
        state: res.data.state,
        promptText: res.data.prompt_text,
        transcript: '', // clear for next stage
      }));
      
      if (confirmed) {
        // Yes — go to complaint capture
        await playAudio(`http://127.0.0.1:8000/api/voice/prompt/ask_complaint?_t=${Date.now()}`);
        if (isMounted.current) triggerVAD();
      } else {
        // No — retry service number edge case
        await playAudio(`http://127.0.0.1:8000/api/voice/prompt/ask_service_number?_t=${Date.now()}`);
        if (isMounted.current) triggerVAD();
      }
    } catch (err) {
      console.error(err);
      setSession(prev => ({ ...prev, state: 'ERROR', promptText: 'Error confirming service number.' }));
    } finally {
      setIsProcessing(false);
    }
  };

  const handleReplayServiceNumber = () => {
    const blobs = confirmSequenceRef.current.filter(Boolean);
    if (!blobs.length) return;
    // Play each cached blob in sequence — zero network/TTS calls
    const player = audioPlayerRef.current;
    let idx = 0;
    const playNext = () => {
      if (idx >= blobs.length) return;
      player.src = blobs[idx++];
      player.onended = playNext;
      player.play().catch(console.error);
    };
    player.pause();
    playNext();
  };

  const handleFallbackSubmit = async () => {
    if (!fallbackData.service_no.trim()) return;
    const svcPattern = /^\d{3}[a-zA-Z]$/;
    if (!svcPattern.test(fallbackData.service_no.trim())) {
      alert('Service number must be exactly 3 digits followed by 1 letter (e.g., 123A).');
      return;
    }
    setIsProcessing(true);
    try {
      const res = await submitFallback(session.id, fallbackData);
      setSession(prev => ({
        ...prev,
        state: res.data.state,
        promptText: res.data.prompt_text,
        serviceNumber: res.data.service_no,
        transcript: '',
      }));
      // Fallback edge case: after manual service number entry, auto-start VAD for complaint
      await playAudio(`http://127.0.0.1:8000/api/voice/prompt/ask_complaint`);
      if (isMounted.current) triggerVAD();
    } catch (err) {
       console.error(err);
    } finally {
       setIsProcessing(false);
    }
  };

  return (
    <div style={panelContainerStyle}>
      <div style={headerStyle}>
        <div style={statusBadgeStyle(session.state)}>
          Status: {session.state.replace(/_/g, ' ')}
        </div>
        <button onClick={onCancel} style={cancelBtnStyle}>✕ Cancel Voice Mode</button>
      </div>

      <div style={promptBoxStyle}>
        <span style={{fontSize: '12px', color: '#64748b', fontWeight: 600, display: 'block', marginBottom: '8px'}}>System Prompt:</span>
        <p style={{margin: 0, fontSize: '15px', fontWeight: 500, color: '#1e293b'}}>{session.promptText}</p>
        
        {session.state === 'OPERATOR_FALLBACK' && (
          <div style={fallbackBoxStyle}>
            <p style={{margin: '0 0 10px 0', fontSize: '13px', color: '#e24b4a'}}>Maximum retries exceeded. Please enter service number manually.</p>
            <input 
              type="text" 
              placeholder="e.g. 2893456P" 
              value={fallbackData.service_no}
              onChange={e => setFallbackData(prev => ({...prev, service_no: e.target.value}))}
              style={inputStyle}
            />
            <button onClick={handleFallbackSubmit} style={btnPrimaryStyle}>Submit & Continue</button>
          </div>
        )}

        {session.state === 'CONFIRMING_SERVICE_NUMBER' && (
          <div style={confirmBoxStyle}>
            <p style={{margin: '0 0 10px 0', fontSize: '14px', fontWeight: 500}}>Did the caller say: <strong style={{color: '#185FA5'}}>{session.serviceNumber}</strong>?</p>
            <div style={{display: 'flex', gap: '10px', flexWrap: 'wrap'}}>
              <button onClick={() => handleServiceNumberConfirm(true)} style={btnPrimaryStyle}>Yes (Confirm)</button>
              <button onClick={() => handleServiceNumberConfirm(false)} style={btnSecondaryStyle}>No (Retry)</button>
              <button onClick={handleReplayServiceNumber} style={btnReplayStyle} title="Replay service number read-back">🔊 Replay</button>
            </div>
          </div>
        )}
      </div>

      {(session.state === 'CAPTURING_SERVICE_NUMBER' || session.state === 'CAPTURING_COMPLAINT' || session.state === 'CONFIRMING_SERVICE_NUMBER' || session.state === 'OPERATOR_REVIEW') && (
        <VoiceRecorder 
          onRecordingComplete={handleRecordingComplete}
          onRecordingStart={stopAllAudio}
          isProcessing={isProcessing}
          autoStartTrigger={autoStartTrigger}
        />
      )}

      <TranscriptPanel 
        transcript={session.transcript}
        confidence={session.confidence}
        language={session.language}
        processingTimeMs={session.latency}
        state={session.state}
      />
    </div>
  );
}

// Inline Styles
const panelContainerStyle = {
  background: '#fff',
  border: '2px solid #185FA5',
  borderRadius: '16px',
  padding: '24px',
  marginBottom: '24px',
  boxShadow: '0 4px 6px rgba(24, 95, 165, 0.1)',
};

const headerStyle = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  marginBottom: '20px',
};

const statusBadgeStyle = (state) => ({
  background: state === 'ERROR' ? '#fee2e2' : state === 'OPERATOR_FALLBACK' ? '#fef08a' : '#E6F1FB',
  color: state === 'ERROR' ? '#991b1b' : state === 'OPERATOR_FALLBACK' ? '#854d0e' : '#185FA5',
  padding: '6px 12px',
  borderRadius: '16px',
  fontSize: '12px',
  fontWeight: 600,
  letterSpacing: '0.05em',
});

const cancelBtnStyle = {
  background: 'none',
  border: 'none',
  color: '#64748b',
  cursor: 'pointer',
  fontSize: '13px',
  fontWeight: 500,
};

const promptBoxStyle = {
  background: '#f1f5f9',
  borderLeft: '4px solid #185FA5',
  padding: '16px',
  borderRadius: '0 8px 8px 0',
  marginBottom: '20px',
};

const fallbackBoxStyle = {
  marginTop: '16px',
  paddingTop: '16px',
  borderTop: '1px solid #cbd5e1',
};

const confirmBoxStyle = {
  marginTop: '16px',
  paddingTop: '16px',
  borderTop: '1px solid #cbd5e1',
};

const inputStyle = {
  padding: '10px 12px',
  fontSize: '14px',
  border: '1px solid #cbd5e1',
  borderRadius: '8px',
  marginRight: '12px',
  outline: 'none',
};

const btnPrimaryStyle = {
  background: '#185FA5',
  color: 'white',
  border: 'none',
  padding: '10px 20px',
  borderRadius: '8px',
  fontSize: '14px',
  fontWeight: 500,
  cursor: 'pointer',
};

const btnSecondaryStyle = {
  background: '#f1f5f9',
  color: '#334155',
  border: '1px solid #cbd5e1',
  padding: '10px 20px',
  borderRadius: '8px',
  fontSize: '14px',
  fontWeight: 500,
  cursor: 'pointer',
};

const btnReplayStyle = {
  background: '#f0fdf4',
  color: '#166534',
  border: '1px solid #bbf7d0',
  padding: '10px 18px',
  borderRadius: '8px',
  fontSize: '14px',
  fontWeight: 500,
  cursor: 'pointer',
  display: 'flex',
  alignItems: 'center',
  gap: '6px',
};

export default VoiceSessionPanel;

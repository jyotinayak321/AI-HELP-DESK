import React, { useState, useEffect, useRef } from 'react';
import { 
  startVoiceSession, 
  submitServiceNumberAudio, 
  submitComplaintAudio, 
  confirmServiceNumber,
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
  const audioPlayerRef = useRef(new Audio());
  // Stores the ordered blob URLs for the service-number confirmation sequence
  // [heard_as.wav, <tts number>, confirm_yes_no.wav]
  // so Replay can play them again without any network/TTS calls.
  const confirmSequenceRef = useRef([]);

  useEffect(() => {
    // Start session on mount
    initSession();
    
    return () => {
      // Cleanup audio
      audioPlayerRef.current.pause();
      audioPlayerRef.current.src = '';
    };
  }, []);

  const initSession = async () => {
    setIsProcessing(true);
    try {
      const res = await startVoiceSession();
      setSession(prev => ({
        ...prev,
        id: res.data.session_id,
        state: res.data.state,
        promptText: res.data.prompt_text,
      }));
      // Play greeting
      playAudio(`http://127.0.0.1:8000/api/voice/prompt/greeting`);
    } catch (err) {
      console.error(err);
      setSession(prev => ({ ...prev, state: 'ERROR', promptText: 'Failed to start voice session.' }));
    } finally {
      setIsProcessing(false);
    }
  };

  const playAudio = async (url) => {
    if (!url) return null;
    try {
      if (audioPlayerRef.current) {
        audioPlayerRef.current.pause();
        audioPlayerRef.current.src = '';
      }
      const blobUrl = await fetchAudioBlob(url);
      audioPlayerRef.current.src = blobUrl;
      await audioPlayerRef.current.play();
      return blobUrl;
    } catch (e) {
      console.error('Audio play failed:', e);
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
    for (const url of urls) {
      try {
        const blobUrl = await fetchAudioBlob(url);
        blobs.push(blobUrl);
        player.src = blobUrl;
        await new Promise((resolve, reject) => {
          player.onended = resolve;
          player.onerror = reject;
          player.play().catch(reject);
        });
      } catch (e) {
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
      if (session.state === 'CAPTURING_SERVICE_NUMBER' || session.state === 'CONFIRMING_SERVICE_NUMBER') {
        const res = await submitServiceNumberAudio(session.id, audioBlob);
        
        setSession(prev => ({
          ...prev,
          state: res.data.state,
          transcript: res.data.recognized_text,
          serviceNumber: res.data.normalised_service_no,
          confidence: res.data.confidence,
          language: res.data.stt_language,
          latency: res.data.stt_processing_time_ms,
          promptText: res.data.prompt_text,
          retries: res.data.retries_count
        }));

        if (res.data.state === 'CONFIRMING_SERVICE_NUMBER' && res.data.is_valid) {
          // Three pre-recorded clips played sequentially:
          //   1. heard_as.wav       — "I heard your service number as"
          //   2. /spell/{number}    — backend stitches char clips into one WAV (same Zira voice, no gaps)
          //   3. is_that_correct.wav — "Is that correct?"
          //   4. confirm_yes_no.wav  — "Please say yes or no."
          const BASE = 'http://127.0.0.1:8000/api/voice';
          const sequence = [
            `${BASE}/prompt/heard_as`,
            `${BASE}/spell/${encodeURIComponent(res.data.normalised_service_no)}`,
            `${BASE}/prompt/is_that_correct`,
            `${BASE}/prompt/confirm_yes_no`,
          ];
          confirmSequenceRef.current = [];
          const blobs = await playSequential(sequence);
          confirmSequenceRef.current = blobs;
        } else if (res.data.state === 'CAPTURING_SERVICE_NUMBER') {
          playAudio(`http://127.0.0.1:8000/api/voice/prompt/retry_service`);
        } else if (res.data.state === 'OPERATOR_FALLBACK') {
          playAudio(`http://127.0.0.1:8000/api/voice/prompt/fallback_operator`);
        }
      } 
      else if (session.state === 'CAPTURING_COMPLAINT') {
        const res = await submitComplaintAudio(session.id, audioBlob);
        
        setSession(prev => ({
          ...prev,
          state: res.data.state,
          transcript: res.data.transcript,
          confidence: res.data.confidence,
          language: res.data.stt_language,
          latency: res.data.stt_processing_time_ms,
          promptText: res.data.prompt_text,
        }));

        if (res.data.state === 'OPERATOR_REVIEW') {
           // Play summary
           playAudio(`http://127.0.0.1:8000/api/voice/tts?text=${encodeURIComponent(res.data.prompt_text)}`);
           
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
           });
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
        playAudio(`http://127.0.0.1:8000/api/voice/prompt/ask_complaint`);
      } else {
        playAudio(`http://127.0.0.1:8000/api/voice/prompt/ask_service_number`);
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
      playAudio(`http://127.0.0.1:8000/api/voice/prompt/ask_complaint`);
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

      {(session.state === 'CAPTURING_SERVICE_NUMBER' || session.state === 'CAPTURING_COMPLAINT' || session.state === 'CONFIRMING_SERVICE_NUMBER') && (
        <VoiceRecorder 
          onRecordingComplete={handleRecordingComplete} 
          isProcessing={isProcessing} 
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

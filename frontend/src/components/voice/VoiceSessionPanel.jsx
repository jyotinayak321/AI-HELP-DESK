import React, { useState, useEffect, useRef, useCallback } from 'react';
import toast from 'react-hot-toast';
import { startVoiceSession, submitServiceNumberAudio, submitComplaintAudio, confirmServiceNumber, submitConfirmAudio, submitAnotherComplaintAudio, submitFallback, fetchAudioBlob, getLiveKitToken } from '../../api/voice.api';
import VoiceRecorder from './VoiceRecorder';
import TranscriptPanel from './TranscriptPanel';
import LiveKitAudioTransport from './LiveKitAudioTransport';

const VOICE_API_BASE = 'http://127.0.0.1:8001/api/voice';

function VoiceSessionPanel({ onClassificationComplete, onCancel, onCallEnded, resumeSessionId, resumeState, resumePromptText, lastTicketNumber }) {
  const [session, setSession] = useState({
    id: null, state: 'INIT', promptText: 'Starting voice session...', transcript: '', serviceNumber: '', confidence: 0, language: '', latency: 0,
    livekitEnabled: false, livekitToken: null, livekitUrl: null,
  });
  const [isProcessing, setIsProcessing] = useState(false);
  const [audioPlaying, setAudioPlaying] = useState(false);
  const [fallbackData, setFallbackData] = useState({ service_no: '' });

  const audioPlayerRef  = useRef(new Audio());
  const confirmBlobsRef = useRef([]);
  const isMounted       = useRef(true);
  const playbackIdRef   = useRef(0);
  const greetingDoneRef = useRef(false);

  useEffect(() => {
    isMounted.current = true;
    initSession();
    return () => {
      isMounted.current = false;
      playbackIdRef.current++;
      if (audioPlayerRef.current) { audioPlayerRef.current.pause(); audioPlayerRef.current.src = ''; }
    };
  }, []);

  const initSession = async () => {
    setIsProcessing(true);
    try {
      // R-42: resuming an existing call (looping for another complaint)
      // instead of starting a brand-new voice session.
      if (resumeSessionId) {
        setSession(prev => ({ ...prev, id: resumeSessionId, state: resumeState, promptText: resumePromptText }));

        // Phase 4: the room (if any) is still alive server-side — re-issue
        // a caller token for it. 404s if this session never had a LiveKit
        // room (LIVEKIT_ENABLED=false), in which case we just continue on
        // the legacy record/upload flow below.
        try {
          const lkRes = await getLiveKitToken(resumeSessionId);
          if (isMounted.current) {
            setSession(prev => ({
              ...prev,
              livekitEnabled: true,
              livekitToken: lkRes.data.livekit_token,
              livekitUrl: lkRes.data.livekit_url,
            }));
          }
        } catch (_) {
          // No active LiveKit room for this session — legacy path, ignore.
        }

        greetingDoneRef.current = true;
        if (isMounted.current) setIsProcessing(false);
        await playAudio(`${VOICE_API_BASE}/prompt/ask_another_complaint`);
        return;
      }

      const res = await startVoiceSession();
      if (!isMounted.current) return;
      setSession(prev => ({
        ...prev,
        id: res.data.session_id,
        state: res.data.state,
        promptText: res.data.prompt_text,
        livekitEnabled: res.data.livekit_enabled || false,
        livekitToken: res.data.livekit_token || null,
        livekitUrl: res.data.livekit_url || null,
      }));
      // REQUIREMENT 1 & 2: Play greeting FULLY — mic tab tak OFF
      await playAudio(`http://127.0.0.1:8001/api/voice/prompt/greeting`);
      // REQUIREMENT 3: Greeting khatam — ab mic on hoga
      greetingDoneRef.current = true;
    } catch (err) {
      console.error('Session init failed:', err);
      if (isMounted.current) setSession(prev => ({ ...prev, state: 'ERROR', promptText: 'Failed to start session.' }));
    } finally {
      if (isMounted.current) setIsProcessing(false);
    }
  };

  const stopAllAudio = useCallback(() => {
    playbackIdRef.current++;
    if (audioPlayerRef.current) { audioPlayerRef.current.pause(); audioPlayerRef.current.currentTime = 0; audioPlayerRef.current.src = ''; }
    setAudioPlaying(false);
  }, []);

  // REQUIREMENT 4 & 5: Barge-in — user bole toh TTS band
  const handleRecordingStart = useCallback(() => {
    if (audioPlayerRef.current && !audioPlayerRef.current.paused) {
      console.log('Barge-in — stopping TTS');
      stopAllAudio();
    }
  }, [stopAllAudio]);

  const playAudio = useCallback(async (url) => {
    if (!url || !isMounted.current) return;
    const currentId = ++playbackIdRef.current;
    try {
      if (audioPlayerRef.current) { audioPlayerRef.current.pause(); audioPlayerRef.current.src = ''; }
      const blobUrl = await fetchAudioBlob(url);
      if (!isMounted.current || playbackIdRef.current !== currentId) return;
      setAudioPlaying(true);
      audioPlayerRef.current.src = blobUrl;
      // REQUIREMENT 6: Audio khatam → flag reset → mic on hoga
      await new Promise((resolve) => {
        audioPlayerRef.current.onended = () => { if (isMounted.current) setAudioPlaying(false); resolve(); };
        audioPlayerRef.current.onerror = () => { if (isMounted.current) setAudioPlaying(false); resolve(); };
        audioPlayerRef.current.play().catch(() => { if (isMounted.current) setAudioPlaying(false); resolve(); });
      });
    } catch (e) {
      if (isMounted.current) setAudioPlaying(false);
      console.error('Audio play failed:', e);
    }
  }, []);

  const playSequential = useCallback(async (urls) => {
    const blobs = [];
    const currentId = ++playbackIdRef.current;
    setAudioPlaying(true);
    for (const url of urls) {
      if (!isMounted.current || playbackIdRef.current !== currentId) break;
      try {
        const blobUrl = await fetchAudioBlob(url);
        if (!isMounted.current || playbackIdRef.current !== currentId) break;
        blobs.push(blobUrl);
        audioPlayerRef.current.src = blobUrl;
        await new Promise((resolve) => {
          audioPlayerRef.current.onended = resolve;
          audioPlayerRef.current.onerror = resolve;
          audioPlayerRef.current.play().catch(resolve);
        });
      } catch (e) { blobs.push(null); }
    }
    if (isMounted.current && playbackIdRef.current === currentId) setAudioPlaying(false);
    return blobs;
  }, []);

  const handleRecordingComplete = useCallback(async (audioBlob) => {
    if (!session.id) return;
    setIsProcessing(true);
    try {
      if (session.state === 'CONFIRMING_SERVICE_NUMBER') {
        const res = await submitConfirmAudio(session.id, audioBlob);
        if (!isMounted.current) return;
        setSession(prev => ({ ...prev, state: res.data.state, transcript: res.data.recognized_text, promptText: res.data.prompt_text, language: res.data.stt_language, latency: res.data.stt_processing_time_ms }));
        if (res.data.state === 'CAPTURING_COMPLAINT') await playAudio(`http://127.0.0.1:8001/api/voice/prompt/ask_complaint`);
        else if (res.data.state === 'CAPTURING_SERVICE_NUMBER') await playAudio(`http://127.0.0.1:8001/api/voice/prompt/ask_service_number`);

      } else if (session.state === 'CAPTURING_SERVICE_NUMBER') {
        const res = await submitServiceNumberAudio(session.id, audioBlob);
        if (!isMounted.current) return;
        setSession(prev => ({ ...prev, state: res.data.state, transcript: res.data.recognized_text, serviceNumber: res.data.normalised_service_no, confidence: res.data.confidence, language: res.data.stt_language, latency: res.data.stt_processing_time_ms, promptText: res.data.prompt_text }));
        if (res.data.state === 'CONFIRMING_SERVICE_NUMBER' && res.data.is_valid) {
          const BASE = 'http://127.0.0.1:8001/api/voice';
          const blobs = await playSequential([`${BASE}/prompt/heard_as`, `${BASE}/spell/${encodeURIComponent(res.data.normalised_service_no)}`, `${BASE}/prompt/is_that_correct`, `${BASE}/prompt/confirm_yes_no`]);
          confirmBlobsRef.current = blobs;
        } else if (res.data.state === 'CAPTURING_SERVICE_NUMBER') {
          await playAudio(`http://127.0.0.1:8001/api/voice/prompt/retry_service`);
        } else if (res.data.state === 'OPERATOR_FALLBACK') {
          await playAudio(`http://127.0.0.1:8001/api/voice/prompt/fallback_operator`);
        }

      } else if (session.state === 'CAPTURING_COMPLAINT') {
        const res = await submitComplaintAudio(session.id, audioBlob);
        if (!isMounted.current) return;
        setSession(prev => ({ ...prev, state: res.data.state, transcript: res.data.transcript, confidence: res.data.confidence, language: res.data.stt_language, latency: res.data.stt_processing_time_ms, promptText: res.data.prompt_text }));
        if (res.data.state === 'OPERATOR_REVIEW') {
          onClassificationComplete({ intake_id: res.data.intake_id, is_repeat_caller: false, potential_duplicates: [], fault_type_proposal: res.data.fault_type_proposal, severity_proposal: res.data.severity_proposal, candidates: res.data.candidates }, { raw_text: res.data.transcript, complainant_service_no: session.serviceNumber, complainant_name: '', complainant_unit: '', complainant_rank: '', voice_session_id: session.id });
        } else if (res.data.state === 'CAPTURING_COMPLAINT') {
          await playAudio(`http://127.0.0.1:8001/api/voice/tts?text=${encodeURIComponent(res.data.prompt_text)}`);
        }

      } else if (session.state === 'ASK_ANOTHER_COMPLAINT') {
        // R-42: "koi aur complaint hai?" — loop for another ticket, or end the call.
        const res = await submitAnotherComplaintAudio(session.id, audioBlob);
        if (!isMounted.current) return;
        setSession(prev => ({ ...prev, state: res.data.state, transcript: res.data.recognized_text, promptText: res.data.prompt_text, language: res.data.stt_language, latency: res.data.stt_processing_time_ms }));
        if (res.data.wants_another === true) {
          await playAudio(`${VOICE_API_BASE}/prompt/ask_service_number`);
        } else if (res.data.wants_another === false) {
          await playAudio(`${VOICE_API_BASE}/prompt/goodbye`);
          if (onCallEnded) onCallEnded();
        } else {
          await playAudio(`${VOICE_API_BASE}/tts?text=${encodeURIComponent(res.data.prompt_text)}`);
        }
      }
    } catch (err) {
      console.error(err);
      if (isMounted.current) setSession(prev => ({ ...prev, state: 'ERROR', promptText: 'Error occurred. Please try again.' }));
    } finally {
      if (isMounted.current) setIsProcessing(false);
    }
  }, [session.id, session.state, session.serviceNumber, playAudio, playSequential, onClassificationComplete, onCallEnded]);

  const handleManualConfirm = async (confirmed) => {
    setIsProcessing(true);
    try {
      const res = await confirmServiceNumber(session.id, confirmed);
      setSession(prev => ({ ...prev, state: res.data.state, promptText: res.data.prompt_text, transcript: '' }));
      if (confirmed) await playAudio(`http://127.0.0.1:8001/api/voice/prompt/ask_complaint`);
      else await playAudio(`http://127.0.0.1:8001/api/voice/prompt/ask_service_number`);
    } catch (err) { console.error(err); }
    finally { setIsProcessing(false); }
  };

  const handleReplay = () => {
    const blobs = confirmBlobsRef.current.filter(Boolean);
    if (!blobs.length) return;
    let idx = 0;
    setAudioPlaying(true);
    const player = audioPlayerRef.current;
    player.pause();
    const playNext = () => {
      if (idx >= blobs.length) { setAudioPlaying(false); return; }
      player.src = blobs[idx++];
      player.onended = playNext;
      player.play().catch(playNext);
    };
    playNext();
  };

  const handleFallbackSubmit = async () => {
    if (!fallbackData.service_no.trim()) return;
    if (!/^\d{5}$/.test(fallbackData.service_no.trim())) { toast.error('Service number must be 5 digits.'); return; }
    setIsProcessing(true);
    try {
      const res = await submitFallback(session.id, fallbackData);
      setSession(prev => ({ ...prev, state: res.data.state, promptText: res.data.prompt_text, serviceNumber: res.data.service_no, transcript: '' }));
      await playAudio(`http://127.0.0.1:8001/api/voice/prompt/ask_complaint`);
    } catch (err) { console.error(err); }
    finally { setIsProcessing(false); }
  };

  const audioActiveStates = ['CAPTURING_SERVICE_NUMBER', 'CAPTURING_COMPLAINT', 'CONFIRMING_SERVICE_NUMBER', 'OPERATOR_REVIEW', 'ASK_ANOTHER_COMPLAINT'];
  const showRecorder = greetingDoneRef.current && !session.livekitEnabled && audioActiveStates.includes(session.state);
  const showLiveKit  = greetingDoneRef.current && session.livekitEnabled && audioActiveStates.includes(session.state);

  const handleLiveKitStateChange = useCallback((data) => {
    setIsProcessing(false);
    setSession(prev => ({
      ...prev,
      state: data.state || prev.state,
      transcript: data.transcript || prev.transcript,
      promptText: data.prompt_text || prev.promptText,
      serviceNumber: data.service_no || prev.serviceNumber,
      confidence: data.stt_confidence ?? data.confidence ?? prev.confidence,
      language: data.stt_language || prev.language,
      latency: data.stt_processing_time_ms ?? prev.latency,
    }));

    if (data.state === 'OPERATOR_REVIEW') {
      onClassificationComplete(
        {
          intake_id: data.intake_id,
          is_repeat_caller: false,
          potential_duplicates: [],
          fault_type_proposal: data.fault_type_proposal,
          severity_proposal: data.severity_proposal,
          candidates: data.candidates || [],
        },
        {
          raw_text: data.transcript,
          complainant_service_no: session.serviceNumber,
          complainant_name: '',
          complainant_unit: '',
          complainant_rank: '',
          voice_session_id: session.id,
        }
      );
    } else if (data.state === 'COMPLETED') {
      if (onCallEnded) onCallEnded();
    }
  }, [onClassificationComplete, onCallEnded, session.serviceNumber, session.id]);

  const handleLiveKitTranscribed = useCallback((data) => {
    setSession(prev => ({ ...prev, transcript: data.text, confidence: data.confidence, language: data.language }));
  }, []);

  const handleLiveKitError = useCallback((data) => {
    setIsProcessing(false);
    setSession(prev => ({ ...prev, state: 'ERROR', promptText: data.detail || 'An error occurred' }));
  }, []);

  return (
    <div style={{ background: '#0d1b2e', border: '1px solid rgba(30,144,255,0.3)', borderRadius: 14, padding: 20, marginBottom: 24, boxShadow: '0 0 20px rgba(30,144,255,0.1)' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
        <span style={{ fontSize: '0.72rem', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--accent, #1E90FF)', background: 'rgba(30,144,255,0.1)', padding: '4px 10px', borderRadius: 20, border: '1px solid rgba(30,144,255,0.2)' }}>
          {session.state.replace(/_/g, ' ')}
        </span>
        <button onClick={onCancel} style={{ background: 'none', border: 'none', color: '#4d6480', cursor: 'pointer', fontSize: '0.82rem' }}>✕ Cancel</button>
      </div>

      {lastTicketNumber && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, background: 'rgba(34,197,94,0.08)', border: '1px solid rgba(34,197,94,0.2)', borderRadius: 8, padding: '8px 14px', marginBottom: 16, fontSize: '0.82rem', color: '#22c55e' }}>
          ✓ Ticket <strong style={{ fontFamily: 'monospace' }}>{lastTicketNumber}</strong> created. Continuing the same call...
        </div>
      )}

      {/* Prompt */}
      <div style={{ background: 'rgba(10,22,40,0.8)', borderLeft: '3px solid #1E90FF', borderRadius: '0 8px 8px 0', padding: '12px 16px', marginBottom: 16 }}>
        <span style={{ fontSize: '0.7rem', color: '#4d6480', textTransform: 'uppercase', letterSpacing: '0.06em', display: 'block', marginBottom: 6 }}>System</span>
        <p style={{ fontSize: '0.92rem', fontWeight: 500, color: '#e8edf5', margin: 0 }}>{session.promptText}</p>

        {session.state === 'OPERATOR_FALLBACK' && (
          <div style={{ marginTop: 14, paddingTop: 14, borderTop: '1px solid rgba(255,255,255,0.06)' }}>
            <p style={{ fontSize: '0.8rem', color: '#ef4444', marginBottom: 10 }}>Max retries exceeded. Enter manually.</p>
            <div style={{ display: 'flex', gap: 8 }}>
              <input type="text" placeholder="e.g. 12345" value={fallbackData.service_no} onChange={e => setFallbackData(p => ({ ...p, service_no: e.target.value }))} style={{ padding: '8px 12px', background: '#0f2040', border: '1px solid rgba(30,144,255,0.2)', borderRadius: 8, color: '#e8edf5', fontSize: '0.875rem', outline: 'none', width: 140 }} />
              <button onClick={handleFallbackSubmit} style={{ background: '#1E90FF', color: 'white', border: 'none', padding: '8px 16px', borderRadius: 8, cursor: 'pointer', fontSize: '0.875rem' }}>Submit</button>
            </div>
          </div>
        )}

        {session.state === 'CONFIRMING_SERVICE_NUMBER' && (
          <div style={{ marginTop: 14, paddingTop: 14, borderTop: '1px solid rgba(255,255,255,0.06)' }}>
            <p style={{ fontSize: '0.82rem', color: '#8fa3c0', marginBottom: 10 }}>
              Did the caller say: <strong style={{ color: '#1E90FF', fontFamily: 'monospace' }}>{session.serviceNumber}</strong>?
            </p>
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={() => handleManualConfirm(true)} style={{ background: '#1E90FF', color: 'white', border: 'none', padding: '7px 14px', borderRadius: 8, cursor: 'pointer', fontSize: '0.82rem' }}>✓ Yes</button>
              <button onClick={() => handleManualConfirm(false)} style={{ background: 'rgba(255,255,255,0.06)', color: '#e8edf5', border: '1px solid rgba(255,255,255,0.1)', padding: '7px 14px', borderRadius: 8, cursor: 'pointer', fontSize: '0.82rem' }}>✗ Retry</button>
              <button onClick={handleReplay} style={{ background: 'rgba(34,197,94,0.1)', color: '#22c55e', border: '1px solid rgba(34,197,94,0.2)', padding: '7px 14px', borderRadius: 8, cursor: 'pointer', fontSize: '0.82rem' }}>🔊 Replay</button>
            </div>
          </div>
        )}
      </div>

      {/* Audio playing indicator */}
      {audioPlaying && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, background: 'rgba(30,144,255,0.06)', border: '1px solid rgba(30,144,255,0.15)', borderRadius: 8, padding: '8px 14px', marginBottom: 12, fontSize: '0.82rem', color: '#1E90FF' }}>
          <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#1E90FF', animation: 'pulse 1s infinite' }}></div>
          Speaking... (say something to interrupt)
        </div>
      )}

      {/* Recorder (legacy record/upload) or LiveKit real-time transport */}
      {showRecorder && (
        <VoiceRecorder
          onRecordingComplete={handleRecordingComplete}
          onRecordingStart={handleRecordingStart}
          isProcessing={isProcessing}
          audioPlaying={audioPlaying}
        />
      )}

      {showLiveKit && (
        <LiveKitAudioTransport
          session_id={session.id}
          livekit_token={session.livekitToken}
          livekit_url={session.livekitUrl}
          onStateChange={handleLiveKitStateChange}
          onTranscribed={handleLiveKitTranscribed}
          onProcessing={() => setIsProcessing(true)}
          onError={handleLiveKitError}
        />
      )}

      {session.state === 'INIT' && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '12px 0' }}>
          <div style={{ width: 18, height: 18, border: '2px solid rgba(30,144,255,0.2)', borderTop: '2px solid #1E90FF', borderRadius: '50%', animation: 'spin 0.7s linear infinite' }}></div>
          <span style={{ fontSize: '0.875rem', color: '#4d6480' }}>Initializing...</span>
        </div>
      )}

      {session.state === 'COMPLETED' && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '12px 0' }}>
          <span style={{ fontSize: '0.875rem', color: '#22c55e' }}>✓ Call ended.</span>
        </div>
      )}

      <TranscriptPanel transcript={session.transcript} confidence={session.confidence} language={session.language} processingTimeMs={session.latency} state={session.state} />
    </div>
  );
}

export default VoiceSessionPanel;
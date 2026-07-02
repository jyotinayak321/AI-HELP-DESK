import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  startVoiceSession,
  submitServiceNumberAudio,
  submitComplaintAudio,
  confirmServiceNumber,
  submitConfirmAudio,
  submitFallback,
  fetchAudioBlob
} from '../../api/voice.api';
import { useCurrentUser } from '../../useCurrentUser';
import VoiceRecorder from './VoiceRecorder';
import TranscriptPanel from './TranscriptPanel';

/**
 * VoiceSessionPanel Component
 *
 * Orchestrates the full voice session state machine.
 *
 * WebSocket lifecycle ownership:
 *  - The WS is opened once when sessionId becomes available.
 *  - It stays open until the session ends or the component unmounts.
 *  - `isListening` only controls whether audio chunks are forwarded to the WS.
 *    It does NOT tear down or re-create the WS.
 */
function VoiceSessionPanel({ onClassificationComplete, onCancel }) {
  const { serviceNo } = useCurrentUser();

  const [isListening, setIsListening] = useState(false);
  const [vadState, setVadState] = useState('inactive'); // 'inactive' | 'listening' | 'speaking' | 'processing'
  const [session, setSession] = useState({
    id: null,
    state: 'INIT',
    promptText: 'Starting voice session...',
    transcript: '',
    serviceNumber: '',
    confidence: 0,
    language: '',
    latency: 0,
    retries: 0,
  });
  const [isProcessing, setIsProcessing] = useState(false);
  const [fallbackData, setFallbackData] = useState({ service_no: '' });
  // Holds the OPERATOR_REVIEW result until the user confirms or re-records
  const [pendingReview, setPendingReview] = useState(null); // { transcript, intakeData, complaintMeta, ttsUrl }
  const [editedTranscript, setEditedTranscript] = useState('');

  // ── Stable refs (survive re-renders) ───────────────────────────────────
  const isMounted = useRef(true);
  const playbackIdRef = useRef(0);
  const confirmSequenceRef = useRef([]);
  const audioPlayerRef = useRef(new Audio());

  // WebSocket / Audio pipeline refs — NEVER recreated on state change
  const wsRef = useRef(null);
  const audioContextRef = useRef(null);
  const processorRef = useRef(null);
  const micStreamRef = useRef(null);
  const isListeningRef = useRef(false); // mirror of isListening for use inside closures

  // Keep ref in sync with state so the onaudioprocess closure reads the latest value
  useEffect(() => { isListeningRef.current = isListening; }, [isListening]);

  // ── Linear-interpolation resampler ─────────────────────────────────────
  const resample = (buf, fromRate, toRate) => {
    if (fromRate === toRate) return buf;
    const ratio = fromRate / toRate;
    const newLen = Math.round(buf.length / ratio);
    const out = new Float32Array(newLen);
    for (let i = 0; i < newLen; i++) {
      const idx = i * ratio;
      const lo = Math.floor(idx);
      const hi = Math.min(buf.length - 1, lo + 1);
      out[i] = buf[lo] * (1 - (idx - lo)) + buf[hi] * (idx - lo);
    }
    return out;
  };

  // ── Open WebSocket and AudioContext exactly once ────────────────────────
  const openStreamingPipeline = useCallback((sessionId, operatorId) => {
    if (wsRef.current) return; // Already open

    const wsUrl = `ws://127.0.0.1:8000/api/voice/stream?session_id=${sessionId}&operator_id=${operatorId}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = async () => {
      console.log('[VAD] WebSocket connected');
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        micStreamRef.current = stream;

        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        audioContextRef.current = ctx;

        const source = ctx.createMediaStreamSource(stream);
        const processor = ctx.createScriptProcessor(4096, 1, 1);
        processorRef.current = processor;

        processor.onaudioprocess = (e) => {
          // Only forward audio when the user should be speaking
          if (!isListeningRef.current) return;
          if (ws.readyState !== WebSocket.OPEN) return;

          const raw = e.inputBuffer.getChannelData(0);
          const resampled = resample(raw, ctx.sampleRate, 16000);
          ws.send(resampled.buffer);
        };

        source.connect(processor);
        processor.connect(ctx.destination);
      } catch (err) {
        console.error('[VAD] Microphone error:', err);
      }
    };

    ws.onmessage = (event) => {
      let msg;
      try { msg = JSON.parse(event.data); } catch { return; }

      if (msg.event === 'speech_started') {
        setVadState('speaking');
      } else if (msg.event === 'speech_ended') {
        setVadState('processing');
      } else if (msg.event === 'result') {
        setVadState('inactive'); // will switch to listening after TTS
        if (handleVADResultRef.current) handleVADResultRef.current(msg);
      } else if (msg.event === 'error') {
        console.error('[VAD] Server error:', msg.message);
        if (isMounted.current) {
          setSession(prev => ({ ...prev, state: 'ERROR', promptText: msg.message }));
        }
      }
    };

    ws.onerror = (e) => {
      console.error('[VAD] WebSocket error:', e);
    };

    ws.onclose = (ev) => {
      console.warn('[VAD] WebSocket closed:', ev.code, ev.reason);
      wsRef.current = null;
      // Attempt reconnect only if the session is still active
      if (isMounted.current && sessionId) {
        setTimeout(() => {
          if (isMounted.current && !wsRef.current) {
            console.log('[VAD] Reconnecting...');
            openStreamingPipeline(sessionId, operatorId);
          }
        }, 1500);
      }
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Tear down pipeline on unmount ──────────────────────────────────────
  useEffect(() => {
    isMounted.current = true;
    initSession();

    return () => {
      isMounted.current = false;
      playbackIdRef.current++;
      if (audioPlayerRef.current) {
        audioPlayerRef.current.pause();
        audioPlayerRef.current.src = '';
      }
      // Tear down streaming resources
      if (processorRef.current) { processorRef.current.disconnect(); processorRef.current = null; }
      if (audioContextRef.current) { audioContextRef.current.close().catch(() => {}); audioContextRef.current = null; }
      if (micStreamRef.current) { micStreamRef.current.getTracks().forEach(t => t.stop()); micStreamRef.current = null; }
      if (wsRef.current) { wsRef.current.close(); wsRef.current = null; }
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Open pipeline once sessionId is known ──────────────────────────────
  useEffect(() => {
    if (session.id && serviceNo) {
      openStreamingPipeline(session.id, serviceNo);
    }
  }, [session.id, serviceNo, openStreamingPipeline]);

  // ── Keep vadState in sync with isListening ─────────────────────────────
  useEffect(() => {
    if (isListening) {
      setVadState('listening');
    }
    // When isListening goes false and we're currently in 'listening', switch to 'inactive'
    if (!isListening && vadState === 'listening') {
      setVadState('inactive');
    }
  }, [isListening]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Audio playback helpers ─────────────────────────────────────────────
  const stopAllAudio = () => {
    playbackIdRef.current++;
    const player = audioPlayerRef.current;
    if (player) {
      player.pause();
      player.currentTime = 0;
      player.src = '';
    }
  };

  const playAudio = async (url) => {
    if (!url) return null;
    const currentId = ++playbackIdRef.current;
    try {
      const player = audioPlayerRef.current;
      // Fully reset player before changing src to prevent AbortError
      player.pause();
      player.src = '';
      await new Promise(r => setTimeout(r, 30)); // let the browser settle

      if (!isMounted.current || playbackIdRef.current !== currentId) return null;

      const blobUrl = await fetchAudioBlob(url);
      if (!isMounted.current || playbackIdRef.current !== currentId) return null;

      return new Promise((resolve, reject) => {
        player.src = blobUrl;
        player.onended = () => resolve(blobUrl);
        player.onerror = (e) => reject(e);
        player.play().catch(err => {
          if (playbackIdRef.current === currentId) reject(err);
          else resolve(null); // aborted by a newer play — that's fine
        });
      });
    } catch (e) {
      if (isMounted.current && playbackIdRef.current === currentId) {
        console.error('[Audio] playAudio failed:', e);
      }
      return null;
    }
  };

  const playSequential = async (urls) => {
    const player = audioPlayerRef.current;
    const blobs = [];
    const currentId = ++playbackIdRef.current;

    // Reset player state cleanly before starting a sequence
    player.pause();
    player.src = '';
    await new Promise(r => setTimeout(r, 30));

    for (const url of urls) {
      if (!isMounted.current || playbackIdRef.current !== currentId) break;
      try {
        const blobUrl = await fetchAudioBlob(url);
        if (!isMounted.current || playbackIdRef.current !== currentId) break;
        blobs.push(blobUrl);
        player.src = blobUrl;
        await new Promise((resolve, reject) => {
          player.onended = resolve;
          player.onerror = reject;
          player.play().catch(err => {
            if (playbackIdRef.current !== currentId) resolve(); // interrupted — ok
            else reject(err);
          });
        });
      } catch (e) {
        if (playbackIdRef.current !== currentId) break;
        console.error('[Audio] sequential failed at:', url, e);
        blobs.push(null);
      }
    }
    return blobs;
  };

  // ── Session init ───────────────────────────────────────────────────────
  const initSession = async () => {
    setIsProcessing(true);
    setIsListening(false);
    try {
      const res = await startVoiceSession();
      if (!isMounted.current) return;
      setSession(prev => ({
        ...prev,
        id: res.data.session_id,
        state: res.data.state,
        promptText: res.data.prompt_text,
      }));
      playAudio(`http://127.0.0.1:8000/api/voice/prompt/greeting`).then(() => {
        if (isMounted.current) {
          setIsListening(true);
          setIsProcessing(false);
        }
      });
    } catch (err) {
      console.error(err);
      if (isMounted.current) {
        setSession(prev => ({ ...prev, state: 'ERROR', promptText: 'Failed to start voice session.' }));
        setIsProcessing(false);
      }
    }
  };

  // ── VAD result handler (called from ws.onmessage) ──────────────────────
  // NOTE: Must be a stable function reference (defined outside ws.onopen) because it's
  // called from the closure inside ws.onmessage. We use a ref-forwarded version.
  const handleVADResultRef = useRef(null);

  const handleVADResult = (msg) => {
    if (!isMounted.current) return;
    
    // Prevent stale WS messages from moving the UI backward after a successful fallback submit
    let ignoreMessage = false;

    setSession(prev => {
      if (prev.state === 'CAPTURING_COMPLAINT' && msg.state === 'OPERATOR_FALLBACK') {
        ignoreMessage = true;
        return prev;
      }
      return {
        ...prev,
        state: msg.state,
        transcript: msg.transcript || msg.recognized_text || '',
        serviceNumber: msg.normalised_service_no || prev.serviceNumber,
        confidence: msg.confidence || 0,
        language: msg.stt_language || '',
        latency: msg.stt_processing_time_ms || 0,
        promptText: msg.prompt_text,
        retries: msg.retries_count !== undefined ? msg.retries_count : prev.retries,
        intakeId: msg.intake_id || prev.intakeId,
      };
    });

    if (ignoreMessage) return;

    if (msg.state === 'OPERATOR_REVIEW') {
      const genericPrompt = 'Please review your transcribed complaint before submitting.';
      const localTtsUrl = `http://127.0.0.1:8000/api/voice/tts?text=${encodeURIComponent(genericPrompt)}`;
      const dashboardTtsUrl = `http://127.0.0.1:8000/api/voice/tts?text=${encodeURIComponent(msg.prompt_text)}`;
      const transcript = msg.transcript || '';

      // Store classification result for user review — do NOT call onClassificationComplete yet
      setPendingReview({
        transcript,
        ttsUrl: dashboardTtsUrl,
        intakeData: {
          intake_id: msg.intake_id,
          is_repeat_caller: false,
          potential_duplicates: [],
          fault_type_proposal: msg.fault_type_proposal,
          severity_proposal: msg.severity_proposal,
          candidates: msg.candidates,
        },
        complaintMeta: {
          raw_text: transcript,
          complainant_service_no: msg.normalised_service_no || session.serviceNumber || '',
          complainant_name: '',
          complainant_unit: '',
          complainant_rank: '',
        },
        confidence: msg.confidence || 0,
        language: msg.stt_language || '',
        latency: msg.stt_processing_time_ms || 0,
      });
      setEditedTranscript(transcript);
      setIsListening(false);
      setIsProcessing(false);
      setVadState('inactive');

      // Play the generic instruction TTS locally
      playAudio(localTtsUrl);
      return;
    }

    if (msg.audio_urls && msg.audio_urls.length > 0) {
      setIsListening(false);
      setIsProcessing(true);
      const absoluteUrls = msg.audio_urls.map(u => `http://127.0.0.1:8000${u}`);

      const afterPlay = (blobs) => {
        if (!isMounted.current) return;
        if (msg.state === 'CONFIRMING_SERVICE_NUMBER') confirmSequenceRef.current = blobs;
        
        // Do not resume listening if we are in fallback - the user must type
        if (msg.state === 'OPERATOR_FALLBACK') {
          setIsListening(false);
        } else {
          setIsListening(true);
        }
        setIsProcessing(false);
      };

      playSequential(absoluteUrls).then(afterPlay);
    } else {
      if (msg.state === 'OPERATOR_FALLBACK') {
        setIsListening(false);
      } else {
        setIsListening(true);
      }
      setIsProcessing(false);
    }
  };

  // Keep the ref in sync so ws.onmessage always calls the latest version
  handleVADResultRef.current = handleVADResult;

  // ── Legacy (push-to-talk) recording handler ────────────────────────────
  const handleRecordingComplete = async (audioBlob) => {
    if (!session.id) return;
    setIsProcessing(true);
    setIsListening(false);

    try {
      if (session.state === 'CONFIRMING_SERVICE_NUMBER') {
        const res = await submitConfirmAudio(session.id, audioBlob);
        setSession(prev => ({
          ...prev,
          state: res.data.state,
          transcript: res.data.recognized_text,
          promptText: res.data.prompt_text,
          language: res.data.stt_language,
          latency: res.data.stt_processing_time_ms,
        }));
        if (res.data.state === 'CAPTURING_COMPLAINT') {
          playAudio(`http://127.0.0.1:8000/api/voice/prompt/ask_complaint`).then(() => {
            if (isMounted.current) { setIsListening(true); setIsProcessing(false); }
          });
        } else if (res.data.state === 'CAPTURING_SERVICE_NUMBER') {
          playAudio(`http://127.0.0.1:8000/api/voice/prompt/ask_service_number`).then(() => {
            if (isMounted.current) { setIsListening(true); setIsProcessing(false); }
          });
        } else {
          handleReplayServiceNumber();
        }
      } else if (session.state === 'CAPTURING_SERVICE_NUMBER') {
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
          retries: res.data.retries_count,
        }));
        if (res.data.state === 'CONFIRMING_SERVICE_NUMBER' && res.data.is_valid) {
          const BASE = 'http://127.0.0.1:8000/api/voice';
          const sequence = [
            `${BASE}/prompt/heard_as`,
            `${BASE}/spell/${encodeURIComponent(res.data.normalised_service_no)}`,
            `${BASE}/prompt/is_that_correct`,
            `${BASE}/prompt/confirm_yes_no`,
          ];
          playSequential(sequence).then(blobs => {
            if (isMounted.current) {
              confirmSequenceRef.current = blobs;
              setIsListening(true); setIsProcessing(false);
            }
          });
        } else if (res.data.state === 'CAPTURING_SERVICE_NUMBER') {
          playAudio(`http://127.0.0.1:8000/api/voice/prompt/retry_service`).then(() => {
            if (isMounted.current) { setIsListening(true); setIsProcessing(false); }
          });
        } else if (res.data.state === 'OPERATOR_FALLBACK') {
          playAudio(`http://127.0.0.1:8000/api/voice/prompt/fallback_operator`).then(() => {
            if (isMounted.current) { setIsListening(true); setIsProcessing(false); }
          });
        }
      } else if (session.state === 'CAPTURING_COMPLAINT' || session.state === 'OPERATOR_REVIEW') {
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
          const ttsUrl = `http://127.0.0.1:8000/api/voice/tts?text=${encodeURIComponent(res.data.prompt_text)}`;
          onClassificationComplete(
            {
              intake_id: res.data.intake_id,
              is_repeat_caller: false,
              potential_duplicates: [],
              fault_type_proposal: res.data.fault_type_proposal,
              severity_proposal: res.data.severity_proposal,
              candidates: res.data.candidates,
            },
            {
              raw_text: res.data.transcript,
              complainant_service_no: session.serviceNumber,
              complainant_name: '', complainant_unit: '', complainant_rank: '',
            },
            ttsUrl
          );
        } else if (res.data.state === 'CAPTURING_COMPLAINT') {
          playAudio(`http://127.0.0.1:8000/api/voice/tts?text=${encodeURIComponent(res.data.prompt_text)}`).then(() => {
            if (isMounted.current) { setIsListening(true); setIsProcessing(false); }
          });
        }
      }
    } catch (err) {
      console.error(err);
      if (isMounted.current) {
        setSession(prev => ({ ...prev, state: 'ERROR', promptText: 'An error occurred during audio processing.' }));
        setIsProcessing(false);
      }
    }
  };

  // ── Service number UI handlers ─────────────────────────────────────────
  const handleServiceNumberConfirm = async (confirmed) => {
    setIsProcessing(true);
    setIsListening(false);
    try {
      const res = await confirmServiceNumber(session.id, confirmed);
      setSession(prev => ({
        ...prev,
        state: res.data.state,
        promptText: res.data.prompt_text,
        transcript: '',
      }));
      const promptKey = confirmed ? 'ask_complaint' : 'ask_service_number';
      playAudio(`http://127.0.0.1:8000/api/voice/prompt/${promptKey}`).then(() => {
        if (isMounted.current) { setIsListening(true); setIsProcessing(false); }
      });
    } catch (err) {
      console.error(err);
      if (isMounted.current) {
        setSession(prev => ({ ...prev, state: 'ERROR', promptText: 'Error confirming service number.' }));
        setIsProcessing(false);
      }
    }
  };

  const handleReplayServiceNumber = () => {
    const blobs = confirmSequenceRef.current.filter(Boolean);
    if (!blobs.length) return;
    setIsListening(false);
    const player = audioPlayerRef.current;
    let idx = 0;
    const playNext = () => {
      if (idx >= blobs.length) { setIsListening(true); return; }
      player.src = blobs[idx++];
      player.onended = playNext;
      player.play().catch(e => { console.error(e); setIsListening(true); });
    };
    player.pause();
    playNext();
  };

  const handleFallbackSubmit = async () => {
    const raw = fallbackData.service_no.trim();
    if (!raw) { alert('Please enter a service number.'); return; }
    // Accept: 2–8 digits followed by exactly 1 letter (e.g. 345O, 2893456P)
    const svcPattern = /^\d{2,8}[a-zA-Z]$/;
    if (!svcPattern.test(raw)) {
      alert('Service number must be digits followed by one letter (e.g. 345O or 2893456P).');
      return;
    }
    setIsProcessing(true);
    setIsListening(false);
    try {
      const res = await submitFallback(session.id, fallbackData);
      setSession(prev => ({
        ...prev,
        state: res.data.state,
        promptText: res.data.prompt_text,
        serviceNumber: res.data.service_no,
        transcript: '',
      }));
      playAudio(`http://127.0.0.1:8000/api/voice/prompt/ask_complaint`).then(() => {
        if (isMounted.current) { setIsListening(true); setIsProcessing(false); }
      }).catch(() => {
        // Even if audio fails, resume listening so user can speak the complaint
        if (isMounted.current) { setIsListening(true); setIsProcessing(false); }
      });
    } catch (err) {
      console.error(err);
      if (isMounted.current) setIsProcessing(false);
    }
  };

  // ── Complaint review handlers ──────────────────────────────────────────
  const handleConfirmComplaint = () => {
    if (!pendingReview) return;
    const finalMeta = {
      ...pendingReview.complaintMeta,
      raw_text: editedTranscript.trim() || pendingReview.transcript,
    };
    onClassificationComplete(pendingReview.intakeData, finalMeta, pendingReview.ttsUrl);
  };

  const handleRerecordComplaint = () => {
    setPendingReview(null);
    setEditedTranscript('');
    // session.state is already OPERATOR_REVIEW on backend — VAD accepts re-recording in that state
    setSession(prev => ({ ...prev, promptText: 'Please describe your complaint clearly.' }));
    playAudio('http://127.0.0.1:8000/api/voice/prompt/ask_complaint').then(() => {
      if (isMounted.current) { setIsListening(true); setIsProcessing(false); }
    });
  };

  // ── Render ─────────────────────────────────────────────────────────────
  const showRecorder = !pendingReview && ['CAPTURING_SERVICE_NUMBER', 'CONFIRMING_SERVICE_NUMBER', 'CAPTURING_COMPLAINT', 'OPERATOR_REVIEW'].includes(session.state);

  return (
    <div style={panelContainerStyle}>
      <div style={headerStyle}>
        <div style={statusBadgeStyle(pendingReview ? 'REVIEWING' : session.state)}>
          Status: {pendingReview ? 'REVIEW COMPLAINT' : session.state.replace(/_/g, ' ')}
        </div>
        <button onClick={onCancel} style={cancelBtnStyle}>✕ Cancel Voice Mode</button>
      </div>

      {/* ── Complaint Review Screen ─────────────────────────────────── */}
      {pendingReview && (
        <div style={reviewBoxStyle}>
          <div style={reviewHeaderStyle}>
            <span style={{ fontSize: '16px' }}>📝</span>
            <span style={{ fontWeight: 700, fontSize: '15px', color: '#1e293b' }}>Review &amp; Confirm Complaint</span>
            {pendingReview.confidence > 0 && (
              <span style={confidenceBadgeStyle(pendingReview.confidence)}>
                {Math.round(pendingReview.confidence * 100)}% confidence
              </span>
            )}
          </div>

          <p style={{ margin: '0 0 8px 0', fontSize: '12px', color: '#64748b' }}>
            Transcribed from voice — you can edit before submitting.
          </p>

          <textarea
            value={editedTranscript}
            onChange={e => setEditedTranscript(e.target.value)}
            rows={5}
            style={reviewTextareaStyle}
            placeholder="Complaint text..."
          />

          {pendingReview.language && (
            <p style={{ margin: '4px 0 0 0', fontSize: '11px', color: '#94a3b8' }}>
              Detected language: <strong>{pendingReview.language.toUpperCase()}</strong>
              {pendingReview.latency > 0 && ` • STT: ${pendingReview.latency}ms`}
            </p>
          )}

          <div style={{ display: 'flex', gap: '12px', marginTop: '16px', flexWrap: 'wrap' }}>
            <button onClick={handleConfirmComplaint} style={btnConfirmStyle}>
              ✅ Confirm &amp; Submit
            </button>
            <button onClick={handleRerecordComplaint} style={btnRerecordStyle}>
              🔄 Re-record Complaint
            </button>
          </div>
        </div>
      )}

      {!pendingReview && <div style={promptBoxStyle}>
        <span style={{ fontSize: '12px', color: '#64748b', fontWeight: 600, display: 'block', marginBottom: '8px' }}>System Prompt:</span>
        <p style={{ margin: 0, fontSize: '15px', fontWeight: 500, color: '#1e293b' }}>{session.promptText}</p>

        {session.state === 'OPERATOR_FALLBACK' && (
          <div style={fallbackBoxStyle}>
            <p style={{ margin: '0 0 10px 0', fontSize: '13px', color: '#e24b4a' }}>Maximum retries exceeded. Please enter service number manually.</p>
            <input
              type="text"
              placeholder="e.g. 345O or 2893456P"
              value={fallbackData.service_no}
              onChange={e => setFallbackData(prev => ({ ...prev, service_no: e.target.value }))}
              style={inputStyle}
            />
            <button onClick={handleFallbackSubmit} style={btnPrimaryStyle}>Submit &amp; Continue</button>
          </div>
        )}

        {session.state === 'CONFIRMING_SERVICE_NUMBER' && (
          <div style={confirmBoxStyle}>
            <p style={{ margin: '0 0 6px 0', fontSize: '14px', fontWeight: 500 }}>
              Heard: <strong style={{ color: '#185FA5' }}>{session.serviceNumber}</strong>
            </p>
            <p style={{ margin: '0 0 12px 0', fontSize: '13px', color: '#475569' }}>
              🎙️ <em>Please say <strong>"Yes"</strong> to confirm or <strong>"No"</strong> to retry.</em>
            </p>
            <button onClick={handleReplayServiceNumber} style={btnReplayStyle} title="Replay service number read-back">🔊 Replay Read-back</button>
          </div>
        )}
      </div>}

      {showRecorder && (
        <VoiceRecorder
          isContinuous={true}
          vadState={vadState}
          isListening={isListening}
          onRecordingComplete={handleRecordingComplete}
          onRecordingStart={stopAllAudio}
          isProcessing={isProcessing}
          onError={(err) => setSession(prev => ({ ...prev, state: 'ERROR', promptText: err }))}
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

// ── Styles ────────────────────────────────────────────────────────────────
const panelContainerStyle = {
  background: '#fff', border: '2px solid #185FA5', borderRadius: '16px',
  padding: '24px', marginBottom: '24px', boxShadow: '0 4px 6px rgba(24, 95, 165, 0.1)',
};
const headerStyle = {
  display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px',
};
const statusBadgeStyle = (state) => ({
  background: state === 'ERROR' ? '#fee2e2'
    : state === 'OPERATOR_FALLBACK' ? '#fef08a'
    : state === 'REVIEWING' ? '#e0f2fe'
    : '#E6F1FB',
  color: state === 'ERROR' ? '#991b1b'
    : state === 'OPERATOR_FALLBACK' ? '#854d0e'
    : state === 'REVIEWING' ? '#0369a1'
    : '#185FA5',
  padding: '6px 12px', borderRadius: '16px', fontSize: '12px', fontWeight: 600, letterSpacing: '0.05em',
});
const cancelBtnStyle = {
  background: 'none', border: 'none', color: '#64748b', cursor: 'pointer', fontSize: '13px', fontWeight: 500,
};
const promptBoxStyle = {
  background: '#f1f5f9', borderLeft: '4px solid #185FA5',
  padding: '16px', borderRadius: '0 8px 8px 0', marginBottom: '20px',
};
const fallbackBoxStyle = { marginTop: '16px', paddingTop: '16px', borderTop: '1px solid #cbd5e1' };
const confirmBoxStyle = { marginTop: '16px', paddingTop: '16px', borderTop: '1px solid #cbd5e1' };
const inputStyle = {
  padding: '10px 12px', fontSize: '14px', border: '1px solid #cbd5e1',
  borderRadius: '8px', marginRight: '12px', outline: 'none',
};
const btnPrimaryStyle = {
  background: '#185FA5', color: 'white', border: 'none',
  padding: '10px 20px', borderRadius: '8px', fontSize: '14px', fontWeight: 500, cursor: 'pointer',
};
const btnSecondaryStyle = {
  background: '#f1f5f9', color: '#334155', border: '1px solid #cbd5e1',
  padding: '10px 20px', borderRadius: '8px', fontSize: '14px', fontWeight: 500, cursor: 'pointer',
};
const btnReplayStyle = {
  background: '#f0fdf4', color: '#166534', border: '1px solid #bbf7d0',
  padding: '10px 18px', borderRadius: '8px', fontSize: '14px', fontWeight: 500,
  cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px',
};

// ── Review / edit complaint styles ─────────────────────────────────────────
const reviewBoxStyle = {
  background: 'linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%)',
  border: '2px solid #38bdf8',
  borderRadius: '12px',
  padding: '20px',
  marginBottom: '20px',
};
const reviewHeaderStyle = {
  display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px', flexWrap: 'wrap',
};
const confidenceBadgeStyle = (conf) => ({
  marginLeft: 'auto',
  background: conf >= 0.8 ? '#dcfce7' : conf >= 0.5 ? '#fef9c3' : '#fee2e2',
  color: conf >= 0.8 ? '#166534' : conf >= 0.5 ? '#713f12' : '#991b1b',
  fontSize: '11px', fontWeight: 700, padding: '3px 10px', borderRadius: '12px',
});
const reviewTextareaStyle = {
  width: '100%', boxSizing: 'border-box', padding: '12px',
  fontSize: '14px', lineHeight: '1.6', fontFamily: 'inherit',
  border: '1.5px solid #bae6fd', borderRadius: '8px',
  background: '#fff', color: '#1e293b',
  resize: 'vertical', outline: 'none',
  boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
};
const btnConfirmStyle = {
  background: 'linear-gradient(135deg, #16a34a 0%, #15803d 100%)',
  color: 'white', border: 'none',
  padding: '11px 24px', borderRadius: '8px', fontSize: '14px', fontWeight: 600,
  cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '8px',
  boxShadow: '0 2px 4px rgba(22, 163, 74, 0.3)',
};
const btnRerecordStyle = {
  background: '#fff', color: '#334155',
  border: '1.5px solid #cbd5e1',
  padding: '11px 20px', borderRadius: '8px', fontSize: '14px', fontWeight: 500,
  cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '8px',
};

export default VoiceSessionPanel;

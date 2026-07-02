import React, { useState, useRef, useEffect, useCallback } from 'react';

/**
 * VoiceRecorder Component — Web Audio VAD Edition
 *
 * Uses the browser's native Web Audio API (AnalyserNode) to detect
 * voice activity and automatically stop recording after 2 seconds of silence.
 * Zero external dependencies — works 100% offline.
 *
 * Props:
 *   onRecordingComplete(blob) — called when speech ends (auto VAD) or manual stop
 *   onRecordingStart()        — called when recording starts (silences TTS)
 *   isProcessing              — shows spinner
 *   autoStartTrigger          — flip this value to programmatically activate the mic
 */
function VoiceRecorder({ onRecordingComplete, onRecordingStart, isProcessing = false, autoStartTrigger }) {
  const [phase, setPhase] = useState('idle'); // 'idle' | 'loading' | 'listening' | 'speaking'
  const isMountedRef = useRef(true);

  // Refs for audio resources
  const streamRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const audioContextRef = useRef(null);
  const analyserRef = useRef(null);
  const rafRef = useRef(null);          // requestAnimationFrame ID
  const chunksRef = useRef([]);

  // VAD state refs
  const hasSpokenRef = useRef(false);
  const silenceStartRef = useRef(null);  // timestamp when silence began

  // Tuning constants
  const VOLUME_THRESHOLD = 0.04;         // RMS volume threshold (0-1 scale)
  const SILENCE_TIMEOUT_MS = 2000;       // 2 seconds of silence → auto-stop

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      cleanup();
    };
  }, []);

  const cleanup = () => {
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      try { mediaRecorderRef.current.stop(); } catch (_) {}
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
      streamRef.current = null;
    }
    if (audioContextRef.current) {
      try { audioContextRef.current.close(); } catch (_) {}
      audioContextRef.current = null;
    }
  };

  // ─── React to autoStartTrigger ─────────────────────────────────────
  const isInitialMount = useRef(true);
  useEffect(() => {
    if (isInitialMount.current) {
      isInitialMount.current = false;
      return;
    }
    if (autoStartTrigger === undefined || autoStartTrigger === null) return;
    startListening();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoStartTrigger]);

  // ─── Start Listening ───────────────────────────────────────────────
  const startListening = async () => {
    if (!isMountedRef.current) return;
    cleanup();
    hasSpokenRef.current = false;
    silenceStartRef.current = null;
    chunksRef.current = [];
    setPhase('loading');

    try {
      // Notify parent to stop TTS before opening mic
      if (onRecordingStart) onRecordingStart();

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (!isMountedRef.current) { stream.getTracks().forEach(t => t.stop()); return; }
      streamRef.current = stream;

      // Set up Web Audio analyser for volume monitoring
      const audioContext = new (window.AudioContext || window.webkitAudioContext)();
      audioContextRef.current = audioContext;
      const source = audioContext.createMediaStreamSource(stream);
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 512;
      analyser.smoothingTimeConstant = 0.3;
      source.connect(analyser);
      analyserRef.current = analyser;

      // Set up MediaRecorder to capture audio
      const mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      mediaRecorder.onstop = () => {
        if (!isMountedRef.current) return;
        const audioBlob = new Blob(chunksRef.current, { type: 'audio/webm' });
        // Only submit if there was actual speech
        if (hasSpokenRef.current && audioBlob.size > 0) {
          onRecordingComplete(audioBlob);
        }
        // Release mic
        if (streamRef.current) {
          streamRef.current.getTracks().forEach(t => t.stop());
          streamRef.current = null;
        }
      };

      mediaRecorder.start(250); // Collect data every 250ms
      setPhase('listening');

      // Start the VAD monitoring loop
      monitorVolume();
    } catch (err) {
      console.error('Microphone access failed:', err);
      if (isMountedRef.current) setPhase('idle');
    }
  };

  // ─── Volume Monitoring Loop ────────────────────────────────────────
  const monitorVolume = () => {
    if (!isMountedRef.current || !analyserRef.current) return;

    const analyser = analyserRef.current;
    const dataArray = new Float32Array(analyser.fftSize);

    const tick = () => {
      if (!isMountedRef.current || !analyserRef.current) return;

      analyser.getFloatTimeDomainData(dataArray);

      // Calculate RMS volume
      let sum = 0;
      for (let i = 0; i < dataArray.length; i++) {
        sum += dataArray[i] * dataArray[i];
      }
      const rms = Math.sqrt(sum / dataArray.length);

      if (rms >= VOLUME_THRESHOLD) {
        // Sound detected
        if (!hasSpokenRef.current) {
          hasSpokenRef.current = true;
          setPhase('speaking');
        }
        silenceStartRef.current = null; // Reset silence timer
      } else if (hasSpokenRef.current) {
        // Silence after speech
        if (silenceStartRef.current === null) {
          silenceStartRef.current = Date.now();
        } else if (Date.now() - silenceStartRef.current >= SILENCE_TIMEOUT_MS) {
          // 2 seconds of silence after speech → auto-stop
          autoStop();
          return; // Stop the loop
        }
      }

      rafRef.current = requestAnimationFrame(tick);
    };

    rafRef.current = requestAnimationFrame(tick);
  };

  // ─── Auto-Stop (triggered by silence timeout) ─────────────────────
  const autoStop = () => {
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }
    if (isMountedRef.current) setPhase('idle');
  };

  // ─── Manual Stop & Submit ─────────────────────────────────────────
  const handleManualStop = useCallback(() => {
    if (!isMountedRef.current) return;
    hasSpokenRef.current = true; // Treat as valid speech for manual stop
    autoStop();
  }, []);

  // ─── Render ───────────────────────────────────────────────────────
  return (
    <div style={containerStyle}>
      {isProcessing ? (
        <div style={processingStyle}>
          <div style={spinnerStyle}></div>
          <span style={{ fontSize: '13px', color: '#64748b' }}>Processing audio...</span>
        </div>
      ) : phase === 'loading' ? (
        <div style={processingStyle}>
          <div style={spinnerStyle}></div>
          <span style={{ fontSize: '13px', color: '#64748b' }}>Opening microphone...</span>
        </div>
      ) : phase === 'idle' ? (
        <div style={idleStyle}>
          <span style={{ fontSize: '13px', color: '#94a3b8' }}>🎙️ Waiting for prompt...</span>
        </div>
      ) : (
        /* listening or speaking */
        <div style={activeRecordingStyle}>
          {/* Animated waveform */}
          <div style={waveStyle}>
            {[...Array(5)].map((_, i) => (
              <div key={i} style={{ ...barStyle, animationDelay: `${i * 0.12}s` }} />
            ))}
          </div>

          <span style={{
            fontSize: '13px',
            color: phase === 'speaking' ? '#e24b4a' : '#64748b',
            fontWeight: 600,
            flexGrow: 1,
          }}>
            {phase === 'speaking' ? '🔴 Speaking...' : '⏳ Listening...'}
          </span>

          {/* Manual safety hatch */}
          <button onClick={handleManualStop} style={stopBtnStyle}>
            Stop & Submit
          </button>
        </div>
      )}
    </div>
  );
}

// ─── Inline Styles ──────────────────────────────────────────────────

const containerStyle = {
  padding: '16px',
  border: '1px solid #e2e8f0',
  borderRadius: '12px',
  background: '#f8fafc',
  display: 'flex',
  justifyContent: 'center',
  alignItems: 'center',
  minHeight: '72px',
};

const idleStyle = { display: 'flex', alignItems: 'center' };

const activeRecordingStyle = {
  display: 'flex',
  alignItems: 'center',
  gap: '12px',
  background: '#fff5f5',
  padding: '8px 12px 8px 16px',
  borderRadius: '8px',
  border: '1px solid #fca5a5',
  width: '100%',
};

const waveStyle = {
  display: 'flex',
  alignItems: 'center',
  gap: '3px',
  height: '32px',
  marginRight: '12px',
};

const barStyle = {
  width: '4px',
  height: '20px',
  background: '#e24b4a',
  borderRadius: '4px',
  animation: 'vadWave 0.6s ease-in-out infinite alternate',
};

const stopBtnStyle = {
  background: '#e24b4a',
  color: 'white',
  border: 'none',
  padding: '8px 16px',
  borderRadius: '8px',
  fontSize: '13px',
  fontWeight: 600,
  cursor: 'pointer',
  flexShrink: 0,
};

const processingStyle = { display: 'flex', alignItems: 'center', gap: '12px' };

const spinnerStyle = {
  width: '20px',
  height: '20px',
  border: '3px solid #e2e8f0',
  borderTop: '3px solid #185FA5',
  borderRadius: '50%',
  animation: 'spin 1s linear infinite',
};

// Inject CSS animations once
if (typeof document !== 'undefined') {
  const styleId = 'vad-recorder-styles';
  if (!document.getElementById(styleId)) {
    const style = document.createElement('style');
    style.id = styleId;
    style.innerHTML = `
      @keyframes vadWave {
        0%   { transform: scaleY(0.4); }
        100% { transform: scaleY(1.2); }
      }
      @keyframes spin {
        0%   { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
      }
    `;
    document.head.appendChild(style);
  }
}

export default VoiceRecorder;

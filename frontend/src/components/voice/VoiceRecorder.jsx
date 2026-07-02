import React, { useState, useRef, useEffect } from 'react';
import { useVadStream } from '../../hooks/useVadStream';
/**
 * VoiceRecorder Component
 * Handles microphone capture using MediaRecorder API.
 * Provides a simple recording indicator and waveform animation.
 */
function VoiceRecorder({ onRecordingComplete, onRecordingStart, isProcessing = false }) {
  const [isRecording, setIsRecording] = useState(false);
  const { vadStatus, startVadMonitoring, stopVadMonitoring } = useVadStream({
    onSpeechStarted: () => {
      console.log('VAD: user has started speaking');
    },
    onEndOfSpeech: () => {
      console.log('VAD: end of speech detected â€” auto-stopping');
      stopRecording(); // â† ye function already file me hai
    },
    onTimeout: () => {
      console.log('VAD: timeout â€” no speech detected');
      stopRecording();
    },
  });
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const streamRef = useRef(null);

  useEffect(() => {
    // Cleanup on unmount
    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop());
      }
    };
  }, []);

  const startRecording = async () => {
    // Issue 4 FIX: Immediately silence any playing TTS before opening the mic
    if (onRecordingStart) onRecordingStart();

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: 'audio/webm'
      });
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        onRecordingComplete(audioBlob);
        
        // Stop all tracks to release microphone
        if (streamRef.current) {
          streamRef.current.getTracks().forEach(track => track.stop());
          streamRef.current = null;
        }
      };

      mediaRecorder.start();
      setIsRecording(true);
      startVadMonitoring(stream);
    } catch (err) {
      console.error('Error accessing microphone:', err);
      alert('Microphone access denied or unavailable. Please check permissions.');
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      stopVadMonitoring(); // NAYA â€” VAD WebSocket bhi band karo
    }
  };

  return (
    <div style={containerStyle}>
      {isProcessing ? (
        <div style={processingStyle}>
          <div className="spinner" style={spinnerStyle}></div>
          <span style={{ fontSize: '13px', color: '#64748b' }}>Processing audio...</span>
        </div>
      ) : (
        <div style={controlsStyle}>
          {isRecording ? (
            <div style={activeRecordingStyle}>
              <div style={pulsingDotStyle}></div>
              <span style={{ fontSize: '13px', color: '#e24b4a', fontWeight: 500, marginRight: '16px' }}>
                Recording...
              </span>
              <button onClick={stopRecording} style={stopBtnStyle}>
                Stop & Submit
              </button>
            </div>
          ) : (
            <button onClick={startRecording} style={startBtnStyle}>
              ðŸŽ¤ Start Recording
            </button>
          )}
        </div>
      )}
    </div>
  );
}

// Inline Styles
const containerStyle = {
  padding: '16px',
  border: '1px solid #e2e8f0',
  borderRadius: '12px',
  background: '#f8fafc',
  display: 'flex',
  justifyContent: 'center',
  alignItems: 'center',
  minHeight: '80px',
};

const controlsStyle = {
  display: 'flex',
  alignItems: 'center',
};

const startBtnStyle = {
  background: '#185FA5',
  color: 'white',
  border: 'none',
  padding: '10px 20px',
  borderRadius: '8px',
  fontSize: '14px',
  fontWeight: 500,
  cursor: 'pointer',
  display: 'flex',
  alignItems: 'center',
  gap: '8px',
};

const stopBtnStyle = {
  background: '#e24b4a',
  color: 'white',
  border: 'none',
  padding: '10px 20px',
  borderRadius: '8px',
  fontSize: '14px',
  fontWeight: 500,
  cursor: 'pointer',
};

const activeRecordingStyle = {
  display: 'flex',
  alignItems: 'center',
  background: '#fee2e2',
  padding: '8px 8px 8px 16px',
  borderRadius: '8px',
  border: '1px solid #fca5a5',
};

const pulsingDotStyle = {
  width: '10px',
  height: '10px',
  borderRadius: '50%',
  background: '#e24b4a',
  marginRight: '8px',
  animation: 'pulse 1.5s infinite',
};

const processingStyle = {
  display: 'flex',
  alignItems: 'center',
  gap: '12px',
};

const spinnerStyle = {
  width: '20px',
  height: '20px',
  border: '3px solid #e2e8f0',
  borderTop: '3px solid #185FA5',
  borderRadius: '50%',
  animation: 'spin 1s linear infinite',
};

// Add keyframes for animation in a <style> block dynamically, or rely on existing global CSS
if (typeof document !== 'undefined') {
  const style = document.createElement('style');
  style.innerHTML = `
    @keyframes pulse {
      0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(226, 75, 74, 0.7); }
      70% { transform: scale(1); box-shadow: 0 0 0 6px rgba(226, 75, 74, 0); }
      100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(226, 75, 74, 0); }
    }
    @keyframes spin {
      0% { transform: rotate(0deg); }
      100% { transform: rotate(360deg); }
    }
  `;
  document.head.appendChild(style);
}

export default VoiceRecorder;

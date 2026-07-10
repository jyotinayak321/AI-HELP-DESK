import React, { useEffect, useRef, useState, useCallback } from 'react';
import {
  LiveKitRoom,
  RoomAudioRenderer,
  useLocalParticipant,
  useTracks,
  useConnectionState,
  useRoomContext,
  useRemoteParticipants,
} from '@livekit/components-react';
import { Track } from 'livekit-client';
import { flushLiveKitSpeech } from '../../api/voice.api';

const API_URL = import.meta.env.VITE_API_URL || 'http://192.168.1.34:8001';
const WS_URL = API_URL.replace(/^http/, 'ws');

/**
 * Handles WebRTC audio transport, barge-in, and WebSocket state updates.
 *
 * Props:
 *   stopTts      — callback from VoiceSessionPanel to stop local TTS playback
 *                  (the greeting/confirmation audio played via <Audio>).
 *                  LiveKit room TTS (RoomAudioRenderer) is muted separately
 *                  inside this component via the room context.
 *
 * Lifecycle design:
 *  - The signalling WebSocket reconnects ONLY when session_id changes.
 *  - Callbacks are stored in refs so that parent re-renders (which hand new
 *    function references each time) do NOT trigger a WS reconnect cycle.
 *  - LiveKitRoom is mounted once and stays mounted for the session lifetime.
 */
function LiveKitAudioTransport({
  session_id,
  livekit_token,
  livekit_url,
  onStateChange,
  onTranscribed,
  onError,
  onProcessing,
  stopTts,           // NEW: parent callback to stop local <Audio> TTS playback
}) {
  const [isAgentReady, setIsAgentReady] = useState(false);
  const [wsStatus, setWsStatus] = useState('connecting');
  const [liveKitMounted, setLiveKitMounted] = useState(false);
  const [isFlushing, setIsFlushing] = useState(false);

  // Shared ref so inner components can call barge-in without prop drilling
  const bargeInRef = useRef(null);

  const wsRef = useRef(null);

  // ── Callback refs ──────────────────────────────────────────────────────────
  const onStateChangeRef = useRef(onStateChange);
  const onTranscribedRef = useRef(onTranscribed);
  const onErrorRef       = useRef(onError);
  const onProcessingRef  = useRef(onProcessing);
  const stopTtsRef       = useRef(stopTts);

  useEffect(() => { onStateChangeRef.current = onStateChange; }, [onStateChange]);
  useEffect(() => { onTranscribedRef.current = onTranscribed; }, [onTranscribed]);
  useEffect(() => { onErrorRef.current       = onError;       }, [onError]);
  useEffect(() => { onProcessingRef.current  = onProcessing;  }, [onProcessing]);
  useEffect(() => { stopTtsRef.current       = stopTts;       }, [stopTts]);

  // ── WebSocket connection ───────────────────────────────────────────────────
  useEffect(() => {
    if (!session_id) return;

    console.log(`[LiveKit Transport] Connecting WebSocket for session ${session_id}`);
    const ws = new WebSocket(`${WS_URL}/api/livekit/events/${session_id}`);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('[LiveKit Transport] WebSocket Connected');
      setWsStatus('connected');
      setLiveKitMounted(true);
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        console.log('[LiveKit Transport] WS Event:', msg.type, msg.payload);

        switch (msg.type) {
          case 'ready':
            setIsAgentReady(true);
            break;

          case 'speech_started':
            // ── BARGE-IN ──────────────────────────────────────────────────
            // User started speaking. Stop any ongoing TTS immediately.
            console.log('[Barge-in] speech_started — stopping TTS');
            if (stopTtsRef.current) stopTtsRef.current();   // stops local <Audio>
            if (bargeInRef.current)  bargeInRef.current();  // mutes LiveKit room audio
            break;

          case 'state_change':
            if (onStateChangeRef.current) onStateChangeRef.current(msg.payload);
            break;
          case 'transcribed':
            if (onTranscribedRef.current) onTranscribedRef.current(msg.payload);
            break;
          case 'processing':
            if (onProcessingRef.current) onProcessingRef.current(msg.payload);
            break;
          case 'error':
            if (onErrorRef.current) onErrorRef.current(msg.payload);
            break;
          default:
            break;
        }
      } catch (err) {
        console.error('[LiveKit Transport] Failed to parse WS message:', err);
      }
    };

    ws.onerror = (err) => {
      console.error('[LiveKit Transport] WebSocket Error:', err);
      setWsStatus('error');
    };

    ws.onclose = () => {
      console.log('[LiveKit Transport] WebSocket Closed');
      setWsStatus('closed');
    };

    return () => {
      console.log(`[LiveKit Transport] Closing WebSocket for session ${session_id}`);
      ws.close();
      wsRef.current = null;
    };
  }, [session_id]); // ← ONLY session_id; callbacks read from refs

  // ── Stop & Submit handler ───────────────────────────────────────────────
  const handleStopAndSubmit = useCallback(async () => {
    // [TRACE-FE-1] Guard checks
    console.log('[TRACE-FE-1] Stop & Submit clicked:', {
      session_id,
      isFlushing,
      wsStatus,
      isAgentReady,
    });
    if (!session_id || isFlushing) {
      console.warn('[TRACE-FE-1] BLOCKED — reason:', !session_id ? 'no session_id' : 'already flushing');
      return;
    }

    setIsFlushing(true);
    const t0 = Date.now();

    // [TRACE-FE-2] HTTP request fired
    console.log(`[TRACE-FE-2] Calling POST /api/livekit/flush/${session_id} at`, new Date().toISOString());
    try {
      const res = await flushLiveKitSpeech(session_id);

      // [TRACE-FE-3] HTTP response received
      console.log('[TRACE-FE-3] Flush HTTP response:', {
        status: res.status,
        data: res.data,
        elapsed_ms: Date.now() - t0,
      });

      if (res.data?.had_audio === false) {
        console.warn(
          '[TRACE-FE-3] had_audio=false — server reported an empty speech buffer. '
          + 'Possible causes: (1) you pressed Stop & Submit before speaking, '
          + '(2) the VAD already processed the speech automatically, '
          + '(3) the mic gate was active (TTS was playing when you spoke), '
          + '(4) the session is not registered in adapter._states. '
          + 'Check backend TRACE-FLUSH-B and TRACE-FLUSH-C logs for details.'
        );
      } else if (res.data?.had_audio === true) {
        console.log(
          '[TRACE-FE-3] had_audio=true — server processed audio. '
          + 'Waiting for WebSocket events: transcribed → state_change (or silent/error).'
        );
      }
    } catch (err) {
      // [TRACE-FE-ERR] HTTP-level failure
      console.error('[TRACE-FE-ERR] Stop & Submit HTTP request FAILED:', {
        status: err.response?.status,
        data: err.response?.data,
        message: err.message,
        elapsed_ms: Date.now() - t0,
      });
    } finally {
      setIsFlushing(false);
      console.log('[TRACE-FE-4] Flush complete (isFlushing reset). '
        + 'If the pipeline ran successfully you should now see '
        + 'WebSocket events: processing → transcribed → state_change.');
    }
  }, [session_id, isFlushing]);

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div style={{
      padding: '16px',
      border: '1px solid rgba(30,144,255,0.2)',
      borderRadius: '12px',
      background: 'rgba(10,22,40,0.6)',
      minHeight: '80px',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
        <span style={{ fontSize: '11px', color: '#4d6480', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
          LiveKit Transport
        </span>
        <span style={{
          fontSize: '11px',
          color: wsStatus === 'connected' ? '#22c55e' : '#eab308',
          fontWeight: 600,
        }}>
          WS: {wsStatus} | Agent: {isAgentReady ? '● Ready' : '○ Waiting...'}
        </span>
      </div>

      {/* LiveKitRoom stays mounted once connected */}
      {liveKitMounted && (
        <LiveKitRoom
          serverUrl={livekit_url}
          token={livekit_token}
          connect={true}
          audio={false}
          video={false}
          onConnected={() => console.log(`[LiveKit] Connected to room`)}
          onDisconnected={() => console.log('[LiveKit] Disconnected from room')}
          onError={(err) => console.error('[LiveKit] Room Error:', err)}
        >
          {/* Renders the AI's TTS tracks automatically */}
          <RoomAudioRenderer />

          {/* Manages mic publication and exposes barge-in mute fn */}
          <MicrophoneManager
            isAgentReady={isAgentReady}
            bargeInRef={bargeInRef}
          />

          {/* Connection state logger */}
          <ConnectionStateLogger />
        </LiveKitRoom>
      )}

      {/* ── Stop & Submit button ─────────────────────────────────────────── */}
      {isAgentReady && (
        <div style={{ marginTop: '12px' }}>
          <button
            onClick={handleStopAndSubmit}
            disabled={isFlushing}
            style={{
              width: '100%',
              padding: '10px 20px',
              background: isFlushing
                ? 'rgba(226,75,74,0.4)'
                : 'linear-gradient(135deg, #e24b4a 0%, #c0392b 100%)',
              color: 'white',
              border: 'none',
              borderRadius: '8px',
              fontSize: '13px',
              fontWeight: 600,
              cursor: isFlushing ? 'not-allowed' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              transition: 'opacity 0.2s',
              opacity: isFlushing ? 0.7 : 1,
              letterSpacing: '0.03em',
            }}
          >
            {isFlushing ? (
              <>
                <div style={{
                  width: '12px', height: '12px',
                  border: '2px solid rgba(255,255,255,0.3)',
                  borderTop: '2px solid white',
                  borderRadius: '50%',
                  animation: 'spin 0.7s linear infinite',
                }} />
                Submitting...
              </>
            ) : (
              <>■ Stop &amp; Submit</>
            )}
          </button>
          <p style={{ fontSize: '10px', color: '#4d6480', textAlign: 'center', marginTop: '6px', marginBottom: 0 }}>
            Press if VAD doesn't detect your speech automatically
          </p>
        </div>
      )}
    </div>
  );
}

/**
 * Logs LiveKit connection state changes for debugging.
 */
function ConnectionStateLogger() {
  const state = useConnectionState();
  const room = useRoomContext();
  const { localParticipant } = useLocalParticipant();

  useEffect(() => {
    console.log(`[LiveKit] Connection state changed: ${state}`);
    if (state === 'connected' && room && localParticipant) {
      console.log(`[LiveKit Frontend Info] Room Name: ${room.name}`);
      console.log(`[LiveKit Frontend Info] Local Participant Identity: ${localParticipant.identity}`);
      console.log(`[LiveKit Frontend Info] Local Participant SID: ${localParticipant.sid}`);
    }
  }, [state, room, localParticipant]);

  return null;
}

/**
 * MicrophoneManager
 * Publishes the local microphone when `isAgentReady` is true.
 * Exposes a barge-in mute function via `bargeInRef` that the parent can call
 * when a speech_started event arrives to immediately silence remote tracks.
 */
function MicrophoneManager({ isAgentReady, bargeInRef }) {
  const { localParticipant } = useLocalParticipant();
  const remoteParticipants = useRemoteParticipants();
  const room = useRoomContext();
  const [isMicActive, setIsMicActive] = useState(false);

  // ── Barge-in: mute all remote participants' audio tracks ─────────────────
  // Wire the barge-in callback into the shared ref so the WS handler
  // above can call it without re-running the WS useEffect.
  useEffect(() => {
    bargeInRef.current = () => {
      // Mute all remote audio tracks in the room so AI TTS stops immediately.
      if (!room) return;
      for (const participant of remoteParticipants) {
        for (const [, publication] of participant.audioTrackPublications) {
          if (publication.track) {
            console.log('[Barge-in] Muting remote track:', publication.trackSid);
            publication.track.mediaStreamTrack.enabled = false;
          }
        }
      }
      // Re-enable after a short delay so the next TTS response plays normally.
      setTimeout(() => {
        for (const participant of remoteParticipants) {
          for (const [, publication] of participant.audioTrackPublications) {
            if (publication.track) {
              publication.track.mediaStreamTrack.enabled = true;
            }
          }
        }
      }, 3000); // 3s — enough time for STT + pipeline to respond
    };
  }, [bargeInRef, room, remoteParticipants]);

  useEffect(() => {
    if (localParticipant) {
      console.log(`[LiveKit Transport] Local participant identity: ${localParticipant.identity}`);
    }

    if (!localParticipant || !isAgentReady) return;

    const publishMic = async () => {
      try {
        console.log('[LiveKit Transport] Agent is ready, publishing microphone...');
        try {
          const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
          console.log('[LiveKit Transport] Microphone permissions granted by browser.');
          stream.getTracks().forEach(t => t.stop());
        } catch (mediaErr) {
          console.error('[LiveKit Transport] Microphone permissions denied by browser!', mediaErr);
        }
        await localParticipant.setMicrophoneEnabled(true);
        setIsMicActive(true);
        console.log('[LiveKit Transport] setMicrophoneEnabled(true) succeeded!');
      } catch (err) {
        console.error('[LiveKit Transport] Failed to publish microphone:', err);
      }
    };

    publishMic();

    return () => {
      if (localParticipant) {
        console.log('[LiveKit Transport] Unpublishing microphone...');
        localParticipant.setMicrophoneEnabled(false).catch(console.error);
        setIsMicActive(false);
      }
    };
  }, [localParticipant, isAgentReady]);

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
      <div style={{
        width: '10px', height: '10px', borderRadius: '50%', flexShrink: 0,
        background: isMicActive ? '#e24b4a' : (isAgentReady ? '#eab308' : '#4d6480'),
        animation: isMicActive ? 'pulse 1.5s infinite' : 'none',
      }} />
      <span style={{
        fontSize: '12px',
        color: isMicActive ? '#e24b4a' : (isAgentReady ? '#ca8a04' : '#4d6480'),
        fontWeight: 600,
      }}>
        {isMicActive
          ? 'Recording — speak now (or press Stop & Submit)'
          : isAgentReady
            ? 'Connecting microphone...'
            : 'Waiting for AI agent...'}
      </span>
    </div>
  );
}

// Keyframes
if (typeof document !== 'undefined' && !document.getElementById('lk-kf')) {
  const s = document.createElement('style');
  s.id = 'lk-kf';
  s.innerHTML = `
    @keyframes pulse {
      0%   { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(226,75,74,0.7); }
      70%  { transform: scale(1);    box-shadow: 0 0 0 6px rgba(226,75,74,0); }
      100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(226,75,74,0); }
    }
    @keyframes spin {
      0%   { transform: rotate(0deg); }
      100% { transform: rotate(360deg); }
    }
  `;
  document.head.appendChild(s);
}

export default LiveKitAudioTransport;

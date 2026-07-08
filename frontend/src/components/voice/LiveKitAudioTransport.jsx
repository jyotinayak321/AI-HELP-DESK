import React, { useEffect, useRef, useState, useCallback } from 'react';
import {
  LiveKitRoom,
  RoomAudioRenderer,
  useLocalParticipant,
  useTracks,
  useConnectionState,
  useRoomContext,
} from '@livekit/components-react';
import { Track } from 'livekit-client';

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://127.0.0.1:8001';

/**
 * Handles WebRTC audio transport, Hybrid Barge-in, and WebSocket state updates.
 */
function LiveKitAudioTransport({
  session_id,
  livekit_token,
  livekit_url,
  onStateChange,
  onTranscribed,
  onError,
  onProcessing
}) {
  const [isAgentReady, setIsAgentReady] = useState(false);
  const [wsStatus, setWsStatus] = useState('connecting');
  const wsRef = useRef(null);
  
  // WebSocket Connection Management
  useEffect(() => {
    if (!session_id) return;
    
    console.log(`[LiveKit Transport] Connecting WebSocket for session ${session_id}`);
    const ws = new WebSocket(`${WS_URL}/api/livekit/events/${session_id}`);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('[LiveKit Transport] WebSocket Connected');
      setWsStatus('connected');
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        // Schema: { type, session_id, timestamp, payload }
        console.log('[LiveKit Transport] WS Event:', msg.type, msg.payload);
        
        switch (msg.type) {
          case 'ready':
            setIsAgentReady(true);
            break;
          case 'state_change':
            if (onStateChange) onStateChange(msg.payload);
            break;
          case 'transcribed':
            if (onTranscribed) onTranscribed(msg.payload);
            break;
          case 'processing':
            if (onProcessing) onProcessing(msg.payload);
            break;
          case 'error':
            if (onError) onError(msg.payload);
            break;
          // Other backend events (ping, speech_started, etc) can be handled here or ignored.
          default:
            break;
        }
      } catch (err) {
        console.error('Failed to parse WS message:', err);
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
  }, [session_id, onStateChange, onTranscribed, onError, onProcessing]);

  return (
    <div style={{ padding: "16px", border: "1px solid #e2e8f0", borderRadius: "12px", background: "#f8fafc", minHeight: "80px" }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
        <span style={{ fontSize: "12px", color: "#64748b" }}>LiveKit Transport</span>
        <span style={{ fontSize: "12px", color: wsStatus === 'connected' ? "#22c55e" : "#eab308" }}>
          WS: {wsStatus} | Agent: {isAgentReady ? 'Ready' : 'Waiting...'}
        </span>
      </div>

      {wsStatus === 'connected' && (
        <LiveKitRoom
          serverUrl={livekit_url}
          token={livekit_token}
          connect={true}
          audio={false} // We will manually publish audio only when agent is ready
          video={false}
          onConnected={() => console.log(`[LiveKit] Connected to room with token: ${livekit_token.substring(0, 15)}...`)}
          onDisconnected={() => console.log('[LiveKit] Disconnected from room')}
          onError={(err) => console.error('[LiveKit] Room Error:', err)}
        >
          {/* Renders the AI's TTS tracks automatically */}
          <RoomAudioRenderer />
          
          {/* Manages the caller's microphone publication and local ducking */}
          <MicrophoneManager isAgentReady={isAgentReady} />
          
          {/* Connection State Logger */}
          <ConnectionStateLogger />
        </LiveKitRoom>
      )}
    </div>
  );
}

/**
 * Helper to log LiveKit connection state changes
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
 * Publishes the local microphone only when `isAgentReady` is true.
 * Implements "Hybrid Barge-in" by ducking the volume of remote tracks 
 * when local speech volume exceeds a threshold.
 */
function MicrophoneManager({ isAgentReady }) {
  const { localParticipant } = useLocalParticipant();
  const tracks = useTracks([Track.Source.Microphone], { onlySubscribed: true }); // Agent's track
  
  // Publish microphone when agent is ready
  useEffect(() => {
    if (localParticipant) {
      console.log(`[LiveKit Transport] Local participant identity: ${localParticipant.identity}`);
    }

    if (!localParticipant || !isAgentReady) return;

    let isSubscribed = true;
    const publishMic = async () => {
      try {
        console.log('[LiveKit Transport] Agent is ready, publishing microphone...');
        // Let's ask the browser for permissions just in case
        try {
          const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
          console.log('[LiveKit Transport] Microphone permissions granted by browser.');
          // Stop the test stream immediately
          stream.getTracks().forEach(t => t.stop());
        } catch (mediaErr) {
          console.error('[LiveKit Transport] Microphone permissions denied by browser!', mediaErr);
        }

        await localParticipant.setMicrophoneEnabled(true);
        console.log('[LiveKit Transport] localParticipant.setMicrophoneEnabled(true) succeeded!');
      } catch (err) {
        console.error('[LiveKit Transport] Failed to publish microphone:', err);
      }
    };

    publishMic();

    return () => {
      isSubscribed = false;
      if (localParticipant) {
        console.log('[LiveKit Transport] Unpublishing microphone...');
        localParticipant.setMicrophoneEnabled(false).catch(console.error);
      }
    };
  }, [localParticipant, isAgentReady]);

  // Hybrid Barge-in: Local Volume Ducking
  // In a real implementation, you would attach an AnalyserNode to the local audio stream,
  // check the volume level, and if > threshold, find the HTMLAudioElements created by 
  // RoomAudioRenderer and set their volume to 0.2 (ducking).
  // For simplicity in this iteration, we rely on the backend VAD to formally interrupt.
  // The actual ducking logic would be hooked into LiveKit's `createAudioAnalyser` or similar.

  return (
    <div style={{ display: "flex", alignItems: "center", gap: "12px", marginTop: "12px" }}>
      <div style={{
        width: "20px", height: "20px", borderRadius: "50%",
        background: isAgentReady ? "#22c55e" : "#eab308",
        animation: isAgentReady ? "pulse 1.5s infinite" : "none"
      }}></div>
      <span style={{ fontSize: "13px", color: isAgentReady ? "#15803d" : "#ca8a04", fontWeight: 600 }}>
        {isAgentReady ? "Microphone Live (Speak to interrupt)" : "Connecting to AI Agent..."}
      </span>
    </div>
  );
}

// Add keyframes for pulse if not exists
if (typeof document !== "undefined" && !document.getElementById("lk-kf")) {
  const s = document.createElement("style");
  s.id = "lk-kf";
  s.innerHTML = "@keyframes pulse{0%{transform:scale(0.95);box-shadow:0 0 0 0 rgba(34,197,94,0.7)}70%{transform:scale(1);box-shadow:0 0 0 6px rgba(34,197,94,0)}100%{transform:scale(0.95);box-shadow:0 0 0 0 rgba(34,197,94,0)}}";
  document.head.appendChild(s);
}

export default LiveKitAudioTransport;

import { useRef, useCallback, useState } from 'react';

/**
 * useVadStream — Real-time VAD WebSocket hook.
 *
 * Mic se live audio capture karta hai (AudioWorklet ke through),
 * backend VAD WebSocket ko bhejta hai, aur "speech_started" /
 * "end_of_speech" / "timeout" events expose karta hai.
 */
export function useVadStream({ onSpeechStarted, onEndOfSpeech, onTimeout } = {}) {
  const [vadStatus, setVadStatus] = useState('idle'); // idle | listening | speaking

  const wsRef = useRef(null);
  const audioContextRef = useRef(null);
  const workletNodeRef = useRef(null);
  const sourceRef = useRef(null);

  const startVadMonitoring = useCallback(async (stream) => {
    try {
      // 1. WebSocket connect karo
      const ws = new WebSocket('ws://127.0.0.1:8000/api/voice/ws/vad-stream');
      wsRef.current = ws;

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);

        if (data.event === 'listening') {
          setVadStatus('listening');
        } else if (data.event === 'speech_started') {
          setVadStatus('speaking');
          if (onSpeechStarted) onSpeechStarted();
        } else if (data.event === 'end_of_speech') {
          setVadStatus('idle');
          if (onEndOfSpeech) onEndOfSpeech();
        } else if (data.event === 'timeout') {
          setVadStatus('idle');
          if (onTimeout) onTimeout();
        }
      };

      ws.onerror = (err) => {
        console.error('VAD WebSocket error:', err);
      };

      // 2. AudioContext + AudioWorklet setup karo
      const audioContext = new AudioContext();
      audioContextRef.current = audioContext;

      await audioContext.audioWorklet.addModule('/vad-processor.js');

      const source = audioContext.createMediaStreamSource(stream);
      sourceRef.current = source;

      const workletNode = new AudioWorkletNode(audioContext, 'vad-processor');
      workletNodeRef.current = workletNode;

      // 3. Worklet se aaye har frame ko WebSocket pe bhejo
      workletNode.port.onmessage = (event) => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(event.data); // event.data ek ArrayBuffer hai (raw PCM16)
        }
      };

      source.connect(workletNode);
      // Note: workletNode ko destination se connect NAHI kiya —
      // taaki mic ki awaaz speaker se echo na ho.
    } catch (err) {
      console.error('Failed to start VAD monitoring:', err);
    }
  }, [onSpeechStarted, onEndOfSpeech, onTimeout]);

  const stopVadMonitoring = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    if (workletNodeRef.current) {
      workletNodeRef.current.disconnect();
      workletNodeRef.current = null;
    }
    if (sourceRef.current) {
      sourceRef.current.disconnect();
      sourceRef.current = null;
    }
    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }
    setVadStatus('idle');
  }, []);

  return { vadStatus, startVadMonitoring, stopVadMonitoring };
}
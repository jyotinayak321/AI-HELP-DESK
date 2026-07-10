import api from './axios';

export const startVoiceSession = async () => {
  return api.post('/api/voice/start');
};

export const submitServiceNumberAudio = async (sessionId, audioBlob) => {
  const formData = new FormData();
  formData.append('session_id', sessionId);
  formData.append('audio', audioBlob, 'audio.webm');
  return api.post('/api/voice/service-number', formData, {
    headers: { 'Content-Type': undefined },
  });
};

export const confirmServiceNumber = async (sessionId, confirmed, overrideData = {}) => {
  return api.post('/api/voice/confirm', {
    session_id: sessionId,
    confirmed,
    ...overrideData,
  });
};

export const submitConfirmAudio = async (sessionId, audioBlob) => {
  const formData = new FormData();
  formData.append('session_id', sessionId);
  formData.append('audio', audioBlob, 'audio.webm');
  return api.post('/api/voice/confirm-audio', formData, {
    headers: { 'Content-Type': undefined },
  });
};

export const submitComplaintAudio = async (sessionId, audioBlob) => {
  const formData = new FormData();
  formData.append('session_id', sessionId);
  formData.append('audio', audioBlob, 'audio.webm');
  return api.post('/api/voice/complaint', formData, {
    headers: { 'Content-Type': undefined },
  });
};

export const submitFallback = async (sessionId, fallbackData) => {
  return api.post('/api/voice/fallback', {
    session_id: sessionId,
    ...fallbackData,
  });
};

// FIX: Sirf ek fetchAudioBlob — JWT token ke saath
export const fetchAudioBlob = async (url) => {
  const oidcKey = Object.keys(sessionStorage).find(k => k.startsWith('oidc.user:'));
  let token = '';
  if (oidcKey) {
    try {
      token = JSON.parse(sessionStorage.getItem(oidcKey))?.access_token || '';
    } catch (_) {}
  }
  const response = await fetch(url, {
    headers: { Authorization: `Bearer ${token}` }
  });
  if (!response.ok) throw new Error(`Audio fetch failed: ${response.status}`);
  const blob = await response.blob();
  return URL.createObjectURL(blob);
};

export const getTTSUrl = (text, normalise = false) => {
  const params = new URLSearchParams({ text, normalise: normalise ? 'true' : 'false' });
  const baseUrl = import.meta.env.VITE_API_URL || 'http://192.168.1.34:8001';
  return `${baseUrl}/api/voice/tts?${params.toString()}`;
};

export const getPromptUrl = (key) => {
  const baseUrl = import.meta.env.VITE_API_URL || 'http://192.168.1.34:8001';
  return `${baseUrl}/api/voice/prompt/${key}`;
};

/** Manually trigger end-of-speech for a LiveKit session (Stop & Submit button). */
export const flushLiveKitSpeech = (sessionId) =>
  api.post(`/api/livekit/flush/${sessionId}`);
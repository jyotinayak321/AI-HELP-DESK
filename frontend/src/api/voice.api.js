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

export const submitAnotherComplaintAudio = async (sessionId, audioBlob) => {
  const formData = new FormData();
  formData.append('session_id', sessionId);
  formData.append('audio', audioBlob, 'audio.webm');
  return api.post('/api/voice/another-complaint', formData, {
    headers: { 'Content-Type': undefined },
  });
};

export const submitFallback = async (sessionId, fallbackData) => {
  return api.post('/api/voice/fallback', {
    session_id: sessionId,
    ...fallbackData,
  });
};

// Phase 4: re-issue a LiveKit token for an existing session (e.g. when
// resuming into ASK_ANOTHER_COMPLAINT after a ticket is confirmed, or
// after a browser refresh). 404s if the session never had a LiveKit
// room (LIVEKIT_ENABLED=false) — callers should treat that as "not
// available" and fall back to the legacy record/upload flow.
export const getLiveKitToken = async (sessionId) => {
  return api.get('/api/livekit/token', { params: { session_id: sessionId } });
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
  return `http://127.0.0.1:8001/api/voice/tts?${params.toString()}`;
};

export const getPromptUrl = (key) => {
  return `http://127.0.0.1:8001/api/voice/prompt/${key}`;
};
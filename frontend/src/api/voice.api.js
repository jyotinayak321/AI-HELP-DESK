import api from './axios';

/**
 * Start a new voice session.
 */
export const startVoiceSession = async () => {
  return api.post('/api/voice/start');
};

/**
 * Upload audio to capture and validate the service number.
 * @param {string} sessionId
 * @param {Blob} audioBlob
 */
export const submitServiceNumberAudio = async (sessionId, audioBlob) => {
  const formData = new FormData();
  formData.append('session_id', sessionId);
  formData.append('audio', audioBlob, 'audio.webm');
  
  // Set Content-Type to undefined so the browser generates the boundary
  return api.post('/api/voice/service-number', formData, {
    headers: { 'Content-Type': undefined },
  });
};

/**
 * Confirm or reject the recognized service number.
 * @param {string} sessionId
 * @param {boolean} confirmed
 * @param {Object} overrideData - Optional manual entry data if fallback
 */
export const confirmServiceNumber = async (sessionId, confirmed, overrideData = {}) => {
  return api.post('/api/voice/confirm', {
    session_id: sessionId,
    confirmed,
    ...overrideData,
  });
};

/**
 * Upload audio to capture and classify the complaint.
 * @param {string} sessionId
 * @param {Blob} audioBlob
 */
export const submitComplaintAudio = async (sessionId, audioBlob) => {
  const formData = new FormData();
  formData.append('session_id', sessionId);
  formData.append('audio', audioBlob, 'audio.webm');
  
  return api.post('/api/voice/complaint', formData, {
    headers: { 'Content-Type': undefined },
  });
};

/**
 * Manually submit the service number (operator fallback).
 * @param {string} sessionId
 * @param {Object} fallbackData - { service_no, complainant_name, etc. }
 */
export const submitFallback = async (sessionId, fallbackData) => {
  return api.post('/api/voice/fallback', {
    session_id: sessionId,
    ...fallbackData,
  });
};

/**
 * Fetch authenticated audio blob for TTS or static prompts.
 */
export const fetchAudioBlob = async (url) => {
  const response = await api.get(url, { responseType: 'blob' });
  return URL.createObjectURL(response.data);
};

/**
 * Get dynamic TTS audio URL for a given text.
 * @param {string} text
 * @param {boolean} normalise
 */
export const getTTSUrl = (text, normalise = false) => {
  const params = new URLSearchParams({ text, normalise: normalise ? 'true' : 'false' });
  // Make sure this points to the backend base URL correctly
  return `http://127.0.0.1:8000/api/voice/tts?${params.toString()}`;
};

/**
 * Get static prompt audio URL.
 * @param {string} key
 */
export const getPromptUrl = (key) => {
  return `http://127.0.0.1:8000/api/voice/prompt/${key}`;
};

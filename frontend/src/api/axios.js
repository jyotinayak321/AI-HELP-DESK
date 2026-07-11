/**
 * axios.js
 * ---------
 * Shared Axios instance for all API calls.
 *
 * When the user is logged in via Keycloak, the access token is automatically
 * injected into every request header using a request interceptor.
 * The token is stored in sessionStorage by react-oidc-context after login.
 */

import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://192.168.1.34:8001',
  headers: { 'Content-Type': 'application/json' },
});

// Automatically attach the Keycloak JWT to every outgoing request.
// This reads the token from the OIDC session storage key that react-oidc-context uses.
api.interceptors.request.use((config) => {
  // react-oidc-context stores the user in sessionStorage with a key like:
  // "oidc.user:http://192.168.1.34:8080/realms/ai-helpdesk:helpdesk-frontend"
  const oidcKey = Object.keys(sessionStorage).find(
    (k) => k.startsWith('oidc.user:')
  );
  if (oidcKey) {
    try {
      const user = JSON.parse(sessionStorage.getItem(oidcKey));
      if (user?.access_token) {
        config.headers['Authorization'] = `Bearer ${user.access_token}`;
      }
    } catch (_) {
      // If parsing fails, just proceed without the token
    }
  }
  return config;
});

export default api;

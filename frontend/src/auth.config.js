/**
 * auth.config.js
 * ---------------
 * Keycloak / OIDC configuration for react-oidc-context.
 *
 * This tells the React app where Keycloak lives and which client to use.
 * The redirect_uri tells Keycloak where to send the user BACK to after login.
 */

export const oidcConfig = {
  authority: `${import.meta.env.VITE_KEYCLOAK_URL || 'http://192.168.1.34:8080'}/realms/ai-helpdesk`,
  client_id: 'helpdesk-frontend',
  redirect_uri: window.location.origin,
  post_logout_redirect_uri: window.location.origin,
  response_type: 'code',
  scope: 'openid profile email',
  // Automatically refresh tokens before they expire
  automaticSilentRenew: true,
  // Load user profile from Keycloak
  loadUserInfo: true,
};

/**
 * useCurrentUser.js
 * ------------------
 * Custom hook that reads the logged-in user's role and persona from the backend.
 *
 * HOW IT WORKS:
 *   1. Reads the Keycloak JWT from react-oidc-context's `useAuth()`.
 *   2. Calls GET /api/me on the FastAPI backend, passing the token in the header.
 *   3. Returns { serviceNo, role, managedApplicationId, isOperator, isAdmin }.
 *
 * When AUTH_ENABLED=False in the backend, /api/me returns the DEV_USER mock,
 * so the frontend stays fully functional even without Keycloak running.
 */

import { useState, useEffect } from 'react';
import { useAuth } from 'react-oidc-context';
import api from './api/axios';

export function useCurrentUser() {
  const auth = useAuth();
  const [userInfo, setUserInfo] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchMe() {
      try {
        const headers = {};
        // Attach the JWT token if the user is logged in via Keycloak
        if (auth.isAuthenticated && auth.user?.access_token) {
          headers['Authorization'] = `Bearer ${auth.user.access_token}`;
        }
        const response = await api.get('/api/me', { headers });
        setUserInfo(response.data);
      } catch (err) {
        console.error('Failed to fetch /api/me:', err);
        // Fallback: treat as a dev operator if backend call fails
        setUserInfo({ service_no: 'DEV-00000', role: 'operator', managed_team: null });
      } finally {
        setLoading(false);
      }
    }

    // Only fetch once Keycloak has settled (or immediately if not using auth)
    if (!auth.isLoading) {
      fetchMe();
    }
  }, [auth.isAuthenticated, auth.isLoading, auth.user]);

  return {
    loading,
    serviceNo: userInfo?.service_no,
    role: userInfo?.role,
    managedTeam: userInfo?.managed_team,
    isOperator: userInfo?.role === 'operator',
    isAdmin: userInfo?.role === 'admin',
  };
}

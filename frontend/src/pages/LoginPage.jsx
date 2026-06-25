/**
 * LoginPage.jsx
 * -------------
 * The login screen shown to unauthenticated users.
 * When the user clicks "Login", they are redirected to the Keycloak login page.
 * After successful login, Keycloak redirects them back and react-oidc-context
 * automatically picks up the token.
 */

import { useAuth } from 'react-oidc-context';

export default function LoginPage() {
  const auth = useAuth();

  return (
    <div style={styles.container}>
      <div style={styles.card}>
        {/* Logo / App Identity */}
        <div style={styles.logoArea}>
          <div style={styles.logoIcon}>🛡️</div>
          <h1 style={styles.title}>AI Help Desk</h1>
          <p style={styles.subtitle}>Indian Air Force — IT Support Portal</p>
        </div>

        {/* Divider */}
        <div style={styles.divider} />

        {/* Login prompt */}
        <p style={styles.prompt}>
          Please authenticate with your Service Number to continue.
        </p>

        {/* Main login button */}
        <button
          id="btn-keycloak-login"
          style={styles.loginBtn}
          onClick={() => auth.signinRedirect()}
        >
          🔐 Login with Service Number
        </button>

        {/* Status / error messages */}
        {auth.error && (
          <p style={styles.error}>
            ⚠️ Login error: {auth.error.message}
          </p>
        )}

        <p style={styles.footer}>
          Authorised personnel only. All access is logged.
        </p>
      </div>
    </div>
  );
}

const styles = {
  container: {
    minHeight: '100vh',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: 'linear-gradient(135deg, #0f172a 0%, #1e3a5f 50%, #0f172a 100%)',
  },
  card: {
    background: 'rgba(255, 255, 255, 0.05)',
    backdropFilter: 'blur(16px)',
    border: '1px solid rgba(255, 255, 255, 0.12)',
    borderRadius: '16px',
    padding: '48px 40px',
    width: '100%',
    maxWidth: '420px',
    textAlign: 'center',
    boxShadow: '0 25px 60px rgba(0,0,0,0.5)',
  },
  logoArea: {
    marginBottom: '24px',
  },
  logoIcon: {
    fontSize: '52px',
    marginBottom: '12px',
  },
  title: {
    color: '#f1f5f9',
    fontSize: '24px',
    fontWeight: 700,
    margin: '0 0 6px 0',
    fontFamily: "'Inter', sans-serif",
    letterSpacing: '-0.3px',
  },
  subtitle: {
    color: '#94a3b8',
    fontSize: '13px',
    margin: 0,
    fontFamily: "'Inter', sans-serif",
    letterSpacing: '0.3px',
  },
  divider: {
    height: '1px',
    background: 'rgba(255,255,255,0.08)',
    margin: '24px 0',
  },
  prompt: {
    color: '#cbd5e1',
    fontSize: '14px',
    marginBottom: '24px',
    fontFamily: "'Inter', sans-serif",
    lineHeight: 1.6,
  },
  loginBtn: {
    width: '100%',
    padding: '14px 24px',
    background: 'linear-gradient(135deg, #3b82f6, #1d4ed8)',
    color: '#fff',
    border: 'none',
    borderRadius: '10px',
    fontSize: '15px',
    fontWeight: 600,
    cursor: 'pointer',
    fontFamily: "'Inter', sans-serif",
    letterSpacing: '0.2px',
    transition: 'transform 0.15s ease, box-shadow 0.15s ease',
    boxShadow: '0 4px 20px rgba(59, 130, 246, 0.4)',
  },
  error: {
    color: '#f87171',
    fontSize: '13px',
    marginTop: '16px',
    fontFamily: "'Inter', sans-serif",
  },
  footer: {
    color: '#475569',
    fontSize: '11px',
    marginTop: '24px',
    fontFamily: "'Inter', sans-serif",
  },
};

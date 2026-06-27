import { useNavigate } from 'react-router-dom';

export default function LoginPage() {
  const navigate = useNavigate();

  function handleLogin() {
    localStorage.setItem('dev_user', JSON.stringify({
      service_no: 'DEV-00000',
      role: 'operator',
    }));
    navigate('/dashboard');
  }

  return (
    <div style={styles.container}>
      <div style={styles.card}>
        <div style={styles.logoArea}>
          <div style={styles.logoIcon}>shield</div>
          <h1 style={styles.title}>AI Help Desk</h1>
          <p style={styles.subtitle}>Indian Air Force - IT Support Portal</p>
        </div>
        <div style={styles.divider} />
        <p style={styles.prompt}>Please authenticate with your Service Number to continue.</p>
        <button id='btn-keycloak-login' style={styles.loginBtn} onClick={handleLogin}>
          Login with Service Number
        </button>
        <p style={styles.footer}>Authorised personnel only. All access is logged.</p>
      </div>
    </div>
  );
}

const styles = {
  container: { minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'linear-gradient(135deg, #0f172a 0%, #1e3a5f 50%, #0f172a 100%)' },
  card: { background: 'rgba(255,255,255,0.05)', backdropFilter: 'blur(16px)', border: '1px solid rgba(255,255,255,0.12)', borderRadius: '16px', padding: '48px 40px', width: '100%', maxWidth: '420px', textAlign: 'center', boxShadow: '0 25px 60px rgba(0,0,0,0.5)' },
  logoArea: { marginBottom: '24px' },
  logoIcon: { fontSize: '52px', marginBottom: '12px' },
  title: { color: '#f1f5f9', fontSize: '24px', fontWeight: 700, margin: '0 0 6px 0' },
  subtitle: { color: '#94a3b8', fontSize: '13px', margin: 0 },
  divider: { height: '1px', background: 'rgba(255,255,255,0.08)', margin: '24px 0' },
  prompt: { color: '#cbd5e1', fontSize: '14px', marginBottom: '24px', lineHeight: 1.6 },
  loginBtn: { width: '100%', padding: '14px 24px', background: 'linear-gradient(135deg, #3b82f6, #1d4ed8)', color: '#fff', border: 'none', borderRadius: '10px', fontSize: '15px', fontWeight: 600, cursor: 'pointer', boxShadow: '0 4px 20px rgba(59,130,246,0.4)' },
  footer: { color: '#475569', fontSize: '11px', marginTop: '24px' },
};
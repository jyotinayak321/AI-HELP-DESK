import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { useAuth } from 'react-oidc-context';
import Sidebar from './components/layout/Sidebar';
import Topbar from './components/layout/Topbar';
import Dashboard from './pages/Dashboard';
import SubmitComplaint from './pages/SubmitComplaint';
import ClassifyReview from './pages/ClassifyReview';
import TicketList from './pages/TicketList';
import TicketDetail from './pages/TicketDetail';
import Registry from './pages/Registry';
import TeamQueue from './pages/TeamQueue';
import LoginPage from './pages/LoginPage';

/**
 * AUTH_GUARD_ENABLED controls whether the Login page is shown.
 *
 * Set this to `true` only when Keycloak is running (docker-compose up -d).
 * Set to `false` during normal development to skip the login screen entirely.
 *
 * NOTE: The backend has a separate AUTH_ENABLED flag in config.py that controls
 * whether the JWT tokens are actually validated on the API side.
 */
const AUTH_GUARD_ENABLED = true;

function App() {
  const auth = useAuth();

  // ── Auth Guard ──────────────────────────────────────────────────────────────
  // Only block the user if AUTH_GUARD_ENABLED is explicitly turned on.
  // This way, the app works 100% normally without Keycloak.
  if (AUTH_GUARD_ENABLED) {
    // While Keycloak is still loading, show a spinner
    if (auth.isLoading) {
      return (
        <div style={{
          display: 'flex', height: '100vh', alignItems: 'center',
          justifyContent: 'center', background: '#0f172a'
        }}>
          <div style={{ color: '#94a3b8', fontSize: '16px' }}>
            Connecting to authentication server...
          </div>
        </div>
      );
    }

    // If not authenticated, show the login page
    if (!auth.isAuthenticated) {
      return <LoginPage />;
    }
  }

  // ── Normal App ──────────────────────────────────────────────────────────────
  return (
    <BrowserRouter>
      <Toaster position="top-right" toastOptions={{ style: { fontSize: '13px' } }} />
      <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
        <Sidebar />
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <Topbar />
          <div style={{ flex: 1, overflowY: 'auto', padding: '24px', background: '#f8fafc' }}>
            <Routes>
              <Route path="/" element={<Navigate to="/dashboard" replace />} />
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/submit" element={<SubmitComplaint />} />
              <Route path="/classify" element={<ClassifyReview />} />
              <Route path="/tickets" element={<TicketList />} />
              <Route path="/tickets/:ticketNumber" element={<TicketDetail />} />
              <Route path="/queue" element={<TeamQueue />} />
              <Route path="/registry" element={<Registry />} />
            </Routes>
          </div>
        </div>
      </div>
    </BrowserRouter>
  );
}

export default App;
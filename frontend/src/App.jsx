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
import { useCurrentUser } from './useCurrentUser';

const AUTH_GUARD_ENABLED = true;

function App() {
  const auth = useAuth();
  const { isOperator, isAdmin } = useCurrentUser();

  if (AUTH_GUARD_ENABLED) {
    if (auth.isLoading) {
      return (
        <div style={{
          display: 'flex', height: '100vh',
          alignItems: 'center', justifyContent: 'center',
          background: '#060d1a', flexDirection: 'column', gap: 16,
        }}>
          <div style={{
            width: 36, height: 36,
            border: '3px solid rgba(30,144,255,0.15)',
            borderTop: '3px solid #1E90FF',
            borderRadius: '50%',
            animation: 'spin 0.8s linear infinite',
          }} />
          <div style={{ color: '#4d6480', fontSize: '0.875rem' }}>
            Connecting to authentication server...
          </div>
          <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
        </div>
      );
    }

    if (!auth.isAuthenticated) {
      return <LoginPage />;
    }
  }

  return (
    <BrowserRouter>
      <Toaster
        position="top-right"
        toastOptions={{
          style: {
            background: '#111f35',
            color: '#e8edf5',
            border: '1px solid rgba(30,144,255,0.15)',
            fontSize: '13px',
            borderRadius: '10px',
          },
        }}
      />

      {/* Outer wrapper */}
      <div style={{ display: 'flex', minHeight: '100vh', background: '#060d1a' }}>

        {/* Fixed Sidebar — 220px wide */}
        <Sidebar />

        {/* Everything to the right of sidebar */}
        <div style={{
          marginLeft: '220px',
          flex: 1,
          borderLeft: '1px solid rgba(30,144,255,0.15)',
          display: 'flex',
          flexDirection: 'column',
          minHeight: '100vh',
          minWidth: 0,
        }}>

          {/* Sticky topbar */}
          <Topbar />

          {/* Scrollable page area */}
          <main style={{
            flex: 1,
            overflowY: 'auto',
            overflowX: 'hidden',
            background: '#060d1a',
            padding: '24px',
          }}>
            {/* Centered content — max 1100px */}
            <div style={{ width: '100%' }}>
              <Routes>
                <Route path="/"          element={<Navigate to="/dashboard" replace />} />
                <Route path="/dashboard" element={<Dashboard />} />
                {isOperator && (
                  <>
                    <Route path="/submit"   element={<SubmitComplaint />} />
                    <Route path="/classify" element={<ClassifyReview />} />
                    <Route path="/tickets"  element={<TicketList />} />
                    <Route path="/registry" element={<Registry />} />
                  </>
                )}
                {isAdmin && (
                  <Route path="/queue" element={<TeamQueue />} />
                )}
                <Route path="/tickets/:ticketNumber" element={<TicketDetail />} />
                <Route path="*" element={<Navigate to="/dashboard" replace />} />
              </Routes>
            </div>
          </main>
        </div>
      </div>
    </BrowserRouter>
  );
}

export default App;
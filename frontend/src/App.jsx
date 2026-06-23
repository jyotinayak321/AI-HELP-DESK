import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import Sidebar from './components/layout/Sidebar';
import Topbar from './components/layout/Topbar';
import Dashboard from './pages/Dashboard';
import SubmitComplaint from './pages/SubmitComplaint';
import ClassifyReview from './pages/ClassifyReview';
import TicketList from './pages/TicketList';
import TicketDetail from './pages/TicketDetail';
import Registry from './pages/Registry';

function App() {
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
              <Route path="/registry" element={<Registry />} />
            </Routes>
          </div>
        </div>
      </div>
    </BrowserRouter>
  );
}
export default App;
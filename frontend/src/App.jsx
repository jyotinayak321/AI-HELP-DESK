import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { ThemeProvider } from './context/ThemeContext';
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
    <ThemeProvider>
      <BrowserRouter>
        <Toaster position="top-right" toastOptions={{ style: { fontSize: '13px' } }} />
        <div className="flex min-h-screen bg-background text-on-surface">
          <Sidebar />
          <main className="ml-sidebar-width flex-1 min-h-screen flex flex-col">
            <Topbar />
            <div className="flex-1 overflow-y-auto px-margin-desktop py-section-gap max-w-container-max mx-auto w-full">
              <Routes>
                <Route path="/" element={<Navigate to="/submit" replace />} />
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/submit" element={<SubmitComplaint />} />
                <Route path="/classify" element={<ClassifyReview />} />
                <Route path="/tickets" element={<TicketList />} />
                <Route path="/tickets/:ticketNumber" element={<TicketDetail />} />
                <Route path="/registry" element={<Registry />} />
              </Routes>
            </div>
          </main>
        </div>
      </BrowserRouter>
    </ThemeProvider>
  );
}
export default App;
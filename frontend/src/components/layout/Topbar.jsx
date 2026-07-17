import { useLocation } from 'react-router-dom';
import { useCurrentUser } from '../../useCurrentUser';
import { useTheme } from '../../ThemeContext';

const pageTitles = {
  '/dashboard': 'Dashboard',
  '/submit':    'Submit Complaint',
  '/tickets':   'Tickets',
  '/registry':  'App Registry',
  '/classify':  'Classify Review',
  '/queue':     'Team Queue',
};

export default function Topbar() {
  const { pathname } = useLocation();
  const { serviceNo, role } = useCurrentUser();
  const { theme, toggleTheme } = useTheme();

  const title = pageTitles[pathname] ||
    (pathname.startsWith('/tickets/') ? 'Ticket Detail' : 'AI Help Desk');

  const now = new Date().toLocaleDateString('en-IN', {
    weekday: 'short', day: 'numeric', month: 'short', year: 'numeric',
  });

  return (
    <header style={{
      height: 50,
      background: 'var(--navy-900)',
      borderBottom: '1px solid var(--border)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '0 24px',
      position: 'sticky',
      top: 0,
      zIndex: 50,
      width: '100%',
      flexShrink: 0,
      boxSizing: 'border-box',
    }}>

      {/* Left — Breadcrumb only */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
          AI Help Desk
        </span>
        <span style={{ color: 'var(--text-muted)', fontSize: '0.72rem' }}>›</span>
        <span style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-primary)' }}>
          {title}
        </span>
      </div>

      {/* Right — Theme toggle + Date + User */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0 }}>
        <button
          onClick={toggleTheme}
          className="btn btn-ghost btn-sm"
          title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          style={{ padding: '5px 9px', fontSize: '0.85rem' }}
        >
          {theme === 'dark' ? '🌙' : '☀️'}
        </button>

        <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
          {now}
        </span>

        <div style={{ width: 1, height: 18, background: 'var(--border-light)' }} />

        <div style={{
          display: 'flex', alignItems: 'center', gap: 6,
          background: 'var(--surface-2)',
          border: '1px solid var(--border-light)',
          borderRadius: 'var(--radius-md)',
          padding: '5px 12px',
          fontSize: '0.75rem',
          color: 'var(--text-secondary)',
          whiteSpace: 'nowrap',
        }}>
          <div style={{
            width: 6, height: 6, borderRadius: '50%',
            background: 'var(--success)',
            boxShadow: '0 0 5px var(--success)',
            flexShrink: 0,
          }} />
          {serviceNo || 'Operator'}{role ? ` · ${role}` : ''}
        </div>
      </div>
    </header>
  );
}
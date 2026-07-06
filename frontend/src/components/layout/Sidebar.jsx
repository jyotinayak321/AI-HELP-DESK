import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from 'react-oidc-context';
import { useCurrentUser } from '../../useCurrentUser';

const navItems = [
  { to: '/dashboard', icon: '⊞', label: 'Dashboard' },
  { to: '/submit',    icon: '＋', label: 'Submit Complaint' },
  { to: '/tickets',   icon: '☰', label: 'Tickets' },
  { to: '/registry',  icon: '⊟', label: 'App Registry' },
];

export default function Sidebar() {
  const auth = useAuth();
  const navigate = useNavigate();
  const { user } = useCurrentUser();

  const initials = user?.service_no
    ? user.service_no.slice(0, 2).toUpperCase()
    : 'OP';

  const handleLogout = () => {
    auth.removeUser();
    auth.signoutRedirect().catch(() => {
      navigate('/');
    });
  };

  return (
    <aside className="sidebar">
      {/* Brand */}
      <div className="sidebar-brand">
        <div className="sidebar-brand-icon">🛡️</div>
        <div className="sidebar-brand-text">
          <div className="sidebar-brand-title">AI Help Desk</div>
          <div className="sidebar-brand-sub">IT Support Portal</div>
        </div>
      </div>

      {/* Nav */}
      <nav className="sidebar-nav">
        <div className="sidebar-section-label">Navigation</div>
        {navItems.map(item => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              `sidebar-nav-item${isActive ? ' active' : ''}`
            }
          >
            <span className="nav-icon">{item.icon}</span>
            {item.label}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="sidebar-footer">
        <div className="sidebar-user">
          <div className="sidebar-avatar">{initials}</div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div className="sidebar-user-name truncate">
              {user?.service_no || 'Operator'}
            </div>
            <div className="sidebar-user-role">
              {user?.role || 'operator'}
            </div>
          </div>
        </div>
        <button
          onClick={handleLogout}
          className="btn btn-ghost btn-sm w-full"
          style={{ marginTop: 8, justifyContent: 'center', color: 'var(--danger)', borderColor: 'rgba(239,68,68,0.2)' }}
        >
          ⏻ Logout
        </button>
      </div>
    </aside>
  );
}
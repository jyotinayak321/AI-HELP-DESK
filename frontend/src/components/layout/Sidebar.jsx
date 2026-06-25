import { NavLink } from 'react-router-dom';
import { LayoutDashboard, PlusCircle, Ticket, Database, ListTodo, LogOut } from 'lucide-react';
import { useCurrentUser } from '../../useCurrentUser';

import { useAuth } from 'react-oidc-context';

function Sidebar() {
  const auth = useAuth();
  const { isOperator, isAdmin } = useCurrentUser();

  const navItems = [
    { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard', show: true },
    { to: '/submit',    icon: PlusCircle,       label: 'Submit Complaint', show: isOperator },
    { to: '/tickets',   icon: Ticket,           label: 'Tickets', show: isOperator },
    { to: '/queue',     icon: ListTodo,         label: 'My Queue', show: isAdmin },
    { to: '/registry',  icon: Database,         label: 'App Registry', show: isOperator },
  ];

  return (
    <div style={{
      width: '220px', background: '#0a1628', color: '#e0e6f0',
      display: 'flex', flexDirection: 'column', flexShrink: 0,
    }}>
      <div style={{ padding: '20px 16px', borderBottom: '0.5px solid rgba(255,255,255,0.1)' }}>
        <div style={{ color: '#7eb8f7', fontWeight: 600, fontSize: '14px' }}>✈ IAF HELP DESK</div>
        <div style={{ color: 'rgba(255,255,255,0.4)', fontSize: '11px', marginTop: '3px' }}>UDAAN — Phase 1</div>
      </div>
      <nav style={{ padding: '12px 0', flex: 1 }}>
        {navItems.filter(item => item.show).map(({ to, icon: Icon, label }) => (
          <NavLink key={to} to={to} style={({ isActive }) => ({
            display: 'flex', alignItems: 'center', gap: '10px',
            padding: '9px 16px', fontSize: '13px', textDecoration: 'none',
            color: isActive ? '#fff' : 'rgba(255,255,255,0.55)',
            background: isActive ? 'rgba(126,184,247,0.12)' : 'transparent',
            borderLeft: isActive ? '2px solid #7eb8f7' : '2px solid transparent',
            transition: 'all 0.15s',
          })}>
            <Icon size={16} />
            {label}
          </NavLink>
        ))}
      </nav>
      
      {/* Action / Footer Area */}
      <div style={{ padding: '12px', borderTop: '0.5px solid rgba(255,255,255,0.1)' }}>
        <button 
          onClick={() => auth.signoutRedirect()}
          style={{
            width: '100%', display: 'flex', alignItems: 'center', gap: '10px',
            padding: '9px 12px', fontSize: '13px', color: '#ef4444',
            background: 'transparent', border: 'none', borderRadius: '6px',
            cursor: 'pointer', textAlign: 'left', transition: 'background 0.15s'
          }}
          onMouseEnter={e => e.currentTarget.style.background = 'rgba(239,68,68,0.1)'}
          onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
        >
          <LogOut size={16} />
          Logout
        </button>
        <div style={{
          marginTop: '12px', padding: '0 4px',
          fontSize: '11px', color: 'rgba(255,255,255,0.35)',
        }}>
          Air Force Station Rajokri
        </div>
      </div>
    </div>
  );
}
export default Sidebar;
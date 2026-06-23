import { NavLink } from 'react-router-dom';
import { LayoutDashboard, PlusCircle, Ticket, Database } from 'lucide-react';

const navItems = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/submit',    icon: PlusCircle,       label: 'Submit Complaint' },
  { to: '/tickets',   icon: Ticket,           label: 'Tickets' },
  { to: '/registry',  icon: Database,         label: 'App Registry' },
];

function Sidebar() {
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
        {navItems.map(({ to, icon: Icon, label }) => (
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
      <div style={{
        padding: '12px 16px', borderTop: '0.5px solid rgba(255,255,255,0.1)',
        fontSize: '11px', color: 'rgba(255,255,255,0.35)',
      }}>
        Air Force Station Rajokri
      </div>
    </div>
  );
}
export default Sidebar;
import { NavLink } from 'react-router-dom';

const navItems = [
  { to: '/submit',    icon: 'dashboard', label: 'Intake Console' },
  { to: '/tickets',   icon: 'confirmation_number', label: 'Tickets' },
  { to: '/registry',  icon: 'database', label: 'Registry' },
  { to: '/triage',    icon: 'auto_awesome_motion', label: 'Examples Triage' },
];

function Sidebar() {
  return (
    <aside className="flex flex-col h-full py-section-gap px-4 w-sidebar-width fixed left-0 top-0 border-r border-outline-variant bg-surface z-50">
      <div className="mb-10 px-2">
        <span className="font-headline-md text-headline-md font-bold text-primary">AI Help Desk</span>
      </div>
      <nav className="flex-1 flex flex-col gap-1">
        {navItems.map(({ to, icon, label }) => (
          <NavLink key={to} to={to} 
            className={({ isActive }) => 
              `flex items-center gap-3 px-4 py-3 rounded-lg transition-colors duration-200 font-body-md text-body-md ${
                isActive 
                  ? 'text-primary bg-secondary-container font-semibold' 
                  : 'text-on-surface-variant hover:bg-surface-container-high'
              }`
            }>
            <span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1" }}>
              {icon}
            </span>
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>
      <div className="mt-auto border-t border-outline-variant pt-4 px-2">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-primary-container flex items-center justify-center text-on-primary-container font-bold text-xs">OP</div>
          <div className="flex flex-col">
            <span className="font-label-md text-on-surface">Operator 042</span>
            <span className="text-[10px] text-on-surface-variant uppercase tracking-wider font-bold">Shift A</span>
          </div>
        </div>
      </div>
    </aside>
  );
}
export default Sidebar;
import { useLocation } from 'react-router-dom';
import { useTheme } from '../../context/ThemeContext';

const PAGE_TITLES = {
  '/dashboard': 'Dashboard',
  '/submit':    'Intake Console',
  '/classify':  'Review Classification',
  '/tickets':   'Tickets',
  '/registry':  'Registry',
};

function Topbar() {
  const { pathname } = useLocation();
  const { isDark, toggle } = useTheme();
  const title = PAGE_TITLES[pathname] || 'AI Help Desk';

  return (
    <header className="flex justify-between items-center w-full px-margin-desktop h-16 sticky top-0 z-40 bg-surface-container-lowest border-b border-outline-variant shadow-sm shrink-0 transition-colors duration-300">
      <div className="flex items-center gap-4">
        <button className="material-symbols-outlined text-primary p-2 hover:bg-surface-container rounded-full cursor-pointer active:opacity-80">menu</button>
        <h1 className="font-headline-sm text-headline-sm text-primary font-black">{title}</h1>
      </div>
      
      {pathname === '/registry' ? (
        <div className="flex items-center gap-4">
          <button className="bg-primary text-on-primary px-4 py-2 rounded-lg font-label-md flex items-center gap-2 hover:opacity-90 transition-opacity shadow-sm">
            <span className="material-symbols-outlined text-[18px]">add</span>
            Add Application
          </button>
          <div className="h-8 w-px bg-outline-variant mx-2"></div>

          {/* Dark mode toggle */}
          <button
            id="theme-toggle-btn"
            className="theme-toggle"
            onClick={toggle}
            aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
            title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            <span
              className="toggle-icon material-symbols-outlined text-[20px]"
              style={{ transform: isDark ? 'rotate(180deg)' : 'rotate(0deg)' }}
            >
              {isDark ? 'light_mode' : 'dark_mode'}
            </span>
          </button>

          <div className="w-9 h-9 rounded-full bg-surface-container-highest border border-outline-variant flex items-center justify-center overflow-hidden cursor-pointer">
            <img className="w-full h-full object-cover" src="https://lh3.googleusercontent.com/aida-public/AB6AXuBcIyUpQw2ws-gT2GW3ur7Vbbm42XbP_GwjhLBZeVPfg29MFayllgOEPcNM0ws7mYJ9powQJG45MXrh8C5C-89SMD--r3F14gjwKCoVNJ7VXBNlrh52pcoJNWx1nTZ24owL3XAXbore5o9cQzWHpdzZdiU0G6M_4ORb8rfgxUS2NXBXEGvWRg7Yympmylb_W7DikyIdB-fRiFsiqA9s6iMIeeC4alKiFaG0M6UIChX9Wd2RyQcvYTHAehi2lSRJYGvyLVjgg9KvTDOT" />
          </div>
        </div>
      ) : (
        <div className="flex items-center gap-4">
          <div className="hidden md:flex items-center bg-surface-container px-3 py-1.5 rounded-full border border-outline-variant transition-colors duration-300">
            <span className="material-symbols-outlined text-sm text-on-surface-variant mr-2">search</span>
            <input className="bg-transparent border-none focus:ring-0 text-sm w-48 text-on-surface outline-none" placeholder="Global search..." type="text"/>
          </div>
          <span className="material-symbols-outlined text-on-surface-variant cursor-pointer hover:bg-surface-container p-2 rounded-full transition-colors">notifications</span>

          {/* Dark mode toggle */}
          <button
            id="theme-toggle-btn"
            className="theme-toggle"
            onClick={toggle}
            aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
            title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            <span
              className="toggle-icon material-symbols-outlined text-[20px]"
              style={{ transform: isDark ? 'rotate(180deg)' : 'rotate(0deg)' }}
            >
              {isDark ? 'light_mode' : 'dark_mode'}
            </span>
          </button>

          <div className="w-8 h-8 rounded-full bg-surface-container border border-outline-variant flex items-center justify-center cursor-pointer transition-colors duration-300">
            <span className="material-symbols-outlined text-sm">person</span>
          </div>
        </div>
      )}
    </header>
  );
}

export default Topbar;
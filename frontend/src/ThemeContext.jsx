/**
 * ThemeContext.jsx
 * ----------------
 * Dark/light theme toggle. Persists the choice to localStorage and stamps
 * `data-theme` on <html>, which index.css's `:root[data-theme="light"]`
 * override block reacts to. Defaults to 'dark' (the app's original look)
 * when nothing is stored yet.
 */
import { createContext, useContext, useEffect, useState } from 'react';

const STORAGE_KEY = 'helpdesk-theme';
const ThemeContext = createContext(null);

function getInitialTheme() {
  const stored = localStorage.getItem(STORAGE_KEY);
  return stored === 'light' || stored === 'dark' ? stored : 'dark';
}

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(getInitialTheme);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem(STORAGE_KEY, theme);
  }, [theme]);

  const toggleTheme = () => setTheme(t => (t === 'dark' ? 'light' : 'dark'));

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error('useTheme() must be used within a ThemeProvider');
  return ctx;
}

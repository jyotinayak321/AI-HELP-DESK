// Shared recharts styling so all four dashboard charts read as one system
// against either theme. Recharts SVG `fill`/`stroke` props are plain SVG
// attributes (not CSS `style`), so they can't resolve CSS custom properties —
// literal hex values here are copies of the light/dark vars in index.css.
export const CHART_PALETTE = ['#3B82F6', '#22D3EE', '#8B5CF6', '#22C55E', '#F59E0B', '#EF4444'];

const DARK = {
  grid: 'rgba(255,255,255,0.06)',
  axis: '#64748B',      // --text-muted (dark theme)
  text: '#94A3B8',      // --text-secondary (dark theme)
  accent: '#3B82F6',    // --accent
  tooltip: {
    background: '#24324A',   // --surface-2 (dark theme)
    border: '1px solid rgba(255,255,255,0.06)',
    color: '#F8FAFC',        // --text-primary (dark theme)
  },
  legend: '#94A3B8',
};

const LIGHT = {
  grid: 'rgba(15,23,42,0.08)',
  axis: '#94A3B8',      // --text-muted (light theme)
  text: '#475569',      // --text-secondary (light theme)
  accent: '#3B82F6',
  tooltip: {
    background: '#FFFFFF',   // --surface-1 (light theme)
    border: '1px solid rgba(15,23,42,0.08)',
    color: '#0F172A',        // --text-primary (light theme)
  },
  legend: '#475569',
};

export function getChartColors(theme) {
  return theme === 'light' ? LIGHT : DARK;
}

export function getTooltipStyle(theme) {
  const c = getChartColors(theme);
  return {
    background: c.tooltip.background,
    border: c.tooltip.border,
    borderRadius: 10,
    fontSize: 12,
    color: c.tooltip.color,
  };
}

export function getLegendStyle(theme) {
  return { fontSize: 12, color: getChartColors(theme).legend };
}

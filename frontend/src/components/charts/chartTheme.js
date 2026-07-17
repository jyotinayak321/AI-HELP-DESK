// Shared recharts styling so all four dashboard charts read as one system
// against the dark theme. Recharts SVG `fill`/`stroke` props are plain SVG
// attributes (not CSS `style`), so they can't resolve CSS custom properties —
// literal hex values here are copies of the vars in index.css `:root`.
export const CHART_COLORS = {
  grid: 'rgba(255,255,255,0.06)',
  axis: '#64748B',      // --text-muted
  text: '#94A3B8',      // --text-secondary
  accent: '#3B82F6',    // --accent
  accent2: '#22D3EE',
};

export const CHART_PALETTE = ['#3B82F6', '#22D3EE', '#8B5CF6', '#22C55E', '#F59E0B', '#EF4444'];

export const tooltipStyle = {
  background: '#24324A',       // --surface-2
  border: '1px solid rgba(255,255,255,0.06)',
  borderRadius: 10,
  fontSize: 12,
  color: '#F8FAFC',
};

export const legendStyle = {
  fontSize: 12,
  color: '#94A3B8',
};

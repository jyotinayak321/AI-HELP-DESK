import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { getTooltipStyle, getChartColors } from './chartTheme';
import { useTheme } from '../../ThemeContext';

export default function AppComplaintsBarChart({ tickets }) {
  const { theme } = useTheme();
  const colors = getChartColors(theme);
  const counts = {};
  tickets.forEach(t => {
    const app = t.primary_application_name || 'Unknown';
    counts[app] = (counts[app] || 0) + 1;
  });
  const data = Object.entries(counts)
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 8);

  if (data.length === 0) {
    return <div style={{ padding: 32, textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.82rem' }}>No ticket data yet</div>;
  }

  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} layout="vertical" margin={{ top: 8, right: 16, left: 8, bottom: 0 }}>
        <CartesianGrid stroke={colors.grid} horizontal={false} />
        <XAxis type="number" allowDecimals={false} tick={{ fill: colors.axis, fontSize: 11 }} axisLine={false} tickLine={false} />
        <YAxis
          type="category"
          dataKey="name"
          width={110}
          tick={{ fill: colors.text, fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          tickFormatter={(v) => (v.length > 16 ? `${v.slice(0, 15)}…` : v)}
        />
        <Tooltip contentStyle={getTooltipStyle(theme)} cursor={{ fill: colors.grid }} />
        <Bar dataKey="value" fill={colors.accent} radius={[0, 6, 6, 0]} maxBarSize={18} />
      </BarChart>
    </ResponsiveContainer>
  );
}

import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { STATUS_COLOR } from '../../constants/enums';
import { getTooltipStyle, getLegendStyle, getChartColors } from './chartTheme';
import { useTheme } from '../../ThemeContext';

export default function TicketStatusPieChart({ tickets }) {
  const { theme } = useTheme();
  const colors = getChartColors(theme);
  const counts = {};
  tickets.forEach(t => {
    const status = t.status || 'open';
    counts[status] = (counts[status] || 0) + 1;
  });
  const data = Object.entries(counts).map(([status, value]) => ({ name: status, value }));

  if (data.length === 0) {
    return <div style={{ padding: 32, textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.82rem' }}>No ticket data yet</div>;
  }

  return (
    <ResponsiveContainer width="100%" height={220}>
      <PieChart>
        <Pie data={data} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={50} outerRadius={80} paddingAngle={2}>
          {data.map((entry, i) => (
            <Cell key={entry.name} fill={STATUS_COLOR[entry.name] || '#64748B'} stroke="none" />
          ))}
        </Pie>
        <Tooltip contentStyle={getTooltipStyle(theme)} labelStyle={{ color: colors.tooltip.color, textTransform: 'capitalize' }} />
        <Legend wrapperStyle={getLegendStyle(theme)} formatter={(value) => <span style={{ textTransform: 'capitalize' }}>{value}</span>} />
      </PieChart>
    </ResponsiveContainer>
  );
}

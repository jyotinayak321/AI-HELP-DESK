import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { SEVERITY_LEVELS, SEVERITY_COLOR } from '../../constants/enums';
import { CHART_COLORS, tooltipStyle } from './chartTheme';

export default function SeverityBarChart({ tickets }) {
  const counts = {};
  tickets.forEach(t => {
    const sev = t.severity || 'normal';
    counts[sev] = (counts[sev] || 0) + 1;
  });
  // Fixed order (low -> critical) so the chart reads as an escalation ladder.
  const order = ['low', 'normal', 'high', 'critical'];
  const data = order
    .filter(v => SEVERITY_LEVELS.some(s => s.value === v))
    .map(value => ({
      name: SEVERITY_LEVELS.find(s => s.value === value)?.label || value,
      value: counts[value] || 0,
      color: SEVERITY_COLOR[value],
    }));

  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}>
        <CartesianGrid stroke={CHART_COLORS.grid} vertical={false} />
        <XAxis dataKey="name" tick={{ fill: CHART_COLORS.axis, fontSize: 11 }} axisLine={{ stroke: CHART_COLORS.grid }} tickLine={false} />
        <YAxis allowDecimals={false} tick={{ fill: CHART_COLORS.axis, fontSize: 11 }} axisLine={false} tickLine={false} />
        <Tooltip contentStyle={tooltipStyle} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
        <Bar dataKey="value" radius={[6, 6, 0, 0]} maxBarSize={48}>
          {data.map(entry => <Cell key={entry.name} fill={entry.color} />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

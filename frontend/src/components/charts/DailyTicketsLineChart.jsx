import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { getTooltipStyle, getChartColors } from './chartTheme';
import { useTheme } from '../../ThemeContext';

const DAYS = 14;
const ONE_DAY = 24 * 60 * 60 * 1000;

export default function DailyTicketsLineChart({ tickets }) {
  const { theme } = useTheme();
  const colors = getChartColors(theme);
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());

  const buckets = new Map();
  for (let i = DAYS - 1; i >= 0; i--) {
    const d = new Date(today.getTime() - i * ONE_DAY);
    const key = d.toISOString().slice(0, 10);
    buckets.set(key, { name: d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short' }), value: 0 });
  }

  tickets.forEach(t => {
    if (!t.created_at) return;
    const key = new Date(t.created_at).toISOString().slice(0, 10);
    if (buckets.has(key)) buckets.get(key).value += 1;
  });

  const data = Array.from(buckets.values());

  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={data} margin={{ top: 8, right: 16, left: -20, bottom: 0 }}>
        <CartesianGrid stroke={colors.grid} vertical={false} />
        <XAxis dataKey="name" tick={{ fill: colors.axis, fontSize: 10 }} axisLine={{ stroke: colors.grid }} tickLine={false} interval={2} />
        <YAxis allowDecimals={false} tick={{ fill: colors.axis, fontSize: 11 }} axisLine={false} tickLine={false} />
        <Tooltip contentStyle={getTooltipStyle(theme)} />
        <Line type="monotone" dataKey="value" stroke={colors.accent} strokeWidth={2.5} dot={{ r: 3, fill: colors.accent, strokeWidth: 0 }} activeDot={{ r: 5 }} />
      </LineChart>
    </ResponsiveContainer>
  );
}

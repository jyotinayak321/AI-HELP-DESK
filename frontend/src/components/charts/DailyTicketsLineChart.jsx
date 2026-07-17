import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { CHART_COLORS, tooltipStyle } from './chartTheme';

const DAYS = 14;
const ONE_DAY = 24 * 60 * 60 * 1000;

export default function DailyTicketsLineChart({ tickets }) {
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
        <CartesianGrid stroke={CHART_COLORS.grid} vertical={false} />
        <XAxis dataKey="name" tick={{ fill: CHART_COLORS.axis, fontSize: 10 }} axisLine={{ stroke: CHART_COLORS.grid }} tickLine={false} interval={2} />
        <YAxis allowDecimals={false} tick={{ fill: CHART_COLORS.axis, fontSize: 11 }} axisLine={false} tickLine={false} />
        <Tooltip contentStyle={tooltipStyle} />
        <Line type="monotone" dataKey="value" stroke={CHART_COLORS.accent} strokeWidth={2.5} dot={{ r: 3, fill: CHART_COLORS.accent, strokeWidth: 0 }} activeDot={{ r: 5 }} />
      </LineChart>
    </ResponsiveContainer>
  );
}

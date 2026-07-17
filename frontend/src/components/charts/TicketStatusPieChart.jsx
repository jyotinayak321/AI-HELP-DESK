import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { STATUS_COLOR } from '../../constants/enums';
import { tooltipStyle, legendStyle } from './chartTheme';

export default function TicketStatusPieChart({ tickets }) {
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
        <Tooltip contentStyle={tooltipStyle} labelStyle={{ color: '#F8FAFC', textTransform: 'capitalize' }} />
        <Legend wrapperStyle={legendStyle} formatter={(value) => <span style={{ textTransform: 'capitalize' }}>{value}</span>} />
      </PieChart>
    </ResponsiveContainer>
  );
}

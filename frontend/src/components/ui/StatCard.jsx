export default function StatCard({ value, label, icon, color }) {
  return (
    <div className="stat-card">
      {icon && <div className="stat-card-icon">{icon}</div>}
      <div className="stat-card-value" style={color ? { color } : {}}>
        {value ?? '—'}
      </div>
      <div className="stat-card-label">{label}</div>
    </div>
  );
}

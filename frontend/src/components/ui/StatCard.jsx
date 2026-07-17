export default function StatCard({ icon, value, label, trendLabel, color, delay = 0 }) {
  return (
    <div className="stat-card animate-in" style={{ animationDelay: `${delay}ms` }}>
      {icon && (
        <div
          className="stat-card-icon-badge"
          style={{
            background: color ? `${color}1A` : 'var(--accent-glow)',
            color: color || 'var(--accent)',
          }}
        >
          {icon}
        </div>
      )}
      <div className="stat-card-value" style={color ? { color } : {}}>
        {value ?? '—'}
      </div>
      <div className="stat-card-label">{label}</div>
      {trendLabel && <div className="stat-card-trend">{trendLabel}</div>}
    </div>
  );
}

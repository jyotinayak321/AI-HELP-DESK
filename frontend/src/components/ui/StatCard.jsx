function StatCard({ label, value, sub, dotColor }) {
  return (
    <div style={{
      background: '#fff', border: '0.5px solid #e2e8f0',
      borderRadius: '12px', padding: '14px 16px',
    }}>
      <div style={{ fontSize: '11px', color: '#64748b', marginBottom: '6px' }}>{label}</div>
      <div style={{ fontSize: '24px', fontWeight: 500 }}>{value ?? '—'}</div>
      {sub && (
        <div style={{ fontSize: '11px', color: '#64748b', marginTop: '3px', display: 'flex', alignItems: 'center', gap: '5px' }}>
          <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: dotColor || '#639922', display: 'inline-block' }} />
          {sub}
        </div>
      )}
    </div>
  );
}
export default StatCard;
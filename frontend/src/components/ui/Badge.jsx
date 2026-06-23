function Badge({ label, color, bg }) {
  return (
    <span style={{
      fontSize: '10px', padding: '2px 10px', borderRadius: '10px',
      background: bg || '#f1f5f9', color: color || '#475569',
      fontWeight: 500, whiteSpace: 'nowrap',
    }}>
      {label}
    </span>
  );
}
export default Badge;
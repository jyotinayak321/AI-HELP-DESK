/**
 * Badge.jsx
 * Small colored pill used for Fault Type, Severity, and Status columns.
 * Falls back to theme variables if color/bg aren't provided, so it
 * never becomes invisible against the dark theme.
 */
export default function Badge({ label, color, bg }) {
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '3px 10px',
        borderRadius: '20px',
        fontSize: '11px',
        fontWeight: 600,
        textTransform: 'capitalize',
        letterSpacing: '0.02em',
        color: color || 'var(--text-primary)',
        background: bg || 'var(--surface-2)',
        border: `1px solid ${color ? color + '33' : 'var(--border)'}`,
        whiteSpace: 'nowrap',
      }}
    >
      {label}
    </span>
  );
}
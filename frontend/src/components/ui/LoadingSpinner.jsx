/**
 * LoadingSpinner.jsx
 * Skeleton-shimmer placeholder shown while a page's data is loading.
 * Keeps the same {text} prop call sites already use across the app
 * (Dashboard, TicketList, etc.) but renders shimmering bars instead of
 * a spinner — reads as a real product loading state, not a spinner delay.
 */
export default function LoadingSpinner({ text, rows = 3 }) {
  return (
    <div className="animate-in" style={{ padding: '4px 0' }}>
      {text && (
        <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: 14 }}>
          {text}
        </div>
      )}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="skeleton-bar" style={{ width: i === rows - 1 ? '60%' : '100%' }} />
        ))}
      </div>
    </div>
  );
}

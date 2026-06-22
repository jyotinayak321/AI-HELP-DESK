function StatCard({ label, value, sub, dotColor }) {
  return (
    <div className="bg-surface-container-lowest border border-outline-variant rounded-xl p-4 transition-colors duration-300">
      <div className="font-label-sm text-on-surface-variant mb-1.5">{label}</div>
      <div className="text-headline-lg text-on-surface font-medium">{value ?? '—'}</div>
      {sub && (
        <div className="font-label-sm text-on-surface-variant mt-1 flex items-center gap-1.5">
          <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: dotColor || '#639922', display: 'inline-block', flexShrink: 0 }} />
          {sub}
        </div>
      )}
    </div>
  );
}
export default StatCard;
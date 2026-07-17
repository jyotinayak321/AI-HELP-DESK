function ErrorMessage({ message, onRetry }) {
  return (
    <div className="alert alert-error animate-in" style={{ justifyContent: 'space-between' }}>
      <span>⚠ {message}</span>
      {onRetry && (
        <button onClick={onRetry} className="btn btn-ghost btn-sm" style={{ color: 'var(--danger)', borderColor: 'rgba(239,68,68,0.25)' }}>
          Retry
        </button>
      )}
    </div>
  );
}
export default ErrorMessage;
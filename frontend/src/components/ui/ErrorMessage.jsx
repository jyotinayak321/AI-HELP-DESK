function ErrorMessage({ message, onRetry }) {
  return (
    <div style={{
      padding: '16px', background: '#FCEBEB',
      border: '0.5px solid #F7C1C1', borderRadius: '8px',
      color: '#A32D2D', fontSize: '13px',
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    }}>
      <span>⚠ {message}</span>
      {onRetry && (
        <button onClick={onRetry} style={{
          background: 'none', border: '0.5px solid #A32D2D',
          color: '#A32D2D', borderRadius: '6px',
          padding: '4px 12px', cursor: 'pointer', fontSize: '12px',
        }}>Retry</button>
      )}
    </div>
  );
}
export default ErrorMessage;

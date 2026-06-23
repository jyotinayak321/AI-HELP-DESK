function LoadingSpinner({ text = 'Loading...' }) {
  return (
    <div style={{ padding: '40px', textAlign: 'center', color: '#64748b', fontSize: '14px' }}>
      <div style={{
        width: '28px', height: '28px',
        border: '2px solid #e2e8f0',
        borderTop: '2px solid #185FA5',
        borderRadius: '50%',
        animation: 'spin 0.8s linear infinite',
        margin: '0 auto 12px',
      }} />
      {text}
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
export default LoadingSpinner;
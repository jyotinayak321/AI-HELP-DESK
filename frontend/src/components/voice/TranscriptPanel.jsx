import React from 'react';

/**
 * TranscriptPanel Component
 * Displays the STT transcript, confidence score, and detected language.
 */
function TranscriptPanel({ transcript, confidence, language, processingTimeMs, state }) {
  if (!transcript && !state) return null;

  return (
    <div style={panelStyle}>
      <div style={headerStyle}>
        <span style={titleStyle}>Live Transcript</span>
        {confidence > 0 && (
          <span style={confidenceBadgeStyle(confidence)}>
            Confidence: {(confidence * 100).toFixed(1)}%
          </span>
        )}
      </div>
      
      <div style={contentStyle}>
        {transcript ? (
          <p style={textStyle}>"{transcript}"</p>
        ) : (
          <p style={placeholderStyle}>
            {state === 'OPERATOR_FALLBACK' || state === 'ERROR'
              ? '[Unrecognized or silent audio]'
              : state === 'GREETING' || state === 'CAPTURING_SERVICE_NUMBER' 
                ? 'Waiting for service number audio...' 
                : state === 'CAPTURING_COMPLAINT'
                  ? 'Waiting for complaint audio...'
                  : 'Waiting for speech...'}
          </p>
        )}
      </div>

      <div style={metaStyle}>
        {language && <span>Detected Language: <strong>{language.toUpperCase()}</strong></span>}
        {processingTimeMs > 0 && <span> • STT Latency: {processingTimeMs.toFixed(0)}ms</span>}
      </div>
    </div>
  );
}

// Inline Styles
const panelStyle = {
  background: '#ffffff',
  border: '1px solid #e2e8f0',
  borderRadius: '12px',
  padding: '16px',
  marginTop: '16px',
  boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
};

const headerStyle = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  marginBottom: '12px',
  paddingBottom: '8px',
  borderBottom: '1px solid #f1f5f9',
};

const titleStyle = {
  fontSize: '14px',
  fontWeight: 600,
  color: '#334155',
};

const confidenceBadgeStyle = (confidence) => {
  let bgColor = '#dcfce7'; // green
  let color = '#166534';
  if (confidence < 0.7) {
    bgColor = '#fef08a'; // yellow
    color = '#854d0e';
  }
  if (confidence < 0.5) {
    bgColor = '#fee2e2'; // red
    color = '#991b1b';
  }
  return {
    fontSize: '11px',
    fontWeight: 600,
    padding: '2px 8px',
    borderRadius: '12px',
    background: bgColor,
    color: color,
  };
};

const contentStyle = {
  minHeight: '60px',
  background: '#f8fafc',
  borderRadius: '8px',
  padding: '12px',
  border: '1px solid #e2e8f0',
};

const textStyle = {
  margin: 0,
  fontSize: '14px',
  lineHeight: '1.6',
  color: '#1e293b',
  fontStyle: 'italic',
};

const placeholderStyle = {
  margin: 0,
  fontSize: '13px',
  color: '#94a3b8',
  textAlign: 'center',
  marginTop: '10px',
};

const metaStyle = {
  fontSize: '11px',
  color: '#64748b',
  marginTop: '12px',
  textAlign: 'right',
};

export default TranscriptPanel;

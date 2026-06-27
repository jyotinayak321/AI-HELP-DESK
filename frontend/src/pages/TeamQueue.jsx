import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { listTickets } from '../api/tickets.api';
import { getAllApps } from '../api/registry.api';
import { TICKET_STATUSES, STATUS_COLOR, SEVERITY_COLOR } from '../constants/enums';
import Badge from '../components/ui/Badge';
import LoadingSpinner from '../components/ui/LoadingSpinner';
import ErrorMessage from '../components/ui/ErrorMessage';

/**
 * R-16: Team Queue View
 * Shows only open/in-progress tickets filtered by the operator's owning team.
 * The operator selects their team name from a dropdown.
 */
function TeamQueue() {
  const navigate   = useNavigate();
  const [tickets,  setTickets]  = useState([]);
  const [apps,     setApps]     = useState([]);
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState(null);
  const [teamName, setTeamName] = useState('');
  const [searched, setSearched] = useState(false);

  // Fetch all apps for the dropdown on mount
  useEffect(() => {
    getAllApps().then(res => {
      setApps(res.data || []);
    }).catch(err => console.error("Failed to fetch apps for team dropdown:", err));
  }, []);

  // Extract unique teams and sort them
  const uniqueTeams = [...new Set(apps.map(a => a.owning_team).filter(Boolean))].sort();

  async function load(team) {
    setLoading(true); setError(null); setSearched(true);
    try {
      // Filter to open + in_progress tickets for this team only
      const [openRes, inProgressRes] = await Promise.all([
        listTickets({ team, status: 'open',        limit: 100 }),
        listTickets({ team, status: 'in_progress', limit: 100 }),
      ]);
      const allTickets = [
        ...(openRes.data?.tickets ?? []),
        ...(inProgressRes.data?.tickets ?? []),
      ];
      // Sort by created_at descending
      allTickets.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
      setTickets(allTickets);
    } catch (e) {
      setError(e.response?.data?.detail || e.message || 'Failed to load queue');
    } finally { setLoading(false); }
  }

  function handleSearch(e) {
    e.preventDefault();
    if (teamName.trim()) load(teamName.trim());
  }

  const criticalCount = tickets.filter(t => t.severity === 'critical').length;
  const highCount     = tickets.filter(t => t.severity === 'high').length;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>

      {/* Header */}
      <div style={{ background: '#fff', border: '0.5px solid #e2e8f0', borderRadius: '12px', padding: '16px 20px' }}>
        <div style={{ fontSize: '15px', fontWeight: 600, marginBottom: '4px' }}>📋 My Team's Queue</div>
        <div style={{ fontSize: '12px', color: '#64748b', marginBottom: '14px' }}>
          Select your team to see only your active tickets (open + in progress).
        </div>
        <form onSubmit={handleSearch} style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
          <select
            value={teamName}
            onChange={e => {
              setTeamName(e.target.value);
              if (e.target.value) load(e.target.value);
            }}
            style={{
              flex: 1, padding: '9px 12px', fontSize: '13px',
              border: '0.5px solid #cbd5e1', borderRadius: '8px',
              outline: 'none', fontFamily: 'inherit', color: '#1a1a2e',
              background: '#fff'
            }}
          >
            <option value="">-- Select Team --</option>
            {uniqueTeams.map(team => (
              <option key={team} value={team}>{team}</option>
            ))}
          </select>
          <button type="submit" disabled={!teamName} style={{
            background: teamName ? '#185FA5' : '#cbd5e1', color: '#fff', border: 'none',
            borderRadius: '8px', padding: '9px 18px', fontSize: '13px',
            fontWeight: 500, cursor: teamName ? 'pointer' : 'not-allowed', whiteSpace: 'nowrap',
          }}>
            Load Queue
          </button>
        </form>
      </div>

      {/* Stats strip */}
      {searched && !loading && !error && (
        <div style={{ display: 'flex', gap: '12px' }}>
          {[
            { label: 'Total Active', value: tickets.length, color: '#185FA5', bg: '#EBF4FF' },
            { label: 'Critical',     value: criticalCount,  color: '#DC2626', bg: '#FEF2F2' },
            { label: 'High',         value: highCount,      color: '#D97706', bg: '#FFFBEB' },
          ].map(s => (
            <div key={s.label} style={{
              flex: 1, background: s.bg, border: `0.5px solid ${s.color}33`,
              borderRadius: '10px', padding: '12px 16px', textAlign: 'center',
            }}>
              <div style={{ fontSize: '22px', fontWeight: 700, color: s.color }}>{s.value}</div>
              <div style={{ fontSize: '11px', color: s.color, marginTop: '2px' }}>{s.label}</div>
            </div>
          ))}
        </div>
      )}

      {/* Ticket table */}
      {loading ? <LoadingSpinner text="Queue load ho raha hai..." /> :
       error   ? <ErrorMessage message={error} onRetry={() => load(teamName)} /> :
       searched && (
        <div style={{ background: '#fff', border: '0.5px solid #e2e8f0', borderRadius: '12px', overflow: 'hidden' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '140px 1fr 120px 110px 90px 80px', gap: '12px', padding: '10px 16px', background: '#f8fafc', fontSize: '11px', color: '#64748b', fontWeight: 500, borderBottom: '0.5px solid #e2e8f0' }}>
            <span>Ticket No.</span><span>Complaint</span><span>Application</span><span>Fault Type</span><span>Severity</span><span>Status</span>
          </div>
          {tickets.length === 0 ? (
            <div style={{ padding: '32px', textAlign: 'center', color: '#94a3b8', fontSize: '13px' }}>
              No active tickets for team "<strong>{teamName}</strong>". 🎉
            </div>
          ) : tickets.map(t => (
            <div key={t.ticket_number} onClick={() => navigate(`/tickets/${t.ticket_number}`, { state: { from: '/queue' } })}
              style={{ display: 'grid', gridTemplateColumns: '140px 1fr 120px 110px 90px 80px', gap: '12px', padding: '12px 16px', borderBottom: '0.5px solid #f1f5f9', cursor: 'pointer', alignItems: 'center' }}
              onMouseEnter={e => e.currentTarget.style.background = '#f8fafc'}
              onMouseLeave={e => e.currentTarget.style.background = ''}>
              <span style={{ fontSize: '12px', fontFamily: 'monospace', color: '#185FA5' }}>{t.ticket_number}</span>
              <span style={{ fontSize: '13px' }}>{t.original_complaint_text?.slice(0, 55)}{t.original_complaint_text?.length > 55 ? '…' : ''}</span>
              <span style={{ fontSize: '12px', color: '#475569' }}>{t.primary_application_name ?? '—'}</span>
              <Badge label={t.fault_type?.replace(/_/g, ' ') ?? '—'} color="#534AB7" bg="#EEEDFE" />
              <Badge label={t.severity ?? '—'} color={SEVERITY_COLOR[t.severity]} bg={(SEVERITY_COLOR[t.severity] || '#888') + '22'} />
              <Badge label={t.status ?? '—'} color={STATUS_COLOR[t.status]} bg={(STATUS_COLOR[t.status] || '#888') + '22'} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default TeamQueue;

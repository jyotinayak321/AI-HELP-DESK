export const FAULT_TYPES = [
  { value: 'login_access',     label: 'Login / Access' },
  { value: 'performance_slow', label: 'Performance / Slow' },
  { value: 'data_error',       label: 'Data Error' },
  { value: 'total_outage',     label: 'Total Outage' },
  { value: 'partial_degraded', label: 'Partial / Degraded' },
  { value: 'cosmetic_ui',      label: 'Cosmetic / UI' },
  { value: 'other',            label: 'Other' },
];

export const SEVERITY_LEVELS = [
  { value: 'critical', label: 'Critical', color: '#e24b4a' },
  { value: 'high',     label: 'High',     color: '#EF9F27' },
  { value: 'normal',   label: 'Normal',   color: '#378ADD' },
  { value: 'low',      label: 'Low',      color: '#639922' },
];

export const TICKET_STATUSES = [
  { value: 'open',     label: 'Open' },
  { value: 'triage',   label: 'Triage' },
  { value: 'assigned', label: 'Assigned' },
  { value: 'resolved', label: 'Resolved' },
  { value: 'closed',   label: 'Closed' },
  { value: 'reopened', label: 'Reopened' },
];

export const SEVERITY_COLOR = Object.fromEntries(
  SEVERITY_LEVELS.map(s => [s.value, s.color])
);

export const STATUS_COLOR = {
  open:     '#EF9F27',
  triage:   '#e24b4a',
  assigned: '#378ADD',
  resolved: '#639922',
  closed:   '#888',
  reopened: '#534AB7',
};
/**
 * detectOutages.js
 * ----------------
 * Flags a likely systemic/common issue: 3+ open tickets for the same
 * application created within the last hour. Used on both Dashboard.jsx
 * (visible to every logged-in user, operator or admin) and TeamQueue.jsx
 * (admin-only) so a common outage ("server down", "slow") surfaces
 * everywhere instead of looking like unrelated one-off tickets.
 */
const ONE_HOUR = 60 * 60 * 1000;

export function detectOutages(tickets) {
  const appCount = {};
  const now = Date.now();
  tickets.forEach(t => {
    if (t.status === 'open') {
      const age = now - new Date(t.created_at).getTime();
      if (age <= ONE_HOUR) {
        const appName = t.primary_application_name || 'Unknown';
        appCount[appName] = (appCount[appName] || 0) + 1;
      }
    }
  });
  return Object.entries(appCount)
    .filter(([, count]) => count >= 3)
    .map(([app, count]) => ({ app, count }));
}

import { useLocation } from 'react-router-dom';
import { Bell } from 'lucide-react';

const PAGE_TITLES = {
  '/dashboard': 'Dashboard',
  '/submit':    'Submit Complaint',
  '/classify':  'Review Classification',
  '/tickets':   'Tickets',
  '/registry':  'Application Registry',
};

function Topbar() {
  const { pathname } = useLocation();
  return (
    <div style={{
      height: '52px', background: '#fff',
      borderBottom: '0.5px solid #e2e8f0',
      display: 'flex', alignItems: 'center',
      justifyContent: 'space-between',
      padding: '0 24px', flexShrink: 0,
    }}>
      <span style={{ fontWeight: 500, fontSize: '15px' }}>
        {PAGE_TITLES[pathname] || 'IAF Help Desk'}
      </span>
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        <Bell size={18} color="#64748b" />
        <div style={{
          width: '28px', height: '28px', borderRadius: '50%',
          background: '#185FA5', color: '#fff',
          display: 'flex', alignItems: 'center',
          justifyContent: 'center', fontSize: '11px', fontWeight: 500,
        }}>OP</div>
      </div>
    </div>
  );
}

export default Topbar;
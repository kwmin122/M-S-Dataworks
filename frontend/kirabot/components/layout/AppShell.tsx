import React from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import Sidebar from '../chat/Sidebar';
import type { User } from '../../types';

interface AppShellProps {
  user: User | null;
  onLogout: () => void;
}

const AppShell: React.FC<AppShellProps> = ({ user, onLogout }) => {
  const navigate = useNavigate();
  const location = useLocation();
  // /settings/* routes hide sidebar EXCEPT /settings/alerts (stays in sidebar nav)
  const isFullScreenSettings = location.pathname.startsWith('/settings')
    && !location.pathname.startsWith('/settings/alerts');

  return (
    <div className="flex h-screen overflow-hidden bg-slate-50">
      {!isFullScreenSettings && (
        <Sidebar user={user} onLogout={onLogout} onHome={() => navigate('/')} />
      )}
      <div className="flex flex-1 min-w-0 h-full overflow-hidden">
        <Outlet />
      </div>
    </div>
  );
};

export default AppShell;

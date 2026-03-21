import React from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import Sidebar from '../chat/Sidebar';
import ProductTour from '../onboarding/ProductTour';
import type { User } from '../../types';

interface AppShellProps {
  user: User | null;
  onLogout: () => void;
}

const AppShell: React.FC<AppShellProps> = ({ user, onLogout }) => {
  const navigate = useNavigate();
  const location = useLocation();
  // Hide sidebar for /settings/* and /studio/* routes
  const isFullScreenSettings = location.pathname.startsWith('/settings')
    && !location.pathname.startsWith('/settings/alerts');
  const isStudio = location.pathname.startsWith('/studio');
  const hideSidebar = isFullScreenSettings || isStudio;

  return (
    <div className="flex h-screen overflow-hidden bg-slate-50">
      {!hideSidebar && (
        <Sidebar user={user} onLogout={onLogout} onHome={() => navigate('/')} />
      )}
      <div className="flex flex-1 min-w-0 h-full overflow-hidden">
        <Outlet />
      </div>
      <ProductTour />
    </div>
  );
};

export default AppShell;

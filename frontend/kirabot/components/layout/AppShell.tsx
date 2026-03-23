import React, { useState, useCallback, useEffect } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { Menu } from 'lucide-react';
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
  const [mobileOpen, setMobileOpen] = useState(false);

  // Hide sidebar for /settings/* and /studio/* routes
  const isFullScreenSettings = location.pathname.startsWith('/settings')
    && !location.pathname.startsWith('/settings/alerts');
  const isStudio = location.pathname.startsWith('/studio');
  const hideSidebar = isFullScreenSettings || isStudio;

  // Close mobile drawer on route change
  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  const toggleMobileDrawer = useCallback(() => {
    setMobileOpen((prev) => !prev);
  }, []);

  return (
    <div className="flex h-screen overflow-hidden bg-slate-50">
      {!hideSidebar && (
        <>
          {/* Mobile hamburger button */}
          <button
            type="button"
            onClick={toggleMobileDrawer}
            className="fixed top-3 left-3 z-50 md:hidden flex items-center justify-center w-10 h-10 rounded-lg bg-slate-800 text-white shadow-lg"
            aria-label="메뉴 열기"
          >
            <Menu size={20} />
          </button>

          {/* Mobile backdrop overlay */}
          <div
            className={`fixed inset-0 z-40 bg-black/50 transition-opacity duration-300 md:hidden ${
              mobileOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'
            }`}
            onClick={() => setMobileOpen(false)}
            aria-hidden="true"
          />

          {/* Sidebar: hidden off-screen on mobile, visible on md+ */}
          <div
            className={`fixed inset-y-0 left-0 z-40 transition-transform duration-300 ease-in-out md:relative md:translate-x-0 ${
              mobileOpen ? 'translate-x-0' : '-translate-x-full'
            }`}
          >
            <Sidebar user={user} onLogout={onLogout} onHome={() => navigate('/')} />
          </div>
        </>
      )}
      <div className="flex flex-1 min-w-0 h-full overflow-hidden">
        <Outlet />
      </div>
      <ProductTour />
    </div>
  );
};

export default AppShell;

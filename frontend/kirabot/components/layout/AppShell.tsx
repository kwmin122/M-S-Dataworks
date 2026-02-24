import React from 'react';
import { Outlet, useNavigate } from 'react-router-dom';
import Sidebar from '../chat/Sidebar';
import type { User } from '../../types';

interface AppShellProps {
  user: User | null;
  onLogout: () => void;
}

const AppShell: React.FC<AppShellProps> = ({ user, onLogout }) => {
  const navigate = useNavigate();
  return (
    <div className="flex h-screen overflow-hidden bg-slate-50">
      <Sidebar user={user} onLogout={onLogout} onHome={() => navigate('/')} />
      <div className="flex flex-1 min-w-0 h-full overflow-hidden">
        <Outlet />
      </div>
    </div>
  );
};

export default AppShell;

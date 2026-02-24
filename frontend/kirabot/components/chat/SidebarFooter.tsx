import React from 'react';
import { LogOut, Home } from 'lucide-react';
import type { User } from '../../types';

interface SidebarFooterProps {
  user: User | null;
  collapsed: boolean;
  onLogout: () => void;
  onHome: () => void;
}

const SidebarFooter: React.FC<SidebarFooterProps> = ({ user, collapsed, onLogout, onHome }) => {
  if (collapsed) {
    return (
      <div className="border-t border-white/10 p-2 space-y-1">
        <button
          type="button"
          onClick={onHome}
          className="flex h-9 w-9 items-center justify-center rounded-lg text-slate-400 hover:bg-sidebar-hover hover:text-white"
          title="홈으로"
        >
          <Home size={16} />
        </button>
        <button
          type="button"
          onClick={onLogout}
          className="flex h-9 w-9 items-center justify-center rounded-lg text-slate-400 hover:bg-sidebar-hover hover:text-white"
          title="로그아웃"
        >
          <LogOut size={16} />
        </button>
      </div>
    );
  }

  return (
    <div className="border-t border-white/10 p-3 space-y-2">
      <div className="flex items-center gap-2">
        {user?.avatarUrl ? (
          <img src={user.avatarUrl} alt="" className="h-8 w-8 rounded-full" />
        ) : (
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-sidebar-hover text-xs text-white">
            {user?.name?.charAt(0) || '?'}
          </div>
        )}
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-white">{user?.name || '사용자'}</p>
          <p className="truncate text-xs text-slate-400">{user?.email || ''}</p>
        </div>
      </div>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={onHome}
          className="flex flex-1 items-center justify-center gap-1 rounded-lg border border-white/10 px-2 py-1.5 text-xs text-slate-300 hover:bg-sidebar-hover"
        >
          <Home size={12} /> 홈
        </button>
        <button
          type="button"
          onClick={onLogout}
          className="flex flex-1 items-center justify-center gap-1 rounded-lg border border-white/10 px-2 py-1.5 text-xs text-slate-300 hover:bg-sidebar-hover"
        >
          <LogOut size={12} /> 로그아웃
        </button>
      </div>
    </div>
  );
};

export default SidebarFooter;

import React, { useState } from 'react';
import { ChevronUp } from 'lucide-react';
import ProfilePopover from '../sidebar/ProfilePopover';
import type { User } from '../../types';

interface SidebarFooterProps {
  user: User | null;
  collapsed: boolean;
  onLogout: () => void;
  onHome: () => void;
}

const SidebarFooter: React.FC<SidebarFooterProps> = ({ user, collapsed, onLogout, onHome }) => {
  const [popoverOpen, setPopoverOpen] = useState(false);

  if (collapsed) {
    return (
      <div className="relative border-t border-white/10 p-2">
        <button
          type="button"
          onClick={() => setPopoverOpen(!popoverOpen)}
          className="flex h-9 w-9 items-center justify-center rounded-lg text-slate-400 hover:bg-sidebar-hover hover:text-white"
          title={user?.name || '사용자'}
        >
          {user?.avatarUrl ? (
            <img src={user.avatarUrl} alt="" className="h-7 w-7 rounded-full" />
          ) : (
            <span className="text-xs">{user?.name?.charAt(0) || '?'}</span>
          )}
        </button>
        <ProfilePopover
          open={popoverOpen}
          onClose={() => setPopoverOpen(false)}
          email={user?.email || ''}
          onLogout={onLogout}
          onHome={onHome}
        />
      </div>
    );
  }

  return (
    <div className="relative border-t border-white/10 p-3">
      <button
        type="button"
        onClick={() => setPopoverOpen(!popoverOpen)}
        className="flex w-full items-center gap-2 rounded-lg px-1 py-1.5 hover:bg-sidebar-hover transition-colors"
      >
        {user?.avatarUrl ? (
          <img src={user.avatarUrl} alt="" className="h-8 w-8 rounded-full shrink-0" />
        ) : (
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-sidebar-hover text-xs text-white shrink-0">
            {user?.name?.charAt(0) || '?'}
          </div>
        )}
        <div className="min-w-0 flex-1 text-left">
          <p className="truncate text-sm font-medium text-white">{user?.name || '사용자'}</p>
          <p className="truncate text-xs text-slate-400">{user?.email || ''}</p>
        </div>
        <ChevronUp size={14} className={`text-slate-400 transition-transform shrink-0 ${popoverOpen ? '' : 'rotate-180'}`} />
      </button>
      <ProfilePopover
        open={popoverOpen}
        onClose={() => setPopoverOpen(false)}
        email={user?.email || ''}
        onLogout={onLogout}
        onHome={onHome}
      />
    </div>
  );
};

export default SidebarFooter;

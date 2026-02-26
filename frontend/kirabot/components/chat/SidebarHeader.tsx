import React from 'react';
import { Plus, PanelLeftClose, Home } from 'lucide-react';

interface SidebarHeaderProps {
  collapsed: boolean;
  onToggle: () => void;
  onNewChat: () => void;
  onHome?: () => void;
}

const SidebarHeader: React.FC<SidebarHeaderProps> = ({ collapsed, onToggle, onNewChat, onHome }) => {
  return (
    <div className={`flex h-14 items-center border-b border-white/10 ${collapsed ? 'justify-center px-1 gap-0.5' : 'justify-between px-3'}`}>
      {collapsed ? (
        <>
          {onHome && (
            <button
              type="button"
              onClick={onHome}
              className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 hover:bg-sidebar-hover hover:text-white"
              title="메인화면"
            >
              <Home size={18} />
            </button>
          )}
          <button
            type="button"
            onClick={onNewChat}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 hover:bg-sidebar-hover hover:text-white"
            title="새 대화"
          >
            <Plus size={18} />
          </button>
        </>
      ) : (
        <>
          <div className="flex items-center gap-1">
            {onHome && (
              <button
                type="button"
                onClick={onHome}
                className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 hover:bg-sidebar-hover hover:text-white transition-colors"
                title="메인화면"
              >
                <Home size={16} />
              </button>
            )}
            <button
              type="button"
              onClick={onNewChat}
              className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm font-medium text-slate-300 hover:bg-sidebar-hover hover:text-white transition-colors"
              title="새 대화"
            >
              <Plus size={16} />
              <span>새 채팅</span>
            </button>
          </div>
          <button
            type="button"
            onClick={onToggle}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 hover:bg-sidebar-hover hover:text-white"
            title="사이드바 접기"
          >
            <PanelLeftClose size={18} />
          </button>
        </>
      )}
    </div>
  );
};

export default SidebarHeader;
